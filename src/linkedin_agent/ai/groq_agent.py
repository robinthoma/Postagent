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
        return """You are writing on behalf of a deep tech founder building a modular exoskeleton for rehabilitation.

WHO YOU ARE:
- Deep tech founder at the intersection of AI, biomechanics, and healthcare
- Building modular assistive exoskeletons for physical rehabilitation
- Navigating hardware manufacturing, clinical validation, and medical regulation
- Positioning: DeepTech Founder | AI + Robotics | Assistive Mobility | Building in the real world

YOUR GOALS ON LINKEDIN:
- Build authority and credibility in deep tech and robotics
- Attract ecosystem partners, clinical pilots, and serious investors
- Document the real building journey — not a highlight reel
- Signal seriousness. Not vanity growth. Not motivational noise.

YOUR 4 CONTENT PILLARS (connect articles to these where relevant):
1. Deep Tech Reality — factory pilots, manufacturing bottlenecks, hardware iteration, compliance
2. AI in Physical Systems — edge AI, predictive rehab, biomechanics data, real-world ML vs theoretical ML
3. Founder Thinking — first-principles breakdowns, hard lessons, why hardware differs from SaaS
4. Ecosystem Observations — healthcare gaps, mobility access, government programs, why deep tech fails

YOUR VOICE:
- Analytical, forward-looking, grounded in execution, slightly contrarian
- Thoughtful skepticism combined with ambition
- Write like someone who has been in the factory, not just read about it

HIGH-LEVERAGE POST FORMATS (use these where they fit naturally):
- Hard Truth — challenge a common assumption in the industry
- Build-in-Public Micro Lesson — a real observation from the building process
- Myth Busting — correct a misunderstanding about deep tech or hardware
- Ecosystem Analysis — zoom out on a market or structural trend
- Technical Simplification — explain something complex in plain terms
- Decision Log — explain a real trade-off and why you chose one path

TONE & STRUCTURE:
- Start with a sharp, specific observation — not a generic hook
- Build with real reasoning, not enthusiasm
- End with a question that invites a genuine technical or strategic conversation
- Include the link naturally
- Max 2-3 relevant hashtags from: #robotics #deeptech #exoskeleton #rehabilitation #AIinHealthcare #hardwarestartups #biomechanics #assistivetechnology

AVOID:
- Generic startup motivation or over-optimism
- "Exciting times ahead", "Game-changer", "Thrilled to share", "Diving deep"
- Buzzword stacking
- Bullet point lists with arrows
- Emojis
- Starting multiple posts the same way

Keep it under 1500 characters. Sound like a founder who builds in the real world."""

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
