"""Tests for Eero exceptions module.

Tests cover:
- Exception hierarchy and inheritance
- Exception message formatting
- Status code handling for API exceptions
- Resource type handling for not found exceptions
"""

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


class TestEeroException:
    """Tests for base EeroException."""

    def test_default_message(self):
        """Test default error message."""
        exc = EeroException()
        assert str(exc) == "An error occurred"

    def test_custom_message(self):
        """Test custom error message."""
        exc = EeroException("Custom error message")
        assert str(exc) == "Custom error message"
        assert exc.message == "Custom error message"

    def test_inheritance(self):
        """Test that EeroException inherits from Exception."""
        exc = EeroException()
        assert isinstance(exc, Exception)


class TestEeroAuthenticationException:
    """Tests for EeroAuthenticationException."""

    def test_inherits_from_base(self):
        """Test inheritance from EeroException."""
        exc = EeroAuthenticationException("Auth failed")
        assert isinstance(exc, EeroException)
        assert isinstance(exc, Exception)

    def test_message(self):
        """Test exception message."""
        exc = EeroAuthenticationException("Invalid credentials")
        assert str(exc) == "Invalid credentials"


class TestEeroAPIException:
    """Tests for EeroAPIException."""

    def test_requires_status_code(self):
        """Test that status code is required."""
        exc = EeroAPIException(404, "Not found")
        assert exc.status_code == 404

    def test_message_format(self):
        """Test formatted error message."""
        exc = EeroAPIException(500, "Internal server error")
        assert "500" in str(exc)
        assert "Internal server error" in str(exc)

    def test_inherits_from_base(self):
        """Test inheritance from EeroException."""
        exc = EeroAPIException(400, "Bad request")
        assert isinstance(exc, EeroException)

    def test_various_status_codes(self):
        """Test with various HTTP status codes."""
        codes_and_messages = [
            (400, "Bad Request"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Not Found"),
            (429, "Too Many Requests"),
            (500, "Internal Server Error"),
            (502, "Bad Gateway"),
            (503, "Service Unavailable"),
        ]

        for code, message in codes_and_messages:
            exc = EeroAPIException(code, message)
            assert exc.status_code == code
            assert message in str(exc)


class TestEeroRateLimitException:
    """Tests for EeroRateLimitException."""

    def test_inherits_from_base(self):
        """Test inheritance from EeroException."""
        exc = EeroRateLimitException("Rate limit exceeded")
        assert isinstance(exc, EeroException)

    def test_message(self):
        """Test exception message."""
        exc = EeroRateLimitException("Too many requests")
        assert str(exc) == "Too many requests"


class TestEeroNetworkException:
    """Tests for EeroNetworkException."""

    def test_inherits_from_base(self):
        """Test inheritance from EeroException."""
        exc = EeroNetworkException("Connection failed")
        assert isinstance(exc, EeroException)

    def test_message(self):
        """Test exception message."""
        exc = EeroNetworkException("Network unreachable")
        assert str(exc) == "Network unreachable"


class TestEeroTimeoutException:
    """Tests for EeroTimeoutException."""

    def test_inherits_from_base(self):
        """Test inheritance from EeroException."""
        exc = EeroTimeoutException("Request timed out")
        assert isinstance(exc, EeroException)

    def test_message(self):
        """Test exception message."""
        exc = EeroTimeoutException("Operation timed out after 30 seconds")
        assert str(exc) == "Operation timed out after 30 seconds"


class TestEeroNotFoundException:
    """Tests for EeroNotFoundException."""

    def test_requires_resource_info(self):
        """Test that resource type and ID are required."""
        exc = EeroNotFoundException("network", "network_123")
        assert exc.resource_type == "network"
        assert exc.resource_id == "network_123"

    def test_message_format(self):
        """Test formatted error message."""
        exc = EeroNotFoundException("device", "device_abc")
        assert "device" in str(exc)
        assert "device_abc" in str(exc)

    def test_inherits_from_base(self):
        """Test inheritance from EeroException."""
        exc = EeroNotFoundException("eero", "eero_001")
        assert isinstance(exc, EeroException)

    def test_various_resource_types(self):
        """Test with various resource types."""
        resource_types = ["network", "device", "eero", "profile", "reservation"]

        for resource_type in resource_types:
            exc = EeroNotFoundException(resource_type, f"{resource_type}_123")
            assert resource_type in str(exc)


class TestEeroPremiumRequiredException:
    """Tests for EeroPremiumRequiredException."""

    def test_default_message(self):
        """Test default message."""
        exc = EeroPremiumRequiredException()
        assert "This feature" in str(exc)
        assert "Eero Plus" in str(exc)

    def test_custom_feature(self):
        """Test with custom feature name."""
        exc = EeroPremiumRequiredException("Ad blocking")
        assert exc.feature == "Ad blocking"
        assert "Ad blocking" in str(exc)
        assert "Eero Plus" in str(exc)

    def test_inherits_from_base(self):
        """Test inheritance from EeroException."""
        exc = EeroPremiumRequiredException()
        assert isinstance(exc, EeroException)


class TestEeroFeatureUnavailableException:
    """Tests for EeroFeatureUnavailableException."""

    def test_requires_feature_name(self):
        """Test that feature name is required."""
        exc = EeroFeatureUnavailableException("Thread")
        assert exc.feature == "Thread"

    def test_default_reason(self):
        """Test default reason."""
        exc = EeroFeatureUnavailableException("Thread")
        assert "not supported on this device" in str(exc)

    def test_custom_reason(self):
        """Test with custom reason."""
        exc = EeroFeatureUnavailableException("IPv6", reason="not enabled in network settings")
        assert exc.reason == "not enabled in network settings"
        assert "IPv6" in str(exc)
        assert "not enabled" in str(exc)

    def test_inherits_from_base(self):
        """Test inheritance from EeroException."""
        exc = EeroFeatureUnavailableException("WPA3")
        assert isinstance(exc, EeroException)


class TestEeroValidationException:
    """Tests for EeroValidationException."""

    def test_requires_field_and_message(self):
        """Test that field and message are required."""
        exc = EeroValidationException("password", "must be at least 8 characters")
        assert exc.field == "password"

    def test_message_format(self):
        """Test formatted error message."""
        exc = EeroValidationException("email", "invalid format")
        assert "email" in str(exc)
        assert "invalid format" in str(exc)

    def test_inherits_from_base(self):
        """Test inheritance from EeroException."""
        exc = EeroValidationException("name", "required")
        assert isinstance(exc, EeroException)


class TestExceptionHierarchy:
    """Tests for overall exception hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Test that all exceptions inherit from EeroException."""
        exception_classes = [
            EeroAuthenticationException("test"),
            EeroAPIException(400, "test"),
            EeroRateLimitException("test"),
            EeroNetworkException("test"),
            EeroTimeoutException("test"),
            EeroNotFoundException("resource", "id"),
            EeroPremiumRequiredException(),
            EeroFeatureUnavailableException("feature"),
            EeroValidationException("field", "message"),
        ]

        for exc in exception_classes:
            assert isinstance(
                exc, EeroException
            ), f"{type(exc).__name__} should inherit from EeroException"

    def test_all_exceptions_are_catchable_by_base(self):
        """Test that all exceptions can be caught by base exception."""

        def raise_and_catch(exc_class, *args, **kwargs):
            try:
                raise exc_class(*args, **kwargs)
            except EeroException as e:
                return e
            return None

        assert raise_and_catch(EeroAuthenticationException, "test") is not None
        assert raise_and_catch(EeroAPIException, 400, "test") is not None
        assert raise_and_catch(EeroRateLimitException, "test") is not None
        assert raise_and_catch(EeroNetworkException, "test") is not None
        assert raise_and_catch(EeroTimeoutException, "test") is not None
        assert raise_and_catch(EeroNotFoundException, "type", "id") is not None
        assert raise_and_catch(EeroPremiumRequiredException) is not None
        assert raise_and_catch(EeroFeatureUnavailableException, "feature") is not None
        assert raise_and_catch(EeroValidationException, "field", "msg") is not None
