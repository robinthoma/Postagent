"""Data models for the application."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Token:
    """OAuth access token with expiration."""

    access_token: str
    expires_at: int  # Unix timestamp
    person_urn: Optional[str] = None


@dataclass
class Draft:
    """A draft LinkedIn post."""

    id: Optional[int]
    title: str
    url: str
    summary: str
    post_text: str
    status: str  # PENDING, POSTED, FAILED
    created_at: int
    posted_at: Optional[int] = None
    linkedin_response: Optional[str] = None
    # Image fields (optional)
    image_url: Optional[str] = None
    image_thumb_url: Optional[str] = None
    image_attribution: Optional[str] = None


@dataclass
class Article:
    """Parsed article from RSS feed."""

    title: str
    url: str
    summary: str
    published: Optional[int] = None  # Unix timestamp
