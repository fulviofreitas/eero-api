"""Tests for the exception hierarchy.

Tests cover:
- The ``is_auth_error`` predicate across all exception types
- Constructor compatibility and the optional ``status_code`` / ``retry_after``
  attributes of the authentication and rate-limit exceptions
- The hierarchy position of ``EeroValidationException``
"""

import pytest

from eero.exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroException,
    EeroFeatureUnavailableException,
    EeroNetworkException,
    EeroNotFoundException,
    EeroPremiumRequiredException,
    EeroRateLimitException,
    EeroTimeoutException,
    EeroValidationException,
)


class TestIsAuthError:
    """Tests for the is_auth_error predicate across all exception types."""

    def test_authentication_exception_is_true(self):
        assert EeroAuthenticationException("session expired").is_auth_error() is True

    def test_api_exception_401_is_true(self):
        assert EeroAPIException(401, "Unauthorized").is_auth_error() is True

    def test_api_exception_404_is_false(self):
        assert EeroAPIException(404, "Not Found").is_auth_error() is False

    def test_api_exception_500_is_false(self):
        assert EeroAPIException(500, "Internal Server Error").is_auth_error() is False

    def test_base_exception_is_false(self):
        assert EeroException("something").is_auth_error() is False

    def test_rate_limit_exception_is_false(self):
        assert EeroRateLimitException("rate limited").is_auth_error() is False

    def test_network_exception_is_false(self):
        assert EeroNetworkException("connection refused").is_auth_error() is False

    def test_timeout_exception_is_false(self):
        assert EeroTimeoutException("timed out").is_auth_error() is False

    def test_validation_exception_is_false(self):
        assert EeroValidationException("field", "msg").is_auth_error() is False

    def test_premium_required_exception_is_false(self):
        assert EeroPremiumRequiredException().is_auth_error() is False

    def test_feature_unavailable_exception_is_false(self):
        assert EeroFeatureUnavailableException("featurename").is_auth_error() is False

    def test_not_found_exception_is_false(self):
        assert EeroNotFoundException("network", "abc").is_auth_error() is False


class TestAuthenticationExceptionConstruction:
    """Constructor shapes of EeroAuthenticationException."""

    def test_message_only(self):
        exc = EeroAuthenticationException("session expired")

        assert str(exc) == "session expired"
        assert exc.message == "session expired"
        assert exc.envelope is None
        assert exc.error_code is None
        assert exc.status_code is None

    def test_bare_class_with_no_arguments(self):
        exc = EeroAuthenticationException()

        assert exc.message == "An error occurred"
        assert exc.status_code is None

    def test_envelope_and_error_code(self):
        envelope = {"meta": {"code": 401, "error": "error.session.expired"}}

        exc = EeroAuthenticationException(
            "error.session.expired", envelope=envelope, error_code="error.session.expired"
        )

        assert exc.envelope is envelope
        assert exc.error_code == "error.session.expired"
        assert exc.status_code is None

    def test_status_code_is_carried(self):
        assert EeroAuthenticationException("x", status_code=401).status_code == 401

    def test_status_code_is_keyword_only(self):
        with pytest.raises(TypeError):
            EeroAuthenticationException("x", None, None, 401)


class TestRateLimitExceptionConstruction:
    """Constructor shapes of EeroRateLimitException."""

    def test_message_only(self):
        exc = EeroRateLimitException("rate limited")

        assert str(exc) == "rate limited"
        assert exc.message == "rate limited"
        assert exc.envelope is None
        assert exc.error_code is None
        assert exc.status_code is None
        assert exc.retry_after is None

    def test_bare_class_with_no_arguments(self):
        exc = EeroRateLimitException()

        assert exc.message == "An error occurred"
        assert exc.status_code is None
        assert exc.retry_after is None

    def test_envelope_and_error_code(self):
        envelope = {"meta": {"code": 429, "error": "error.rate.limit"}}

        exc = EeroRateLimitException(
            "error.rate.limit", envelope=envelope, error_code="error.rate.limit"
        )

        assert exc.envelope is envelope
        assert exc.error_code == "error.rate.limit"
        assert exc.status_code is None
        assert exc.retry_after is None

    def test_status_code_and_retry_after_are_carried(self):
        exc = EeroRateLimitException("x", status_code=429, retry_after=12.5)

        assert exc.status_code == 429
        assert exc.retry_after == 12.5

    def test_new_attributes_are_keyword_only(self):
        with pytest.raises(TypeError):
            EeroRateLimitException("x", None, None, 429)


class TestExceptionHierarchy:
    """Positions in the hierarchy that downstream callers rely on."""

    def test_validation_exception_is_not_an_api_exception(self):
        """A client-side validation failure has no HTTP status, so it stays a direct child."""
        assert EeroValidationException.__bases__ == (EeroException,)
        assert not issubclass(EeroValidationException, EeroAPIException)

    def test_authentication_and_rate_limit_stay_direct_children_of_base(self):
        assert EeroAuthenticationException.__bases__ == (EeroException,)
        assert EeroRateLimitException.__bases__ == (EeroException,)
