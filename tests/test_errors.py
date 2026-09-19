"""Tests for the ``eero.errors`` error-code catalogue.

Tests cover:
- Catalogue internal consistency (no duplicate strings across groups, every
  string lowercase and stable, every group non-empty)
- ``classify_error_code`` lookup behaviour, including case-insensitivity and
  whitespace trimming
- ``exception_for_error`` class selection is exercised end-to-end through the
  transport in ``tests/api/test_base.py``; this module covers the pure
  catalogue/classification functions in isolation.
"""

import pytest

from eero.errors import (
    _GROUP_MEMBERS,
    ACCESS_DENIED_ERRORS,
    CLIENT_BLOCKED_ERRORS,
    DOMAIN_ERRORS,
    FEATURE_UNAVAILABLE_ERRORS,
    NOT_FOUND_ERRORS,
    PREMIUM_ERRORS,
    RATE_LIMIT_ERRORS,
    SESSION_ERRORS,
    SESSION_REFRESH_ERRORS,
    VALIDATION_ERRORS,
    VERIFICATION_ERRORS,
    ErrorGroup,
    classify_error_code,
)

ALL_GROUPS = [
    SESSION_ERRORS,
    SESSION_REFRESH_ERRORS,
    VERIFICATION_ERRORS,
    ACCESS_DENIED_ERRORS,
    NOT_FOUND_ERRORS,
    RATE_LIMIT_ERRORS,
    VALIDATION_ERRORS,
    PREMIUM_ERRORS,
    FEATURE_UNAVAILABLE_ERRORS,
    CLIENT_BLOCKED_ERRORS,
    DOMAIN_ERRORS,
]


class TestCatalogueConsistency:
    """Tests for the catalogue's internal integrity."""

    def test_every_group_is_non_empty(self):
        """Every catalogue group must contain at least one error string."""
        for group in ALL_GROUPS:
            assert len(group) > 0

    def test_no_duplicate_strings_across_groups(self):
        """No error string may belong to more than one group."""
        total_strings = sum(len(group) for group in ALL_GROUPS)
        union_of_strings = set().union(*ALL_GROUPS)
        assert len(union_of_strings) == total_strings

    def test_every_string_is_lowercase(self):
        """Every catalogue string is stored lowercase (matching is case-insensitive)."""
        for group in ALL_GROUPS:
            for error_string in group:
                assert error_string == error_string.lower()

    def test_every_string_is_non_empty_and_trimmed(self):
        """Every catalogue string is non-empty with no leading/trailing whitespace."""
        for group in ALL_GROUPS:
            for error_string in group:
                assert error_string
                assert error_string == error_string.strip()

    def test_group_members_covers_every_error_group_enum_value(self):
        """_GROUP_MEMBERS must have an entry for every ErrorGroup member."""
        assert set(_GROUP_MEMBERS.keys()) == set(ErrorGroup)

    def test_group_members_values_match_module_level_constants(self):
        """_GROUP_MEMBERS must reference the same frozensets exported at module level."""
        assert _GROUP_MEMBERS[ErrorGroup.SESSION] == SESSION_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.SESSION_REFRESH] == SESSION_REFRESH_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.VERIFICATION] == VERIFICATION_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.ACCESS_DENIED] == ACCESS_DENIED_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.NOT_FOUND] == NOT_FOUND_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.RATE_LIMIT] == RATE_LIMIT_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.VALIDATION] == VALIDATION_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.PREMIUM] == PREMIUM_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.FEATURE_UNAVAILABLE] == FEATURE_UNAVAILABLE_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.CLIENT_BLOCKED] == CLIENT_BLOCKED_ERRORS
        assert _GROUP_MEMBERS[ErrorGroup.DOMAIN] == DOMAIN_ERRORS


class TestClassifyErrorCode:
    """Tests for ``classify_error_code``."""

    def test_none_returns_none(self):
        assert classify_error_code(None) is None

    def test_empty_string_returns_none(self):
        assert classify_error_code("") is None

    def test_unrecognised_string_returns_none(self):
        assert classify_error_code("error.totally_made_up") is None

    def test_free_text_sentence_returns_none(self):
        assert classify_error_code("No parameters were given to check.") is None

    @pytest.mark.parametrize(
        "group,members",
        [
            (ErrorGroup.SESSION, SESSION_ERRORS),
            (ErrorGroup.SESSION_REFRESH, SESSION_REFRESH_ERRORS),
            (ErrorGroup.VERIFICATION, VERIFICATION_ERRORS),
            (ErrorGroup.ACCESS_DENIED, ACCESS_DENIED_ERRORS),
            (ErrorGroup.NOT_FOUND, NOT_FOUND_ERRORS),
            (ErrorGroup.RATE_LIMIT, RATE_LIMIT_ERRORS),
            (ErrorGroup.VALIDATION, VALIDATION_ERRORS),
            (ErrorGroup.PREMIUM, PREMIUM_ERRORS),
            (ErrorGroup.FEATURE_UNAVAILABLE, FEATURE_UNAVAILABLE_ERRORS),
            (ErrorGroup.CLIENT_BLOCKED, CLIENT_BLOCKED_ERRORS),
            (ErrorGroup.DOMAIN, DOMAIN_ERRORS),
        ],
    )
    def test_every_member_of_every_group_classifies_correctly(self, group, members):
        """Every string in every group classifies back to that same group."""
        for error_string in members:
            assert classify_error_code(error_string) is group

    def test_case_insensitive(self):
        assert classify_error_code("ERROR.ACCESS.DENIED") is ErrorGroup.ACCESS_DENIED
        assert classify_error_code("Error.Access.Denied") is ErrorGroup.ACCESS_DENIED

    def test_whitespace_trimmed(self):
        assert classify_error_code("  error.access.denied  ") is ErrorGroup.ACCESS_DENIED
        assert classify_error_code("\terror.session.refresh\n") is ErrorGroup.SESSION_REFRESH
