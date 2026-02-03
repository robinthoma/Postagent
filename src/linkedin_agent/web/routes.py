"""Web routes and API endpoints."""

import logging
import secrets
import time
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from ..config import settings
from ..db import Database
from ..models import Draft, Token
from ..linkedin.oauth import (
    generate_authorization_url,
    exchange_code_for_token,
    is_token_valid,
)
from ..linkedin.posting import post_to_linkedin, validate_posting_requirements
from ..feeds.rss import fetch_feed
from ..feeds.normalize import normalize_url
from ..drafting.generator import generate_post_draft
from ..models import Article

logger = logging.getLogger(__name__)

# Templates
templates = Jinja2Templates(directory="src/linkedin_agent/web/templates")

# Store OAuth state temporarily (in production, use Redis or similar)
oauth_states: dict[str, bool] = {}


def create_routes(app: FastAPI, db: Database) -> None:
    """
    Create and register all web routes.

    Args:
        app: FastAPI application instance
        db: Database instance
    """

    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request):
        """Home page with system status."""
        token = db.get_token()
        token_valid = is_token_valid(token)

        # Get counts
        pending_count = len(db.get_drafts(status="PENDING"))
        posted_count = len(db.get_drafts(status="POSTED"))
        failed_count = len(db.get_drafts(status="FAILED"))

        # Check configuration
        config_ok = bool(
            settings.linkedin_client_id
            and settings.linkedin_client_secret
            and settings.feeds
        )

        return templates.TemplateResponse(
            "home.html",
            {
                "request": request,
                "token_valid": token_valid,
                "token": token,
                "config_ok": config_ok,
                "feeds": settings.get_feed_list(),
                "db_path": settings.db_path,
                "poll_seconds": settings.poll_seconds,
                "pending_count": pending_count,
                "posted_count": posted_count,
                "failed_count": failed_count,
            },
        )

    @app.get("/login")
    async def login():
        """Redirect to LinkedIn OAuth authorization."""
        if not settings.linkedin_client_id:
            raise HTTPException(status_code=500, detail="LinkedIn client ID not configured")

        auth_url, state = generate_authorization_url()

        # Store state for validation
        oauth_states[state] = True

        return RedirectResponse(auth_url)

    @app.get("/oauth/linkedin/callback")
    async def oauth_callback(request: Request, code: str = None, state: str = None, error: str = None):
        """Handle OAuth callback from LinkedIn."""
        if error:
            logger.error(f"OAuth error: {error}")
            return HTMLResponse(
                content=f"<h1>OAuth Error</h1><p>{error}</p><a href='/'>Back to Home</a>",
                status_code=400,
            )

        if not code or not state:
            return HTMLResponse(
                content="<h1>OAuth Error</h1><p>Missing code or state parameter</p><a href='/'>Back to Home</a>",
                status_code=400,
            )

        # Validate state
        if state not in oauth_states:
            logger.warning(f"Invalid OAuth state: {state}")
            return HTMLResponse(
                content="<h1>OAuth Error</h1><p>Invalid state parameter (possible CSRF)</p><a href='/'>Back to Home</a>",
                status_code=400,
            )

        # Remove used state
        oauth_states.pop(state, None)

        # Exchange code for token
        token = exchange_code_for_token(code)

        if not token:
            return HTMLResponse(
                content="<h1>OAuth Error</h1><p>Failed to exchange code for token</p><a href='/'>Back to Home</a>",
                status_code=500,
            )

        # Save token to database
        db.save_token(token)

        return HTMLResponse(
            content="<h1>Success!</h1><p>You are now authenticated with LinkedIn.</p><a href='/'>Back to Home</a>"
        )

    @app.post("/poll")
    async def trigger_poll(request: Request):
        """Manually trigger feed polling."""
        logger.info("Manual poll triggered")

        if not settings.feeds:
            return RedirectResponse(url="/?error=no_feeds", status_code=303)

        # Run polling
        await _poll_feeds_and_create_drafts(db)

        return RedirectResponse(url="/drafts?status=PENDING", status_code=303)

    @app.get("/drafts", response_class=HTMLResponse)
    async def list_drafts(request: Request, status: Optional[str] = None):
        """List drafts, optionally filtered by status."""
        drafts = db.get_drafts(status=status)

        return templates.TemplateResponse(
            "drafts.html",
            {
                "request": request,
                "drafts": drafts,
                "filter_status": status,
            },
        )

    @app.post("/drafts/{draft_id}/approve")
    async def approve_draft(request: Request, draft_id: int, csrf_token: str = Form(...)):
        """Approve and post a draft to LinkedIn."""
        # Simple CSRF check (in production, use proper CSRF tokens)
        # For now, just check that token exists
        if not csrf_token:
            raise HTTPException(status_code=400, detail="Missing CSRF token")

        # Get draft
        draft = db.get_draft(draft_id)
        if not draft:
            raise HTTPException(status_code=404, detail="Draft not found")

        if draft.status != "PENDING":
            raise HTTPException(status_code=400, detail="Draft is not pending")

        # Get token
        token = db.get_token()

        # Validate posting requirements
        valid, error = validate_posting_requirements(token)
        if not valid:
            logger.error(f"Posting requirements not met: {error}")
            return RedirectResponse(
                url=f"/drafts?error={error}",
                status_code=303,
            )

        # Check token not expired
        if not is_token_valid(token):
            return RedirectResponse(
                url="/drafts?error=token_expired",
                status_code=303,
            )

        # Post to LinkedIn
        success, response_text = post_to_linkedin(token, draft.post_text)

        # Update draft status
        if success:
            posted_at = int(time.time())
            db.update_draft_status(
                draft_id,
                status="POSTED",
                posted_at=posted_at,
                linkedin_response=response_text,
            )
            db.mark_url_posted(draft.url, posted_at)
            logger.info(f"Draft {draft_id} posted successfully")
            return RedirectResponse(url="/drafts?status=POSTED&success=1", status_code=303)
        else:
            db.update_draft_status(
                draft_id,
                status="FAILED",
                linkedin_response=response_text,
            )
            logger.error(f"Draft {draft_id} failed to post")
            return RedirectResponse(
                url=f"/drafts?status=FAILED&error=posting_failed",
                status_code=303,
            )


async def _poll_feeds_and_create_drafts(db: Database) -> None:
    """
    Poll RSS feeds and create drafts for new articles.

    Args:
        db: Database instance
    """
    feeds = settings.get_feed_list()

    if not feeds:
        logger.warning("No feeds configured")
        return

    total_new = 0

    for feed_url in feeds:
        try:
            articles = fetch_feed(feed_url)

            for article in articles:
                # Normalize URL
                normalized_url = normalize_url(article.url)

                # Check if already seen
                if db.is_url_seen(normalized_url):
                    continue

                # Generate draft
                post_text = generate_post_draft(article)

                # Create draft
                draft = Draft(
                    id=None,
                    title=article.title,
                    url=normalized_url,
                    summary=article.summary,
                    post_text=post_text,
                    status="PENDING",
                    created_at=int(time.time()),
                )

                draft_id = db.create_draft(draft)
                logger.info(f"Created draft {draft_id} for: {article.title}")
                total_new += 1

        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}", exc_info=True)

    logger.info(f"Polling complete. Created {total_new} new drafts.")
