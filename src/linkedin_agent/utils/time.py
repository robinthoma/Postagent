"""Time and date utilities."""

import time
from typing import Optional
from time import struct_time


def parse_timestamp(time_struct: Optional[struct_time]) -> Optional[int]:
    """
    Convert time.struct_time to Unix timestamp.

    Args:
        time_struct: Time structure from feedparser

    Returns:
        Unix timestamp or None
    """
    if not time_struct:
        return None

    try:
        return int(time.mktime(time_struct))
    except Exception:
        return None


def timestamp_to_string(timestamp: int) -> str:
    """
    Convert Unix timestamp to human-readable string.

    Args:
        timestamp: Unix timestamp

    Returns:
        Formatted date string
    """
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
    except Exception:
        return str(timestamp)
