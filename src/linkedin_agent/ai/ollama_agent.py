"""Ollama integration for AI-powered content generation."""

import logging
from typing import Optional

import ollama
from ollama import Client
import httpx
from bs4 import BeautifulSoup

from ..config import settings

logger = logging.getLogger(__name__)


def fetch_article_content(url: str, max_chars: int = 4000) -> Optional[str]:
    """
    Fetch and extract the main text content from an article URL.
    
    Args:
        url: The article URL
        max_chars: Maximum characters to return (to avoid token limits)
    
    Returns:
        Extracted article text or None if fetch fails
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Remove script, style, nav, footer, header elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()
        
        # Try to find main article content
        article_content = None
        
        # Look for common article containers
        for selector in ["article", "main", "[role='main']", ".post-content", ".article-content", ".entry-content", "#content", ".content"]:
            content = soup.select_one(selector)
            if content:
                article_content = content
                break
        
        # Fall back to body if no article container found
        if not article_content:
            article_content = soup.body if soup.body else soup
        
        # Extract text from paragraphs
        paragraphs = article_content.find_all("p")
        if paragraphs:
            text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        else:
            text = article_content.get_text(separator="\n", strip=True)
        
        # Clean up whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)
        
        # Truncate to max_chars
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        logger.info(f"Fetched {len(text)} chars from {url}")
        return text if text else None
        
    except Exception as e:
        logger.warning(f"Failed to fetch article content from {url}: {e}")
        return None


class OllamaAgent:
    """AI Agent powered by Ollama for generating LinkedIn posts."""

    def __init__(self):
        """Initialize Ollama client."""
        self.client = Client(host=settings.ollama_base_url)
        self.model = settings.ollama_model
        self.enabled = settings.ai_enabled

    def is_available(self) -> bool:
        """Check if Ollama is available and model is loaded."""
        if not self.enabled:
            return False
        try:
            # Try to list models to check connection
            models = self.client.list()
            model_names = [m.model for m in models.models]
            # Check if our model is available (handle tags like :latest)
            available = any(self.model in name or name.startswith(self.model) for name in model_names)
            if not available:
                logger.warning(f"Model {self.model} not found. Available: {model_names}")
            return available
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            return False

    def generate_linkedin_post(
        self,
        title: str,
        url: str,
        summary: str,
        article_content: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generate an engaging LinkedIn post using AI.

        Args:
            title: Article title
            url: Article URL
            summary: Article summary/description
            article_content: Optional full article content for more accurate generation

        Returns:
            Generated post text or None if generation fails
        """
        if not self.enabled:
            logger.info("AI generation disabled, using fallback")
            return None

        # If no article content provided, try to fetch it
        if not article_content:
            logger.info(f"No content provided, fetching from URL: {url}")
            article_content = fetch_article_content(url)

        try:
            prompt = self._build_prompt(title, url, summary, article_content)
            
            logger.info(f"Generating AI post for: {title}")
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                options={
                    "temperature": 0.7,
                    "num_predict": 500,
                },
            )

            post_text = response.message.content.strip()
            
            # Validate and clean the response
            post_text = self._clean_response(post_text, url)
            
            logger.info(f"AI generated post ({len(post_text)} chars)")
            return post_text

        except Exception as e:
            logger.error(f"AI generation failed: {e}", exc_info=True)
            return None

    def _get_system_prompt(self) -> str:
        """Get the system prompt for LinkedIn post generation."""
        return """You are a thoughtful tech professional sharing interesting articles with your network.

Write posts that sound like a real person, not a corporate content creator. Follow these guidelines:

TONE & STYLE:
- Write like you're telling a friend about something cool you just read
- Use natural, conversational language
- Avoid buzzwords, jargon, and "LinkedIn speak"
- No emojis or excessive punctuation
- Keep it genuine and personal

STRUCTURE:
- Start with your personal reaction or a key insight from the article
- Share what specifically caught your attention
- Maybe relate it to something you've experienced or observed
- End with a simple, genuine question to spark discussion
- Include the link naturally in the flow

VARY YOUR OPENINGS - Use different approaches:
- Start with a surprising fact or insight from the article
- Begin with your personal opinion or reaction
- Open with a relevant question or observation
- Reference a current trend or debate the article relates to
- Share what changed your perspective

AVOID:
- Starting every post the same way
- "Exciting times ahead!" or "Game-changer alert!"
- "Thrilled to share" or "Diving deep into"
- Lists with arrows or bullet points
- Corporate motivational language
- Hashtag spam (max 2-3 relevant ones)
- Using emojis

Keep it under 1500 characters. Sound human, be authentic, spark real conversation."""

    def _build_prompt(self, title: str, url: str, summary: str, article_content: Optional[str] = None) -> str:
        """Build the user prompt for post generation."""
        content_section = ""
        if article_content:
            content_section = f"""

Article content:
{article_content}

"""
        else:
            content_section = """

Note: Could not fetch full article content. Write based on the title and summary only.

"""
        
        return f"""Write a natural LinkedIn post about this article:

Title: {title}
Summary: {summary if summary else "No summary provided"}
{content_section}
Link: {url}

Write like a real person sharing something they found interesting. Be conversational and authentic. What would you personally find noteworthy about this? How might you relate it to your own experience or observations?

Don't sound like a content marketer or use corporate LinkedIn speak."""

    def _clean_response(self, text: str, url: str) -> str:
        """Clean and validate the AI response."""
        # Remove common AI preambles
        prefixes_to_remove = [
            "Here's a LinkedIn post",
            "Here is a LinkedIn post",
            "Sure, here's",
            "Sure! Here's",
            "Here's an engaging",
        ]
        for prefix in prefixes_to_remove:
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix):].lstrip(":").strip()

        # Ensure URL is in the post
        if url not in text:
            # Add URL before hashtags if missing
            if "#" in text:
                parts = text.rsplit("\n#", 1)
                if len(parts) == 2:
                    text = f"{parts[0]}\n\n🔗 Read more: {url}\n\n#{parts[1]}"
                else:
                    text += f"\n\n🔗 Read more: {url}"
            else:
                text += f"\n\n🔗 Read more: {url}"

        # Ensure we have hashtags
        if "#" not in text:
            text += "\n\n#tech #innovation #technology"

        return text


# Global agent instance
_agent: Optional[OllamaAgent] = None


def get_ollama_agent() -> OllamaAgent:
    """Get or create the Ollama agent singleton."""
    global _agent
    if _agent is None:
        _agent = OllamaAgent()
    return _agent
