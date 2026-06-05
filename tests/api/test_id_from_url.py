"""Tests for the id_from_url helper in eero.api.base.

Tests cover:
- Bare numeric ID returned unchanged
- Bare opaque ID returned unchanged
- Full URL fragment: trailing segment extracted
- Nested URL fragment: deepest segment extracted
- URL with trailing slash handled correctly
- Absolute URL: trailing segment extracted
- Empty string raises EeroValidationException
- None raises EeroValidationException
- Non-string (int) raises EeroValidationException
"""

import pytest

from eero.api.base import id_from_url
from eero.exceptions import EeroValidationException

# ========================== Happy-Path Tests ==========================


class TestIdFromUrlHappyPaths:
    """Tests for id_from_url with valid inputs."""

    def test_bare_numeric_id_returned_unchanged(self):
        """Bare numeric ID passes through untouched."""
        assert id_from_url("12345") == "12345"

    def test_bare_opaque_id_returned_unchanged(self):
        """Bare opaque ID with prefix passes through untouched."""
        assert id_from_url("p_abc123") == "p_abc123"

    def test_full_url_fragment_extracts_trailing_id(self):
        """Single-level URL fragment yields the trailing segment."""
        assert id_from_url("/2.2/networks/12345") == "12345"

    def test_nested_url_fragment_extracts_trailing_id(self):
        """Multi-level URL fragment yields the deepest segment."""
        assert id_from_url("/2.2/networks/12345/profiles/p_67890") == "p_67890"

    def test_url_with_trailing_slash_handled(self):
        """Trailing slash is stripped before extraction."""
        assert id_from_url("/2.2/networks/12345/") == "12345"

    def test_absolute_url_extracts_trailing_id(self):
        """Fully-qualified URL yields the trailing path segment."""
        assert id_from_url("https://api-user.e2ro.com/2.2/networks/12345") == "12345"


# ========================== Validation Error Tests ==========================


class TestIdFromUrlValidationErrors:
    """Tests for id_from_url with invalid inputs."""

    def test_empty_string_raises_validation_exception(self):
        """Empty string raises EeroValidationException."""
        with pytest.raises(EeroValidationException) as exc_info:
            id_from_url("")
        assert "id_or_url" in exc_info.value.message

    def test_none_raises_validation_exception(self):
        """None raises EeroValidationException."""
        with pytest.raises(EeroValidationException) as exc_info:
            id_from_url(None)  # type: ignore[arg-type]
        assert "id_or_url" in exc_info.value.message

    def test_non_string_int_raises_validation_exception(self):
        """Non-string integer raises EeroValidationException."""
        with pytest.raises(EeroValidationException) as exc_info:
            id_from_url(12345)  # type: ignore[arg-type]
        assert "id_or_url" in exc_info.value.message
