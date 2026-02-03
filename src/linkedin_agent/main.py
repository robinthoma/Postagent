"""Main FastAPI application."""

import logging
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import Database
from .models import Draft
from .scheduler import FeedScheduler
from .linkedin.oauth import (
    generate_authorization_url,
    exchange_code_for_token,
    is_token_valid,
)
from .linkedin.posting import post_to_linkedin, post_to_linkedin_with_image, validate_posting_requirements
from .feeds.rss import fetch_feed
from .feeds.normalize import normalize_url
from .drafting.generator import generate_post_draft
from .images.unsplash import search_image, generate_image_search_query

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Find template directory
template_dir = Path(__file__).parent / "web" / "templates"
static_dir = Path(__file__).parent / "web" / "static"
templates = Jinja2Templates(directory=str(template_dir))

# Global instances
db: Database = None
scheduler: FeedScheduler = None

# Store OAuth state temporarily
oauth_states: dict[str, bool] = {}


def get_db() -> Database:
    """Get database instance."""
    global db
    if db is None:
        db = Database(settings.db_path)
    return db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    global db, scheduler

    logger.info("Starting LinkedIn Post Agent")

    # Initialize database
    db = Database(settings.db_path)
    logger.info(f"Database initialized at {settings.db_path}")

    # Initialize and start scheduler
    scheduler = FeedScheduler(db)
    scheduler.start()

    yield

    # Shutdown
    logger.info("Shutting down LinkedIn Post Agent")
    if scheduler:
        scheduler.stop()


