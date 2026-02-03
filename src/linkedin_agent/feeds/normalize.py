"""URL normalization and deduplication utilities."""

import logging
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """
    Normalize a URL for deduplication.

    - Lowercase scheme and netloc
    - Remove fragment (#)
    - Remove trailing slash
    - Sort query parameters
    - Remove common tracking parameters

    Args:
        url: URL to normalize

    Returns:
        Normalized URL
    """
    try:
        parsed = urlparse(url)

        # Lowercase scheme and netloc
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path

        # Remove trailing slash from path (unless it's the root)
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        # Parse and filter query parameters
        query_params = parse_qs(parsed.query, keep_blank_values=True)

        # Remove common tracking parameters
        tracking_params = {
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_term",
            "utm_content",
            "fbclid",
            "gclid",
            "ref",
            "source",
        }
        query_params = {k: v for k, v in query_params.items() if k not in tracking_params}

        # Sort and rebuild query string
        query = urlencode(sorted(query_params.items()), doseq=True) if query_params else ""

        # Rebuild URL without fragment
        normalized = urlunparse((scheme, netloc, path, "", query, ""))

        return normalized

    except Exception as e:
        logger.warning(f"Failed to normalize URL {url}: {e}")
        return url
