"""LinkedIn post draft generation with AI-powered content."""

import logging
import random

from ..models import Article
from ..ai.ollama_agent import get_ollama_agent
from ..ai.groq_agent import get_groq_agent
from .rules import DEFAULT_HASHTAGS, MAX_POST_LENGTH, truncate_text, validate_post_text

logger = logging.getLogger(__name__)


def generate_post_draft(article: Article) -> str:
    """
    Generate a LinkedIn post draft from an article.
    
    Uses AI (Ollama) if available, falls back to rule-based generation.

    Args:
        article: Article to create post from

    Returns:
        Post text
    """
    # Try Groq first, then Ollama, then rule-based fallback
    ai_post = _generate_with_groq(article) or _generate_with_ai(article)
    if ai_post:
        # Validate AI-generated post
        is_valid, error = validate_post_text(ai_post)
        if is_valid:
            logger.info("Using AI-generated post")
            return ai_post
        else:
            logger.warning(f"AI post failed validation: {error}, using fallback")

    # Fallback to rule-based generation
    logger.info("Using rule-based post generation")
    return _generate_rule_based(article)


def _generate_with_groq(article: Article) -> str | None:
    """Generate post using Groq AI."""
    try:
        agent = get_groq_agent()
        if not agent.is_available():
            logger.info("Groq not configured, skipping")
            return None
        return agent.generate_linkedin_post(
            title=article.title,
            url=article.url,
            summary=article.summary,
        )
    except Exception as e:
        logger.error(f"Groq generation error: {e}")
        return None


def _generate_with_ai(article: Article) -> str | None:
    """
    Generate post using Ollama AI.
    
    Args:
        article: Article to create post from
        
    Returns:
        AI-generated post or None
    """
    try:
        agent = get_ollama_agent()
        
        if not agent.is_available():
            logger.info("Ollama not available, skipping AI generation")
            return None
        
        return agent.generate_linkedin_post(
            title=article.title,
            url=article.url,
            summary=article.summary,
        )
    except Exception as e:
        logger.error(f"AI generation error: {e}")
        return None


def _generate_rule_based(article: Article) -> str:
    """
    Generate post using simple rules (fallback method).

    Post structure:
    - Title as hook
    - 2-4 bullet takeaways
    - Read link
    - Hashtags

    Args:
        article: Article to create post from

    Returns:
        Post text
    """
    lines = []

    # Add title as hook
    title = article.title.strip()
    lines.append(title)
    lines.append("")  # Empty line

    # Generate takeaways from summary
    takeaways = _generate_takeaways(article.summary)
    if takeaways:
        for takeaway in takeaways:
            lines.append(f"• {takeaway}")
        lines.append("")  # Empty line

    # Add read link
    lines.append(f"Read: {article.url}")
    lines.append("")  # Empty line

    # Add hashtags (3-6 random from defaults)
    num_hashtags = random.randint(3, 6)
    selected_hashtags = random.sample(DEFAULT_HASHTAGS, min(num_hashtags, len(DEFAULT_HASHTAGS)))
    hashtag_line = " ".join(selected_hashtags)
    lines.append(hashtag_line)

    # Join all lines
    post_text = "\n".join(lines)

    # Ensure we're within limits
    if len(post_text) > MAX_POST_LENGTH:
        # Truncate and try to keep structure
        post_text = truncate_text(post_text, MAX_POST_LENGTH)

    # Validate
    is_valid, error = validate_post_text(post_text)
    if not is_valid:
        logger.warning(f"Generated post failed validation: {error}")
        # Fallback to minimal post
        post_text = f"{title}\n\nRead: {article.url}\n\n#tech #innovation"

    return post_text


def _generate_takeaways(summary: str, max_takeaways: int = 4) -> list[str]:
    """
    Generate bullet point takeaways from article summary.

    Simple heuristic approach:
    - Split summary into sentences
    - Take first 2-4 sentences as takeaways
    - Clean and limit length

    Args:
        summary: Article summary text
        max_takeaways: Maximum number of takeaways

    Returns:
        List of takeaway strings
    """
    if not summary or not summary.strip():
        return ["Interesting tech article worth reading"]

    # Simple sentence splitting (split on period followed by space or end)
    import re

    sentences = re.split(r"\.\s+|\.$", summary)
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return ["Key insights and developments"]

    # Take 2-4 sentences
    num_takeaways = min(len(sentences), random.randint(2, max_takeaways))
    takeaways = sentences[:num_takeaways]

    # Clean and limit length of each takeaway
    cleaned = []
    for takeaway in takeaways:
        # Remove URLs from takeaways
        takeaway = re.sub(r"https?://\S+", "", takeaway)
        # Limit length
        if len(takeaway) > 150:
            takeaway = truncate_text(takeaway, 150)
        # Ensure it ends with period
        if takeaway and not takeaway.endswith("."):
            takeaway += "."
        if takeaway:
            cleaned.append(takeaway)

    return cleaned if cleaned else ["Key insights from the article"]
