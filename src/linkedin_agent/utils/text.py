"""Text processing utilities."""

import re


def clean_text(text: str) -> str:
    """
    Clean and normalize text.

    Args:
        text: Text to clean

    Returns:
        Cleaned text
    """
    # Remove extra whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.

    Args:
        url: URL to parse

    Returns:
        Domain name
    """
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        return parsed.netloc
    except Exception:
        return ""


def truncate_words(text: str, max_words: int) -> str:
    """
    Truncate text to a maximum number of words.

    Args:
        text: Text to truncate
        max_words: Maximum number of words

    Returns:
        Truncated text
    """
    words = text.split()
    if len(words) <= max_words:
        return text

    return " ".join(words[:max_words]) + "..."
