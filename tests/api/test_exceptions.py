"""Tests for Eero exceptions module.

Tests cover:
- Exception hierarchy and inheritance
- Exception message formatting
- Status code handling for API exceptions
- Resource type handling for not found exceptions
"""

import pytest

from eero.exceptions import (
    EeroAccessDeniedException,
    EeroAPIException,
    EeroAuthenticationException,
    EeroClientBlockedException,
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

    def test_direct_construction_accepts_envelope_and_error_code(self):
        """Test that the original constructor also accepts envelope/error_code."""
        envelope = {"meta": {"code": 404}}
        exc = EeroNotFoundException(
            "network", "network_123", envelope=envelope, error_code="error.network.not.found"
        )
        assert exc.envelope == envelope
        assert exc.error_code == "error.network.not.found"

    def test_from_response_has_no_resource_type_or_id(self):
        """Test that from_response leaves resource_type/resource_id as None."""
        envelope = {"meta": {"code": 404}}
        exc = EeroNotFoundException.from_response(
            "Resource not found", envelope=envelope, error_code=None
        )
        assert exc.resource_type is None
        assert exc.resource_id is None
        assert exc.envelope == envelope
        assert exc.error_code is None
        assert isinstance(exc, EeroNotFoundException)
        assert isinstance(exc, EeroException)

    def test_from_response_message_is_preserved_verbatim(self):
        """Test that from_response uses the given message unmodified."""
        exc = EeroNotFoundException.from_response("No parameters were given to check.")
        assert str(exc) == "No parameters were given to check."


class TestEeroAccessDeniedException:
    """Tests for EeroAccessDeniedException."""

    def test_inherits_from_api_exception(self):
        """Test inheritance from EeroAPIException (and EeroException transitively)."""
        exc = EeroAccessDeniedException(403, "Forbidden")
        assert isinstance(exc, EeroAPIException)
        assert isinstance(exc, EeroException)

    def test_status_code_and_message(self):
        """Test the inherited EeroAPIException constructor works unchanged."""
        exc = EeroAccessDeniedException(403, "Forbidden", error_code="error.access.denied")
        assert exc.status_code == 403
        assert exc.error_code == "error.access.denied"

    def test_is_not_an_auth_error(self):
        """Test that a 403 access-denied exception is not an auth error."""
        exc = EeroAccessDeniedException(403, "Forbidden")
        assert exc.is_auth_error() is False


class TestEeroClientBlockedException:
    """Tests for EeroClientBlockedException."""

    def test_inherits_from_api_exception(self):
        """Test inheritance from EeroAPIException (and EeroException transitively)."""
        exc = EeroClientBlockedException(400, "Client version blocked")
        assert isinstance(exc, EeroAPIException)
        assert isinstance(exc, EeroException)

    def test_status_code_and_message(self):
        """Test the inherited EeroAPIException constructor works unchanged."""
        exc = EeroClientBlockedException(
            400, "Client version blocked", error_code="error.app.version.blocked"
        )
        assert exc.status_code == 400
        assert exc.error_code == "error.app.version.blocked"


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

    def test_direct_construction_accepts_envelope_and_error_code(self):
        """Test that the original constructor also accepts envelope/error_code."""
        exc = EeroPremiumRequiredException(
            "Ad blocking", envelope={"meta": {"code": 402}}, error_code="error.partner.unavailable"
        )
        assert exc.envelope == {"meta": {"code": 402}}
        assert exc.error_code == "error.partner.unavailable"

    def test_from_response_uses_generic_feature_name(self):
        """Test that from_response falls back to a generic feature name."""
        exc = EeroPremiumRequiredException.from_response(
            "Requires Eero Plus", error_code="error.premium.user_not_subscribed"
        )
        assert exc.feature == "This feature"
        assert str(exc) == "Requires Eero Plus"
        assert exc.error_code == "error.premium.user_not_subscribed"
        assert isinstance(exc, EeroPremiumRequiredException)


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

    def test_direct_construction_accepts_envelope_and_error_code(self):
        """Test that the original constructor also accepts envelope/error_code."""
        exc = EeroFeatureUnavailableException(
            "Thread", envelope={"meta": {"code": 400}}, error_code="error.eero.not.capable"
        )
        assert exc.envelope == {"meta": {"code": 400}}
        assert exc.error_code == "error.eero.not.capable"

    def test_from_response_derives_feature_from_error_code(self):
        """Test that from_response uses error_code as the feature label."""
        exc = EeroFeatureUnavailableException.from_response(
            "eero is offline", error_code="error.eero.offline"
        )
        assert exc.feature == "error.eero.offline"
        assert exc.reason == "eero is offline"
        assert str(exc) == "eero is offline"
        assert isinstance(exc, EeroFeatureUnavailableException)

    def test_from_response_falls_back_to_generic_feature_without_error_code(self):
        """Test that from_response falls back to a generic feature label."""
        exc = EeroFeatureUnavailableException.from_response("Feature unavailable")
        assert exc.feature == "feature"


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

    def test_direct_construction_accepts_envelope_and_error_code(self):
        """Test that the original constructor also accepts envelope/error_code."""
        exc = EeroValidationException(
            "email",
            "invalid format",
            envelope={"meta": {"code": 400}},
            error_code="error.form.errors",
        )
        assert exc.envelope == {"meta": {"code": 400}}
        assert exc.error_code == "error.form.errors"

    def test_from_response_uses_generic_field_name(self):
        """Test that from_response falls back to a generic field name."""
        exc = EeroValidationException.from_response(
            "Email is unavailable", error_code="error.form.email.unavailable"
        )
        assert exc.field == "request"
        assert str(exc) == "Email is unavailable"
        assert isinstance(exc, EeroValidationException)


class TestExceptionHierarchy:
    """Tests for overall exception hierarchy."""

    def test_all_exceptions_inherit_from_base(self):
        """Test that all exceptions inherit from EeroException."""
        exception_classes = [
            EeroAuthenticationException("test"),
            EeroAPIException(400, "test"),
            EeroAccessDeniedException(403, "test"),
            EeroClientBlockedException(400, "test"),
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
        assert raise_and_catch(EeroAccessDeniedException, 403, "test") is not None
        assert raise_and_catch(EeroClientBlockedException, 400, "test") is not None
        assert raise_and_catch(EeroRateLimitException, "test") is not None
        assert raise_and_catch(EeroNetworkException, "test") is not None
        assert raise_and_catch(EeroTimeoutException, "test") is not None
        assert raise_and_catch(EeroNotFoundException, "type", "id") is not None
        assert raise_and_catch(EeroPremiumRequiredException) is not None
        assert raise_and_catch(EeroFeatureUnavailableException, "feature") is not None
        assert raise_and_catch(EeroValidationException, "field", "msg") is not None

    @pytest.mark.parametrize(
        "exc,expected",
        [
            (EeroException("test"), False),
            (EeroAuthenticationException("test"), True),
            (EeroAPIException(401, "test"), True),
            (EeroAPIException(403, "test"), False),
            (EeroAPIException(404, "test"), False),
            (EeroAPIException(500, "test"), False),
            (EeroAccessDeniedException(403, "test"), False),
            (EeroClientBlockedException(400, "test"), False),
            (EeroNotFoundException("network", "id"), False),
            (EeroRateLimitException("test"), False),
            (EeroNetworkException("test"), False),
            (EeroTimeoutException("test"), False),
            (EeroPremiumRequiredException(), False),
            (EeroFeatureUnavailableException("feature"), False),
            (EeroValidationException("field", "msg"), False),
        ],
    )
    def test_is_auth_error_matrix(self, exc, expected):
        """Only an authentication failure (401 family) reports is_auth_error() True.

        Access-denied (403) and not-found (404) are deliberately not auth
        errors -- the caller is authenticated in both cases.
        """
        assert exc.is_auth_error() is expected
