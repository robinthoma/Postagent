"""Tests for RSS feed parsing and normalization."""

import pytest

from linkedin_agent.feeds.rss import _strip_html, _parse_entry
from linkedin_agent.feeds.normalize import normalize_url


class TestRSSParsing:
    """Test RSS feed parsing functions."""

    def test_strip_html_basic(self):
        """Test basic HTML stripping."""
        html = "<p>This is <b>bold</b> text</p>"
        result = _strip_html(html)
        assert result == "This is bold text"

    def test_strip_html_multiple_tags(self):
        """Test stripping multiple HTML tags."""
        html = "<div><p>Test</p><span>content</span></div>"
        result = _strip_html(html)
        assert "Test" in result
        assert "content" in result
        assert "<" not in result

    def test_strip_html_whitespace(self):
        """Test whitespace normalization."""
        html = "<p>Test    with   spaces</p>"
        result = _strip_html(html)
        assert result == "Test with spaces"

    def test_parse_entry_minimal(self):
        """Test parsing entry with minimal data."""
        entry = {
            "title": "Test Article",
            "link": "https://example.com/article",
            "summary": "This is a test summary",
        }
        article = _parse_entry(entry)
        assert article is not None
        assert article.title == "Test Article"
        assert article.url == "https://example.com/article"
        assert article.summary == "This is a test summary"

    def test_parse_entry_no_title(self):
        """Test parsing entry without title returns None."""
        entry = {"link": "https://example.com/article"}
        article = _parse_entry(entry)
        assert article is None

    def test_parse_entry_no_link(self):
        """Test parsing entry without link returns None."""
        entry = {"title": "Test Article"}
        article = _parse_entry(entry)
        assert article is None


class TestURLNormalization:
    """Test URL normalization for deduplication."""

    def test_normalize_basic_url(self):
        """Test basic URL normalization."""
        url = "https://example.com/article"
        result = normalize_url(url)
        assert result == "https://example.com/article"

    def test_normalize_removes_fragment(self):
        """Test that URL fragments are removed."""
        url = "https://example.com/article#section"
        result = normalize_url(url)
        assert result == "https://example.com/article"

    def test_normalize_removes_trailing_slash(self):
        """Test trailing slash removal."""
        url = "https://example.com/article/"
        result = normalize_url(url)
        assert result == "https://example.com/article"

    def test_normalize_lowercase_domain(self):
        """Test domain lowercasing."""
        url = "https://EXAMPLE.COM/article"
        result = normalize_url(url)
        assert "example.com" in result

    def test_normalize_removes_tracking_params(self):
        """Test removal of tracking parameters."""
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result

    def test_normalize_preserves_real_params(self):
        """Test that non-tracking parameters are preserved."""
        url = "https://example.com/article?id=123&page=2"
        result = normalize_url(url)
        assert "id=123" in result
        assert "page=2" in result

    def test_normalize_sorts_params(self):
        """Test that query parameters are sorted."""
        url1 = "https://example.com/article?b=2&a=1"
        url2 = "https://example.com/article?a=1&b=2"
        result1 = normalize_url(url1)
        result2 = normalize_url(url2)
        assert result1 == result2

    def test_normalize_deduplication(self):
        """Test that different URLs normalize to same value."""
        urls = [
            "https://example.com/article?utm_source=test",
            "https://EXAMPLE.com/article/",
            "https://example.com/article#comments",
            "https://example.com/article",
        ]
        normalized = [normalize_url(url) for url in urls]
        # All should normalize to the same URL
        assert len(set(normalized)) == 1
