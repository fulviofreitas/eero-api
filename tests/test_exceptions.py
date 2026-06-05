"""Tests for EeroException.is_auth_error predicate."""

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
