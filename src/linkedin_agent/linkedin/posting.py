"""LinkedIn UGC Posts API for posting content."""

import logging
from typing import Optional

import requests

from ..config import settings
from ..models import Token

logger = logging.getLogger(__name__)

UGC_POSTS_URL = "https://api.linkedin.com/v2/ugcPosts"
IMAGES_URL = "https://api.linkedin.com/v2/images"


def post_to_linkedin(token: Token, post_text: str) -> tuple[bool, str]:
    """
    Post content to LinkedIn using UGC Posts API.

    Args:
        token: OAuth token with w_member_social scope
        post_text: Text content to post

    Returns:
        Tuple of (success, response_text)
    """
    try:
        # Determine author URN
        author_urn = token.person_urn or settings.linkedin_person_urn

        if not author_urn:
            error = "No person URN available. Set LINKEDIN_PERSON_URN or complete OAuth with r_liteprofile scope."
            logger.error(error)
            return False, error

        # Construct UGC Post payload
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": post_text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        logger.info("Posting to LinkedIn UGC Posts API")
        response = requests.post(
            UGC_POSTS_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code in (200, 201):
            logger.info(f"Successfully posted to LinkedIn: {response.status_code}")
            return True, response.text

        # Handle errors
        error_msg = f"LinkedIn API error: {response.status_code} - {response.text}"
        logger.error(error_msg)
        return False, error_msg

    except Exception as e:
        error_msg = f"Exception posting to LinkedIn: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def post_to_linkedin_with_image(
    token: Token, 
    post_text: str, 
    image_url: str,
    image_attribution: Optional[str] = None
) -> tuple[bool, str]:
    """
    Post content with an image to LinkedIn using UGC Posts API.
    
    This uses the external URL method which shares a link with an image preview.
    
    Args:
        token: OAuth token with w_member_social scope
        post_text: Text content to post
        image_url: URL of the image to include
        image_attribution: Optional attribution text to append

    Returns:
        Tuple of (success, response_text)
    """
    try:
        # Determine author URN
        author_urn = token.person_urn or settings.linkedin_person_urn

        if not author_urn:
            error = "No person URN available."
            logger.error(error)
            return False, error

        # Append attribution to post text if provided
        full_text = post_text
        if image_attribution:
            full_text = f"{post_text}\n\n{image_attribution}"

        # For Unsplash images, we'll post the text with the image as an article share
        # This creates a rich preview with the image
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": full_text},
                    "shareMediaCategory": "ARTICLE",
                    "media": [
                        {
                            "status": "READY",
                            "originalUrl": image_url,
                        }
                    ],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        headers = {
            "Authorization": f"Bearer {token.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        logger.info("Posting to LinkedIn UGC Posts API with image")
        response = requests.post(
            UGC_POSTS_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code in (200, 201):
            logger.info(f"Successfully posted to LinkedIn with image: {response.status_code}")
            return True, response.text

        # Handle errors
        error_msg = f"LinkedIn API error: {response.status_code} - {response.text}"
        logger.error(error_msg)
        return False, error_msg

    except Exception as e:
        error_msg = f"Exception posting to LinkedIn with image: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return False, error_msg


def validate_posting_requirements(token: Optional[Token]) -> tuple[bool, str]:
    """
    Validate that we have all requirements for posting.

    Args:
        token: Token to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not token:
        return False, "No token available. Please login first."

    if not token.access_token:
        return False, "Invalid token: missing access_token"

    # Check for person URN
    author_urn = token.person_urn or settings.linkedin_person_urn
    if not author_urn:
        return (
            False,
            "No person URN available. Set LINKEDIN_PERSON_URN environment variable "
            "or ensure OAuth includes r_liteprofile scope.",
        )

    return True, ""
