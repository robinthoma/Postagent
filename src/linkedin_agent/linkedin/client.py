"""LinkedIn API client."""

import logging
from typing import Optional

import requests

from ..models import Token

logger = logging.getLogger(__name__)


class LinkedInClient:
    """Client for LinkedIn API operations."""

    BASE_URL = "https://api.linkedin.com/v2"

    def __init__(self, token: Token):
        """
        Initialize LinkedIn client.

        Args:
            token: OAuth token for authentication
        """
        self.token = token

    def get_headers(self) -> dict[str, str]:
        """Get request headers with authentication."""
        return {
            "Authorization": f"Bearer {self.token.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def get_user_info(self) -> Optional[dict]:
        """
        Fetch authenticated user info.

        Returns:
            User info dictionary or None
        """
        try:
            response = requests.get(
                f"{self.BASE_URL}/me",
                headers=self.get_headers(),
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()

            logger.error(f"Failed to get user info: {response.status_code} - {response.text}")
            return None

        except Exception as e:
            logger.error(f"Error fetching user info: {e}", exc_info=True)
            return None
