"""LinkedIn OAuth 2.0 Authorization Code Flow."""

import logging
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import requests

from ..config import settings
from ..models import Token

logger = logging.getLogger(__name__)

# LinkedIn OAuth endpoints
AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USER_INFO_URL = "https://api.linkedin.com/v2/userinfo"  # OpenID Connect endpoint


def generate_authorization_url(state: Optional[str] = None) -> tuple[str, str]:
    """
    Generate LinkedIn OAuth authorization URL.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Tuple of (authorization_url, state)
    """
    if not state:
        state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": settings.linkedin_client_id,
        "redirect_uri": settings.linkedin_redirect_uri,
        "scope": " ".join(settings.get_scope_list()),
        "state": state,
    }

    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
    return auth_url, state


def exchange_code_for_token(code: str) -> Optional[Token]:
    """
    Exchange authorization code for access token.

    Args:
        code: Authorization code from callback

    Returns:
        Token object or None if exchange fails
    """
    try:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.linkedin_redirect_uri,
            "client_id": settings.linkedin_client_id,
            "client_secret": settings.linkedin_client_secret,
        }

        logger.info("Exchanging authorization code for access token")
        response = requests.post(
            TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )

        if response.status_code != 200:
            logger.error(
                f"Token exchange failed: {response.status_code} - {response.text}"
            )
            return None

        token_data = response.json()
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 5184000)  # Default 60 days

        if not access_token:
            logger.error("No access token in response")
            return None

        # Calculate expiration timestamp
        expires_at = int(time.time()) + expires_in

        # Try to fetch user info to get person URN
        person_urn = fetch_person_urn(access_token)

        token = Token(
            access_token=access_token,
            expires_at=expires_at,
            person_urn=person_urn,
        )

        logger.info("Successfully obtained access token")
        return token

    except Exception as e:
        logger.error(f"Error exchanging code for token: {e}", exc_info=True)
        return None


def fetch_person_urn(access_token: str) -> Optional[str]:
    """
    Fetch the authenticated user's person URN using OpenID Connect userinfo.

    Args:
        access_token: LinkedIn access token

    Returns:
        Person URN (urn:li:person:XXXX) or None
    """
    try:
        logger.info("Fetching user info from OpenID Connect userinfo endpoint")
        response = requests.get(
            USER_INFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )

        if response.status_code != 200:
            logger.warning(
                f"Failed to fetch user info: {response.status_code} - {response.text}"
            )
            return None

        user_data = response.json()
        # OpenID Connect returns 'sub' as the user ID
        user_id = user_data.get("sub")

        if user_id:
            person_urn = f"urn:li:person:{user_id}"
            logger.info(f"Retrieved person URN: {person_urn}")
            return person_urn

        logger.warning("No 'sub' field in userinfo response")
        return None

    except Exception as e:
        logger.warning(f"Error fetching person URN: {e}")
        return None


def is_token_valid(token: Optional[Token]) -> bool:
    """
    Check if a token is valid (not expired).

    Args:
        token: Token object to check

    Returns:
        True if token is valid
    """
    if not token or not token.access_token:
        return False

    current_time = int(time.time())
    # Add 5-minute buffer
    return token.expires_at > (current_time + 300)
