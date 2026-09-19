"""Exceptions for the Eero API package."""

from typing import Any, Dict, Optional


class EeroException(Exception):
    """Base exception for all Eero API errors."""

    def __init__(
        self,
        message: str = "An error occurred",
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize the exception.

        Args:
            message: Human-readable error message.
            envelope: The raw, unmodified JSON response envelope associated
                with the failure, when the response body was valid JSON.
                ``None`` when no response was received or the body was not
                JSON. Callers must not rewrite this value — it is retained
                verbatim from the API.
            error_code: The value of ``envelope["meta"]["error"]`` when
                present, or ``None``.
        """
        self.message = message
        self.envelope = envelope
        self.error_code = error_code
        super().__init__(message)

    def is_auth_error(self) -> bool:
        """Return True if this exception represents an authentication failure."""
        return False


class EeroAuthenticationException(EeroException):
    """Exception raised for authentication errors."""

    def is_auth_error(self) -> bool:
        """Always True — authentication exceptions are by definition auth errors."""
        return True


class EeroRateLimitException(EeroException):
    """Exception raised when rate limited by the API."""

    pass


class EeroNetworkException(EeroException):
    """Exception raised for network-related errors."""

    pass


class EeroAPIException(EeroException):
    """Exception raised for API errors."""

    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize the exception.

        Args:
            status_code: The HTTP status code returned by the API.
            message: Human-readable error message.
            envelope: The raw, unmodified JSON response envelope, or ``None``
                when the response body was not JSON.
            error_code: The value of ``envelope["meta"]["error"]`` when
                present, or ``None``.
        """
        self.status_code = status_code
        self.message = message
        super().__init__(
            f"API error {status_code}: {message}",
            envelope=envelope,
            error_code=error_code,
        )

    def is_auth_error(self) -> bool:
        """True when the HTTP status code is 401 (Unauthorized)."""
        return self.status_code == 401


class EeroTimeoutException(EeroException):
    """Exception raised when a request times out."""

    pass


class EeroNotFoundException(EeroException):
    """Exception raised when a resource is not found."""

    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} '{resource_id}' not found")


class EeroPremiumRequiredException(EeroException):
    """Exception raised when a feature requires Eero Plus subscription."""

    def __init__(self, feature: str = "This feature"):
        self.feature = feature
        super().__init__(f"{feature} requires an Eero Plus subscription")


class EeroFeatureUnavailableException(EeroException):
    """Exception raised when a feature is not available on the device."""

    def __init__(self, feature: str, reason: str = "not supported on this device"):
        self.feature = feature
        self.reason = reason
        super().__init__(f"{feature} is {reason}")


class EeroValidationException(EeroException):
    """Exception raised for validation errors."""

    def __init__(self, field: str, message: str):
        self.field = field
        super().__init__(f"Validation error for '{field}': {message}")
