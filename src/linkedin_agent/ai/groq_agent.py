"""Groq integration for AI-powered content generation."""

import logging
from typing import Optional

import httpx
from bs4 import BeautifulSoup
from groq import Groq

from ..config import settings

logger = logging.getLogger(__name__)


def fetch_article_content(url: str, max_chars: int = 4000) -> Optional[str]:
    """Fetch and extract the main text content from an article URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "noscript"]):
            tag.decompose()

        article_content = None
        for selector in ["article", "main", "[role='main']", ".post-content", ".article-content",
                         ".entry-content", "#content", ".content"]:
            content = soup.select_one(selector)
            if content:
                article_content = content
                break

        if not article_content:
            article_content = soup.body if soup.body else soup

        paragraphs = article_content.find_all("p")
        if paragraphs:
            text = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
        else:
            text = article_content.get_text(separator="\n", strip=True)

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        logger.info(f"Fetched {len(text)} chars from {url}")
        return text if text else None

    except Exception as e:
        logger.warning(f"Failed to fetch article content from {url}: {e}")
        return None


class GroqAgent:
    """AI Agent powered by Groq for generating LinkedIn posts."""

    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.groq_model
        self.enabled = bool(settings.groq_api_key)

    def is_available(self) -> bool:
        return self.enabled

    def generate_linkedin_post(
        self,
        title: str,
        url: str,
        summary: str,
        article_content: Optional[str] = None,
    ) -> Optional[str]:
        if not self.enabled:
            return None

        if not article_content:
            article_content = fetch_article_content(url)

        try:
            prompt = self._build_prompt(title, url, summary, article_content)
            logger.info(f"Generating Groq post for: {title}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            post_text = response.choices[0].message.content.strip()
            post_text = self._clean_response(post_text, url)
            logger.info(f"Groq generated post ({len(post_text)} chars)")
            return post_text

        except Exception as e:
            logger.error(f"Groq generation failed: {e}", exc_info=True)
            return None

    def _get_system_prompt(self) -> str:
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
        if article_content:
            content_section = f"\n\nArticle content:\n{article_content}\n\n"
        else:
            content_section = "\n\nNote: Could not fetch full article content. Write based on title and summary only.\n\n"

        return f"""Write a natural LinkedIn post about this article:

Title: {title}
Summary: {summary if summary else "No summary provided"}
{content_section}Link: {url}

Write like a real person sharing something they found interesting. Be conversational and authentic."""

    def _clean_response(self, text: str, url: str) -> str:
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

        if url not in text:
            if "#" in text:
                parts = text.rsplit("\n#", 1)
                if len(parts) == 2:
                    text = f"{parts[0]}\n\nRead more: {url}\n\n#{parts[1]}"
                else:
                    text += f"\n\nRead more: {url}"
            else:
                text += f"\n\nRead more: {url}"

        if "#" not in text:
            text += "\n\n#tech #innovation #technology"

        return text


_agent: Optional[GroqAgent] = None


def get_groq_agent() -> GroqAgent:
    global _agent
    if _agent is None:
        _agent = GroqAgent()
    return _agent
