"""Database operations using SQLite."""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from .models import Draft, Token

logger = logging.getLogger(__name__)


class Database:
    """SQLite database manager."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_schema()

    def _ensure_db_dir(self) -> None:
        """Create database directory if it doesn't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tokens (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    access_token TEXT,
                    expires_at INTEGER,
                    person_urn TEXT
                );

                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    summary TEXT,
                    post_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    posted_at INTEGER,
                    linkedin_response TEXT,
                    image_url TEXT,
                    image_thumb_url TEXT,
                    image_attribution TEXT
                );

                CREATE TABLE IF NOT EXISTS posted (
                    url TEXT PRIMARY KEY,
                    posted_at INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status);
                CREATE INDEX IF NOT EXISTS idx_drafts_url ON drafts(url);
            """
            )
            conn.commit()
            
            # Migration: Add image columns if they don't exist
            self._migrate_image_columns(conn)
        logger.info(f"Database initialized at {self.db_path}")

    def _migrate_image_columns(self, conn: sqlite3.Connection) -> None:
        """Add image columns to drafts table if they don't exist."""
        cursor = conn.execute("PRAGMA table_info(drafts)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "image_url" not in columns:
            conn.execute("ALTER TABLE drafts ADD COLUMN image_url TEXT")
            logger.info("Added image_url column to drafts table")
        if "image_thumb_url" not in columns:
            conn.execute("ALTER TABLE drafts ADD COLUMN image_thumb_url TEXT")
            logger.info("Added image_thumb_url column to drafts table")
        if "image_attribution" not in columns:
            conn.execute("ALTER TABLE drafts ADD COLUMN image_attribution TEXT")
            logger.info("Added image_attribution column to drafts table")
        conn.commit()

    # Token operations
    def save_token(self, token: Token) -> None:
        """Save or update the OAuth token."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO tokens (id, access_token, expires_at, person_urn)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    access_token = excluded.access_token,
                    expires_at = excluded.expires_at,
                    person_urn = excluded.person_urn
            """,
                (token.access_token, token.expires_at, token.person_urn),
            )
            conn.commit()
        logger.info("Token saved to database")

    def get_token(self) -> Optional[Token]:
        """Retrieve the stored OAuth token."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM tokens WHERE id = 1").fetchone()
            if row:
                return Token(
                    access_token=row["access_token"],
                    expires_at=row["expires_at"],
                    person_urn=row["person_urn"],
                )
        return None

    def delete_token(self) -> bool:
        """Delete the stored OAuth token (logout)."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM tokens WHERE id = 1")
            conn.commit()
        logger.info("Token deleted from database (logged out)")
        return True

    # Draft operations
    def create_draft(self, draft: Draft) -> int:
        """Create a new draft. Returns the draft ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO drafts (title, url, summary, post_text, status, created_at, image_url, image_thumb_url, image_attribution)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    draft.title,
                    draft.url,
                    draft.summary,
                    draft.post_text,
                    draft.status,
                    draft.created_at,
                    draft.image_url,
                    draft.image_thumb_url,
                    draft.image_attribution,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_draft(self, draft_id: int) -> Optional[Draft]:
        """Get a draft by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            if row:
                return self._row_to_draft(row)
        return None

    def get_drafts(self, status: Optional[str] = None) -> list[Draft]:
        """Get all drafts, optionally filtered by status."""
        with self._get_connection() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM drafts WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM drafts ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_draft(row) for row in rows]

    def update_draft_status(
        self,
        draft_id: int,
        status: str,
        posted_at: Optional[int] = None,
        linkedin_response: Optional[str] = None,
    ) -> None:
        """Update draft status after posting attempt."""
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE drafts
                SET status = ?, posted_at = ?, linkedin_response = ?
                WHERE id = ?
            """,
                (status, posted_at, linkedin_response, draft_id),
            )
            conn.commit()

    def delete_drafts_by_status(self, status: str) -> int:
        """Delete all drafts with a specific status. Returns count of deleted drafts."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM drafts WHERE status = ?",
                (status,),
            )
            conn.commit()
            return cursor.rowcount

    def is_url_seen(self, url: str) -> bool:
        """Check if URL has been drafted or posted."""
        with self._get_connection() as conn:
            draft_exists = conn.execute(
                "SELECT 1 FROM drafts WHERE url = ? LIMIT 1", (url,)
            ).fetchone()
            posted_exists = conn.execute(
                "SELECT 1 FROM posted WHERE url = ? LIMIT 1", (url,)
            ).fetchone()
            return bool(draft_exists or posted_exists)

    def mark_url_posted(self, url: str, posted_at: int) -> None:
        """Mark a URL as posted."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO posted (url, posted_at) VALUES (?, ?)",
                (url, posted_at),
            )
            conn.commit()

    @staticmethod
    def _row_to_draft(row: sqlite3.Row) -> Draft:
        """Convert database row to Draft object."""
        return Draft(
            id=row["id"],
            title=row["title"],
            url=row["url"],
            summary=row["summary"],
            post_text=row["post_text"],
            status=row["status"],
            created_at=row["created_at"],
            posted_at=row["posted_at"],
            linkedin_response=row["linkedin_response"],
            image_url=row["image_url"] if "image_url" in row.keys() else None,
            image_thumb_url=row["image_thumb_url"] if "image_thumb_url" in row.keys() else None,
            image_attribution=row["image_attribution"] if "image_attribution" in row.keys() else None,
        )
