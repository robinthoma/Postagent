"""Background scheduler for polling feeds."""

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import settings
from .db import Database
from .web.routes import _poll_feeds_and_create_drafts

logger = logging.getLogger(__name__)


class FeedScheduler:
    """Background scheduler for polling RSS feeds."""

    def __init__(self, db: Database):
        """
        Initialize the scheduler.

        Args:
            db: Database instance
        """
        self.db = db
        self.scheduler = BackgroundScheduler()

    def start(self) -> None:
        """Start the scheduler."""
        if not settings.feeds:
            logger.warning("No feeds configured, scheduler will not run")
            return

        # Add job to poll feeds
        self.scheduler.add_job(
            func=self._poll_job,
            trigger=IntervalTrigger(seconds=settings.poll_seconds),
            id="poll_feeds",
            name="Poll RSS feeds and create drafts",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info(f"Scheduler started. Polling every {settings.poll_seconds} seconds.")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    def _poll_job(self) -> None:
        """Job function for polling feeds."""
        try:
            logger.info("Running scheduled feed poll")
            # Run the async function in sync context
            import asyncio

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            loop.run_until_complete(_poll_feeds_and_create_drafts(self.db))
        except Exception as e:
            logger.error(f"Error in scheduled poll job: {e}", exc_info=True)