# Create FastAPI app
app = FastAPI(
    title="LinkedIn Post Agent",
    description="Human-in-the-loop autonomous agent for LinkedIn posting",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ============== ROUTES ==============

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with system status."""
    database = get_db()
    token = database.get_token()
    token_valid = is_token_valid(token)

    # Get counts
    pending_count = len(database.get_drafts(status="PENDING"))
    posted_count = len(database.get_drafts(status="POSTED"))
    failed_count = len(database.get_drafts(status="FAILED"))

    # Check configuration
    config_ok = bool(
        settings.linkedin_client_id
        and settings.linkedin_client_secret
        and settings.feeds
    )
    
    # Get query params for messages
    article_error = request.query_params.get("article_error")
    article_success = request.query_params.get("article_success")
    feed_error = request.query_params.get("feed_error")
    feed_success = request.query_params.get("feed_success")

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
            "article_error": article_error,
            "article_success": article_success,
            "feed_error": feed_error,
            "feed_success": feed_success,
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


@app.post("/logout")
async def logout():
    """Log out by deleting the stored token."""
    database = get_db()
    database.delete_token()
    return RedirectResponse(url="/?logout_success=true", status_code=303)


@app.get("/oauth/linkedin/callback")
async def oauth_callback(
    request: Request, code: str = None, state: str = None, error: str = None
):
    """Handle OAuth callback from LinkedIn."""
    database = get_db()

    if error:
        logger.error(f"OAuth error: {error}")
        return templates.TemplateResponse(
            "oauth_error.html",
            {
                "request": request,
                "error_message": "LinkedIn returned an error during authentication.",
                "error_detail": error,
                "token_valid": False,
                "token": None,
            },
            status_code=400,
        )

    if not code or not state:
        return templates.TemplateResponse(
            "oauth_error.html",
            {
                "request": request,
                "error_message": "Missing authorization code or state parameter.",
                "error_detail": "The OAuth callback did not include required parameters.",
                "token_valid": False,
                "token": None,
            },
            status_code=400,
        )

    # Validate state
    if state not in oauth_states:
        logger.warning(f"Invalid OAuth state: {state}")
        return templates.TemplateResponse(
            "oauth_error.html",
            {
                "request": request,
                "error_message": "Invalid state parameter detected.",
                "error_detail": "This could be a CSRF attack or your session expired. Please try again.",
                "token_valid": False,
                "token": None,
            },
            status_code=400,
        )

    # Remove used state
    oauth_states.pop(state, None)

    # Exchange code for token
    token = exchange_code_for_token(code)

    if not token:
        return templates.TemplateResponse(
            "oauth_error.html",
            {
                "request": request,
                "error_message": "Failed to exchange authorization code for access token.",
                "error_detail": "LinkedIn API may be unavailable. Please try again later.",
                "token_valid": False,
                "token": None,
            },
            status_code=500,
        )

    # Save token to database
    database.save_token(token)

    return templates.TemplateResponse(
        "oauth_success.html",
        {
            "request": request,
            "person_urn": token.person_urn,
            "token_valid": True,
            "token": token,
        },
    )


@app.post("/poll")
async def trigger_poll(request: Request, include_images: bool = Form(False)):
    """Manually trigger feed polling."""
    database = get_db()
    logger.info(f"Manual poll triggered (include_images={include_images})")

    if not settings.feeds:
        return RedirectResponse(url="/?error=no_feeds", status_code=303)

    # Run polling
    await poll_feeds_and_create_drafts(database, include_images=include_images)

    return RedirectResponse(url="/drafts?status=PENDING", status_code=303)


@app.post("/clear-pending")
async def clear_pending_drafts(request: Request):
    """Delete all pending drafts."""
    database = get_db()
    
    deleted_count = database.delete_drafts_by_status("PENDING")
    logger.info(f"Cleared {deleted_count} pending drafts")
    
    return RedirectResponse(url=f"/?article_success=Cleared {deleted_count} pending drafts", status_code=303)


@app.post("/add-article")
async def add_article(request: Request, article_url: str = Form(...), article_title: str = Form(None), include_image: bool = Form(False)):
    """Add a single article URL and generate a draft for it."""
    from .feeds.normalize import normalize_url
    from .feeds.rss import Article
    import httpx
    from bs4 import BeautifulSoup
    
    database = get_db()
    logger.info(f"Adding article: {article_url} (include_image={include_image})")
    
    try:
        # Normalize URL
        normalized_url = normalize_url(article_url)
        
        # Check if already seen
        if database.is_url_seen(normalized_url):
            return RedirectResponse(url="/?article_error=Article already exists", status_code=303)
        
        # Try to fetch article title if not provided
        title = article_title
        summary = ""
        
        if not title:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(article_url, follow_redirects=True)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        title_tag = soup.find('title')
                        title = title_tag.get_text().strip() if title_tag else "Untitled Article"
                        
                        # Try to get meta description
                        meta_desc = soup.find('meta', attrs={'name': 'description'})
                        if meta_desc:
                            summary = meta_desc.get('content', '')[:500]
            except Exception as e:
                logger.warning(f"Could not fetch article metadata: {e}")
                title = article_title or "Untitled Article"
        
        # Create article object
        article = Article(
            title=title or "Untitled Article",
            url=normalized_url,
            summary=summary,
            published=None
        )
        
        # Generate draft using AI
        post_text = generate_post_draft(article)
        
        # Optionally fetch Unsplash image
        image_url = None
        image_thumb_url = None
        image_attribution = None
        
        if include_image and settings.unsplash_access_key:
            search_query = generate_image_search_query(article.title, summary)
            image = await search_image(search_query)
            if image:
                image_url = image.url
                image_thumb_url = image.thumb_url
                image_attribution = image.get_attribution()
        
        # Create draft
        draft = Draft(
            id=None,
            title=article.title,
            url=normalized_url,
            summary=summary,
            post_text=post_text,
            status="PENDING",
            created_at=int(time.time()),
            image_url=image_url,
            image_thumb_url=image_thumb_url,
            image_attribution=image_attribution,
        )
        
        draft_id = database.create_draft(draft)
        logger.info(f"Created draft {draft_id} for article: {article.title}")
        
        return RedirectResponse(url=f"/drafts?status=PENDING&success=Draft created for: {article.title[:50]}", status_code=303)
        
    except Exception as e:
        logger.error(f"Error adding article: {e}", exc_info=True)
        return RedirectResponse(url=f"/?article_error={str(e)[:100]}", status_code=303)


@app.post("/add-feed")
async def add_feed(request: Request, feed_url: str = Form(...)):
    """Add a new RSS feed URL."""
    import feedparser
    
    logger.info(f"Adding RSS feed: {feed_url}")
    
    try:
        # Validate feed URL by trying to parse it
        feed = feedparser.parse(feed_url)
        
        if feed.bozo and not feed.entries:
            return RedirectResponse(url="/?feed_error=Invalid RSS feed URL", status_code=303)
        
        # Get current feeds
        current_feeds = settings.get_feed_list()
        
        if feed_url in current_feeds:
            return RedirectResponse(url="/?feed_error=Feed already exists", status_code=303)
        
        # Add to feeds list
        current_feeds.append(feed_url)
        new_feeds_str = ",".join(current_feeds)
        
        # Update .env file
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if env_path.exists():
            env_content = env_path.read_text()
            
            # Update FEEDS line
            import re
            if "FEEDS=" in env_content:
                env_content = re.sub(
                    r'FEEDS=.*',
                    f'FEEDS={new_feeds_str}',
                    env_content
                )
            else:
                env_content += f"\nFEEDS={new_feeds_str}"
            
            env_path.write_text(env_content)
            
            # Update settings in memory
            settings.feeds = new_feeds_str
            
            logger.info(f"Added feed: {feed_url}")
            return RedirectResponse(url=f"/?feed_success=Feed added: {feed_url[:50]}", status_code=303)
        else:
            return RedirectResponse(url="/?feed_error=Could not update .env file", status_code=303)
            
    except Exception as e:
        logger.error(f"Error adding feed: {e}", exc_info=True)
        return RedirectResponse(url=f"/?feed_error={str(e)[:100]}", status_code=303)


@app.post("/remove-feed")
async def remove_feed(request: Request, feed_url: str = Form(...)):
    """Remove an RSS feed URL."""
    logger.info(f"Removing RSS feed: {feed_url}")
    
    try:
        # Get current feeds
        current_feeds = settings.get_feed_list()
        
        if feed_url not in current_feeds:
            return RedirectResponse(url="/?feed_error=Feed not found", status_code=303)
        
        # Remove from list
        current_feeds.remove(feed_url)
        new_feeds_str = ",".join(current_feeds)
        
        # Update .env file
        env_path = Path(__file__).parent.parent.parent.parent / ".env"
        if env_path.exists():
            env_content = env_path.read_text()
            
            import re
            env_content = re.sub(
                r'FEEDS=.*',
                f'FEEDS={new_feeds_str}',
                env_content
            )
            
            env_path.write_text(env_content)
            
            # Update settings in memory
            settings.feeds = new_feeds_str
            
            logger.info(f"Removed feed: {feed_url}")
            return RedirectResponse(url="/?feed_success=Feed removed", status_code=303)
        else:
            return RedirectResponse(url="/?feed_error=Could not update .env file", status_code=303)
            
    except Exception as e:
        logger.error(f"Error removing feed: {e}", exc_info=True)
        return RedirectResponse(url=f"/?feed_error={str(e)[:100]}", status_code=303)


@app.get("/drafts", response_class=HTMLResponse)
async def list_drafts(request: Request, status: Optional[str] = None):
    """List drafts, optionally filtered by status."""
    database = get_db()
    drafts = database.get_drafts(status=status)
    token = database.get_token()
    token_valid = is_token_valid(token)

    return templates.TemplateResponse(
        "drafts.html",
        {
            "request": request,
            "drafts": drafts,
            "filter_status": status,
            "token": token,
            "token_valid": token_valid,
        },
    )


@app.post("/drafts/{draft_id}/approve")
async def approve_draft(request: Request, draft_id: int, csrf_token: str = Form(...)):
    """Approve and post a draft to LinkedIn."""
    database = get_db()

    # Simple CSRF check
    if not csrf_token:
        raise HTTPException(status_code=400, detail="Missing CSRF token")

    # Get draft
    draft = database.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft.status != "PENDING":
        raise HTTPException(status_code=400, detail="Draft is not pending")

    # Get token
    token = database.get_token()

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

    # Post to LinkedIn (with or without image)
    if draft.image_url:
        success, response_text = post_to_linkedin_with_image(
            token, 
            draft.post_text, 
            draft.image_url,
            draft.image_attribution
        )
    else:
        success, response_text = post_to_linkedin(token, draft.post_text)

    # Update draft status
    if success:
        posted_at = int(time.time())
        database.update_draft_status(
            draft_id,
            status="POSTED",
            posted_at=posted_at,
            linkedin_response=response_text,
        )
        database.mark_url_posted(draft.url, posted_at)
        logger.info(f"Draft {draft_id} posted successfully")
        return RedirectResponse(url="/drafts?status=POSTED&success=1", status_code=303)
    else:
        database.update_draft_status(
            draft_id,
            status="FAILED",
            linkedin_response=response_text,
        )
        logger.error(f"Draft {draft_id} failed to post")
        return RedirectResponse(
            url=f"/drafts?status=FAILED&error=posting_failed",
            status_code=303,
        )


async def poll_feeds_and_create_drafts(database: Database, max_drafts: int = 10, include_images: bool = False) -> None:
    """
    Poll RSS feeds and create drafts for new articles.
    
    Args:
        database: Database instance
        max_drafts: Maximum number of drafts to create (default: 10)
        include_images: Whether to fetch Unsplash images for drafts
    """
    feeds = settings.get_feed_list()

    if not feeds:
        logger.warning("No feeds configured")
        return

    total_new = 0

    for feed_url in feeds:
        if total_new >= max_drafts:
            logger.info(f"Reached max drafts limit ({max_drafts})")
            break
            
        try:
            articles = fetch_feed(feed_url)

            for article in articles:
                if total_new >= max_drafts:
                    break
                    
                # Normalize URL
                normalized_url = normalize_url(article.url)

                # Check if already seen
                if database.is_url_seen(normalized_url):
                    continue

                # Generate draft
                post_text = generate_post_draft(article)
                
                # Optionally fetch Unsplash image
                image_url = None
                image_thumb_url = None
                image_attribution = None
                
                if include_images and settings.unsplash_access_key:
                    search_query = generate_image_search_query(article.title, article.summary)
                    image = await search_image(search_query)
                    if image:
                        image_url = image.url
                        image_thumb_url = image.thumb_url
                        image_attribution = image.get_attribution()

                # Create draft
                draft = Draft(
                    id=None,
                    title=article.title,
                    url=normalized_url,
                    summary=article.summary,
                    post_text=post_text,
                    status="PENDING",
                    created_at=int(time.time()),
                    image_url=image_url,
                    image_thumb_url=image_thumb_url,
                    image_attribution=image_attribution,
                )

                draft_id = database.create_draft(draft)
                logger.info(f"Created draft {draft_id} for: {article.title}")
                total_new += 1

        except Exception as e:
            logger.error(f"Error processing feed {feed_url}: {e}", exc_info=True)

    logger.info(f"Polling complete. Created {total_new} new drafts (limit: {max_drafts}).")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
