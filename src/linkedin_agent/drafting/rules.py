"""Draft post generation rules and limits."""

# LinkedIn post limits
MAX_POST_LENGTH = 3000  # Conservative limit (actual is 3000 chars)
MIN_POST_LENGTH = 1

# Default hashtags for tech content
DEFAULT_HASHTAGS = [
    "#tech",
    "#technology",
    "#innovation",
    "#programming",
    "#development",
    "#software",
]


def validate_post_text(text: str) -> tuple[bool, str]:
    """
    Validate a post text against LinkedIn rules.

    Args:
        text: Post text to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not text or not text.strip():
        return False, "Post text cannot be empty"

    text_length = len(text)

    if text_length < MIN_POST_LENGTH:
        return False, f"Post too short (minimum {MIN_POST_LENGTH} characters)"

    if text_length > MAX_POST_LENGTH:
        return False, f"Post too long (maximum {MAX_POST_LENGTH} characters, got {text_length})"

    return True, ""


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate text to maximum length, adding suffix if needed.

    Args:
        text: Text to truncate
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncating

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    truncate_at = max_length - len(suffix)
    return text[:truncate_at].rstrip() + suffix
