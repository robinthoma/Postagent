"""Tests for draft generation."""

import pytest

from linkedin_agent.models import Article
from linkedin_agent.drafting.generator import generate_post_draft, _generate_takeaways
from linkedin_agent.drafting.rules import validate_post_text, truncate_text, MAX_POST_LENGTH


class TestDraftGeneration:
    """Test draft post generation."""

    def test_generate_post_basic(self):
        """Test basic post generation."""
        article = Article(
            title="Test Article",
            url="https://example.com/article",
            summary="This is a test article. It has multiple sentences. Each provides information.",
        )
        post = generate_post_draft(article)

        assert "Test Article" in post
        assert "https://example.com/article" in post
        assert "#" in post  # Should have hashtags

    def test_generate_post_with_long_summary(self):
        """Test post generation with long summary."""
        long_summary = " ".join(["This is sentence number."] * 50)
        article = Article(
            title="Long Article",
            url="https://example.com/long",
            summary=long_summary,
        )
        post = generate_post_draft(article)

        # Should not exceed maximum length
        assert len(post) <= MAX_POST_LENGTH
        assert "Long Article" in post

    def test_generate_post_with_empty_summary(self):
        """Test post generation with empty summary."""
        article = Article(
            title="No Summary Article",
            url="https://example.com/nosummary",
            summary="",
        )
        post = generate_post_draft(article)

        # Should still generate a valid post
        assert "No Summary Article" in post
        assert "https://example.com/nosummary" in post
        assert len(post) > 0

    def test_generate_takeaways_basic(self):
        """Test takeaway generation."""
        summary = "First sentence. Second sentence. Third sentence. Fourth sentence."
        takeaways = _generate_takeaways(summary)

        assert isinstance(takeaways, list)
        assert len(takeaways) >= 2
        assert len(takeaways) <= 4

    def test_generate_takeaways_empty(self):
        """Test takeaway generation with empty summary."""
        takeaways = _generate_takeaways("")

        assert isinstance(takeaways, list)
        assert len(takeaways) > 0  # Should have fallback

    def test_generate_takeaways_removes_urls(self):
        """Test that URLs are removed from takeaways."""
        summary = "Check out https://example.com for details. More information here."
        takeaways = _generate_takeaways(summary)

        for takeaway in takeaways:
            assert "https://" not in takeaway
            assert "http://" not in takeaway


class TestPostValidation:
    """Test post validation rules."""

    def test_validate_post_valid(self):
        """Test validation of valid post."""
        text = "This is a valid post with sufficient content."
        is_valid, error = validate_post_text(text)

        assert is_valid is True
        assert error == ""

    def test_validate_post_empty(self):
        """Test validation of empty post."""
        is_valid, error = validate_post_text("")

        assert is_valid is False
        assert "empty" in error.lower()

    def test_validate_post_too_long(self):
        """Test validation of too long post."""
        text = "A" * (MAX_POST_LENGTH + 100)
        is_valid, error = validate_post_text(text)

        assert is_valid is False
        assert "too long" in error.lower()

    def test_validate_post_whitespace_only(self):
        """Test validation of whitespace-only post."""
        is_valid, error = validate_post_text("   \n  \t  ")

        assert is_valid is False

    def test_truncate_text_no_truncation(self):
        """Test truncate when text is short enough."""
        text = "Short text"
        result = truncate_text(text, 20)

        assert result == text

    def test_truncate_text_with_truncation(self):
        """Test truncate when text is too long."""
        text = "This is a very long text that needs truncation"
        result = truncate_text(text, 20)

        assert len(result) <= 20
        assert result.endswith("...")

    def test_truncate_text_custom_suffix(self):
        """Test truncate with custom suffix."""
        text = "This is a long text"
        result = truncate_text(text, 15, suffix=">>")

        assert len(result) <= 15
        assert result.endswith(">>")
