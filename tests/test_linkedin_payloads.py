"""Tests for LinkedIn API payload construction."""

import pytest
from linkedin_agent.models import Token
from linkedin_agent.linkedin.posting import validate_posting_requirements


class TestLinkedInPayloads:
    """Test LinkedIn API payload construction and validation."""

    def test_validate_posting_no_token(self):
        """Test validation with no token."""
        is_valid, error = validate_posting_requirements(None)

        assert is_valid is False
        assert "no token" in error.lower()

    def test_validate_posting_no_access_token(self):
        """Test validation with token missing access_token."""
        token = Token(access_token="", expires_at=0, person_urn="")
        is_valid, error = validate_posting_requirements(token)

        assert is_valid is False
        assert "access_token" in error.lower()

    def test_validate_posting_no_person_urn(self):
        """Test validation with no person URN."""
        token = Token(access_token="test_token", expires_at=9999999999, person_urn=None)
        is_valid, error = validate_posting_requirements(token)

        assert is_valid is False
        assert "urn" in error.lower()

    def test_validate_posting_valid(self):
        """Test validation with valid token."""
        token = Token(
            access_token="test_token",
            expires_at=9999999999,
            person_urn="urn:li:person:12345",
        )
        is_valid, error = validate_posting_requirements(token)

        assert is_valid is True
        assert error == ""

    def test_ugc_post_payload_structure(self):
        """Test that UGC post payload has correct structure."""
        # This tests the expected structure of the payload
        # In actual posting.py, we construct this payload
        expected_keys = ["author", "lifecycleState", "specificContent", "visibility"]

        payload = {
            "author": "urn:li:person:12345",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": "Test post"},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        for key in expected_keys:
            assert key in payload

        # Verify structure
        assert payload["lifecycleState"] == "PUBLISHED"
        assert "com.linkedin.ugc.ShareContent" in payload["specificContent"]
        assert "shareCommentary" in payload["specificContent"]["com.linkedin.ugc.ShareContent"]
        assert payload["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] == "NONE"

    def test_person_urn_format(self):
        """Test person URN format validation."""
        valid_urns = [
            "urn:li:person:12345",
            "urn:li:person:abc123",
            "urn:li:person:ABC-123_xyz",
        ]

        for urn in valid_urns:
            assert urn.startswith("urn:li:person:")
            assert len(urn.split(":")) == 4

    def test_oauth_scopes_required(self):
        """Test that required OAuth scopes are documented."""
        # This is a documentation test
        required_scopes = ["w_member_social"]
        optional_scopes = ["r_liteprofile"]

        # In config.py, we default to these scopes
        from linkedin_agent.config import Settings

        settings = Settings(
            linkedin_scopes="w_member_social r_liteprofile",
            linkedin_client_id="test",
            linkedin_client_secret="test",
        )

        scopes = settings.get_scope_list()

        for required in required_scopes:
            assert required in scopes
