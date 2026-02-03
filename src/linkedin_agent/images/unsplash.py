"""Unsplash API client for fetching relevant images."""

import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

UNSPLASH_API_URL = "https://api.unsplash.com/search/photos"


@dataclass
class UnsplashImage:
    """Represents an Unsplash image."""
    
    url: str  # Regular size URL for posting
    thumb_url: str  # Thumbnail for preview
    photographer: str
    photographer_url: str
    unsplash_url: str  # Link to photo on Unsplash
    alt_description: Optional[str] = None
    
    def get_attribution(self) -> str:
        """Get attribution text for the image."""
        return f"📷 Photo by {self.photographer} on Unsplash"


async def search_image(query: str) -> Optional[UnsplashImage]:
    """
    Search Unsplash for an image matching the query.
    
    Args:
        query: Search terms (e.g., "AI technology healthcare")
        
    Returns:
        UnsplashImage if found, None otherwise
    """
    if not settings.unsplash_access_key:
        logger.warning("Unsplash API key not configured")
        return None
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                UNSPLASH_API_URL,
                params={
                    "query": query,
                    "per_page": 1,
                    "orientation": "landscape",
                },
                headers={
                    "Authorization": f"Client-ID {settings.unsplash_access_key}",
                },
            )
            
            if response.status_code != 200:
                logger.error(f"Unsplash API error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                logger.info(f"No Unsplash images found for query: {query}")
                return None
            
            photo = results[0]
            
            image = UnsplashImage(
                url=photo["urls"]["regular"],
                thumb_url=photo["urls"]["thumb"],
                photographer=photo["user"]["name"],
                photographer_url=photo["user"]["links"]["html"],
                unsplash_url=photo["links"]["html"],
                alt_description=photo.get("alt_description"),
            )
            
            # Trigger download tracking (required by Unsplash API guidelines)
            download_location = photo.get("links", {}).get("download_location")
            if download_location:
                try:
                    await client.get(
                        download_location,
                        headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"},
                    )
                except Exception:
                    pass  # Non-critical
            
            logger.info(f"Found Unsplash image by {image.photographer} for: {query}")
            return image
            
    except Exception as e:
        logger.error(f"Error searching Unsplash: {e}", exc_info=True)
        return None


def generate_image_search_query(title: str, summary: str = "") -> str:
    """
    Generate a search query for Unsplash based on article title/summary.
    This extracts key themes suitable for image search.
    
    Args:
        title: Article title
        summary: Article summary (optional)
        
    Returns:
        A cleaned search query string
    """
    # Use title as base, strip common noise words
    noise_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
        "be", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "must", "can", "how", "what",
        "when", "where", "why", "who", "which", "that", "this", "these",
        "those", "it", "its", "new", "says", "just", "now", "also", "than",
        "more", "most", "very", "about", "into", "over", "after", "before",
    }
    
    # Combine title and first part of summary
    text = f"{title} {summary[:100] if summary else ''}"
    
    # Clean and filter words
    words = text.lower().split()
    filtered = [w.strip(".,!?:;\"'()[]{}") for w in words if len(w) > 3]
    filtered = [w for w in filtered if w not in noise_words and w.isalpha()]
    
    # Take first 3-5 meaningful words
    query = " ".join(filtered[:5])
    
    return query if query else "technology business"
