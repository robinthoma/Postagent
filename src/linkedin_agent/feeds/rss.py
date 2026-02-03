"""RSS feed fetching and parsing."""

import logging
from typing import Optional

import feedparser

from ..models import Article
from ..utils.time import parse_timestamp

logger = logging.getLogger(__name__)


def fetch_feed(url: str) -> list[Article]:
    """
    Fetch and parse an RSS/Atom feed.

    Args:
        url: Feed URL to fetch

    Returns:
        List of Article objects
    """
    try:
        logger.info(f"Fetching feed: {url}")
        feed = feedparser.parse(url)

        if feed.bozo and not feed.entries:
            logger.error(f"Failed to parse feed {url}: {feed.get('bozo_exception', 'Unknown error')}")
            return []

        articles = []
        for entry in feed.entries:
            article = _parse_entry(entry)
            if article:
                articles.append(article)

        logger.info(f"Fetched {len(articles)} articles from {url}")
        return articles

    except Exception as e:
        logger.error(f"Error fetching feed {url}: {e}", exc_info=True)
        return []


def _parse_entry(entry: feedparser.FeedParserDict) -> Optional[Article]:
    """
    Parse a single feed entry into an Article.

    Args:
        entry: Feed entry dictionary

    Returns:
        Article object or None if parsing fails
    """
    try:
        # Extract title
        title = entry.get("title", "").strip()
        if not title:
            return None

        # Extract link
        url = entry.get("link", "").strip()
        if not url:
            return None

        # Extract summary/description
        summary = ""
        if "summary" in entry:
            summary = entry.summary
        elif "description" in entry:
            summary = entry.description
        elif "content" in entry and entry.content:
            summary = entry.content[0].get("value", "")

        # Clean HTML tags from summary (basic)
        summary = _strip_html(summary).strip()

        # Extract published date
        published = None
        if "published_parsed" in entry and entry.published_parsed:
            published = parse_timestamp(entry.published_parsed)
        elif "updated_parsed" in entry and entry.updated_parsed:
            published = parse_timestamp(entry.updated_parsed)

        return Article(
            title=title,
            url=url,
            summary=summary,
            published=published,
        )

    except Exception as e:
        logger.warning(f"Failed to parse entry: {e}")
        return None


def _strip_html(text: str) -> str:
    """
    Remove HTML tags from text (basic implementation).

    Args:
        text: Text with potential HTML tags

    Returns:
        Plain text
    """
    import re

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()
