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


class EeroAccessDeniedException(EeroAPIException):
    """Exception raised when the API denies access to a resource (HTTP 403).

    Distinct from :class:`EeroAuthenticationException`: the caller is
    authenticated, but not permitted to perform the operation.
    ``is_auth_error()`` (inherited from :class:`EeroAPIException`) is False
    for this exception, since it is only ever raised for a 403.
    """

    pass


class EeroClientBlockedException(EeroAPIException):
    """Exception raised when the API rejects requests from this client version."""

    pass


class EeroNotFoundException(EeroException):
    """Exception raised when a resource is not found.

    Constructed either directly, with a known resource type and ID (the
    original, backward-compatible shape), or via :meth:`from_response` when
    the transport receives an HTTP 404 with no way to know the resource type
    or ID up front (for example a network-scoped path, or a 404 carrying a
    free-text sentence instead of a catalogue error string).
    """

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize the exception.

        Args:
            resource_type: The kind of resource that was not found (e.g.
                ``"network"``, ``"device"``).
            resource_id: The identifier that was looked up.
            envelope: The raw, unmodified response envelope, or ``None``.
            error_code: The value of ``envelope["meta"]["error"]``, or
                ``None``.
        """
        self.resource_type: Optional[str] = resource_type
        self.resource_id: Optional[str] = resource_id
        super().__init__(
            f"{resource_type} '{resource_id}' not found",
            envelope=envelope,
            error_code=error_code,
        )

    @classmethod
    def from_response(
        cls,
        message: str,
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ) -> "EeroNotFoundException":
        """Build a 404 exception when no resource type/ID is known up front.

        Args:
            message: A pre-built, human-readable message describing the 404.
            envelope: The raw, unmodified response envelope, or ``None``.
            error_code: The value of ``envelope["meta"]["error"]``, or
                ``None``.

        Returns:
            An :class:`EeroNotFoundException` with ``resource_type`` and
            ``resource_id`` set to ``None``.
        """
        instance = cls.__new__(cls)
        instance.resource_type = None
        instance.resource_id = None
        EeroException.__init__(instance, message, envelope=envelope, error_code=error_code)
        return instance


class EeroPremiumRequiredException(EeroException):
    """Exception raised when a feature requires Eero Plus subscription."""

    def __init__(
        self,
        feature: str = "This feature",
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize the exception.

        Args:
            feature: The name of the gated feature.
            envelope: The raw, unmodified response envelope, or ``None``.
            error_code: The value of ``envelope["meta"]["error"]``, or
                ``None``.
        """
        self.feature = feature
        super().__init__(
            f"{feature} requires an Eero Plus subscription",
            envelope=envelope,
            error_code=error_code,
        )

    @classmethod
    def from_response(
        cls,
        message: str,
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ) -> "EeroPremiumRequiredException":
        """Build a premium-required exception directly from an API response.

        Args:
            message: A pre-built, human-readable message from the transport.
            envelope: The raw, unmodified response envelope, or ``None``.
            error_code: The value of ``envelope["meta"]["error"]``, or
                ``None``.

        Returns:
            An :class:`EeroPremiumRequiredException` with ``feature`` set to
            the generic default, since the transport has no per-feature
            context at classification time.
        """
        instance = cls.__new__(cls)
        instance.feature = "This feature"
        EeroException.__init__(instance, message, envelope=envelope, error_code=error_code)
        return instance


class EeroFeatureUnavailableException(EeroException):
    """Exception raised when a feature is not available on the device."""

    def __init__(
        self,
        feature: str,
        reason: str = "not supported on this device",
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize the exception.

        Args:
            feature: The name of the unavailable feature.
            reason: A short explanation of why it is unavailable.
            envelope: The raw, unmodified response envelope, or ``None``.
            error_code: The value of ``envelope["meta"]["error"]``, or
                ``None``.
        """
        self.feature = feature
        self.reason = reason
        super().__init__(f"{feature} is {reason}", envelope=envelope, error_code=error_code)

    @classmethod
    def from_response(
        cls,
        message: str,
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ) -> "EeroFeatureUnavailableException":
        """Build a feature-unavailable exception directly from an API response.

        Args:
            message: A pre-built, human-readable message from the transport.
            envelope: The raw, unmodified response envelope, or ``None``.
            error_code: The value of ``envelope["meta"]["error"]``, or
                ``None``.

        Returns:
            An :class:`EeroFeatureUnavailableException` with ``feature`` and
            ``reason`` derived from ``error_code`` (or a generic fallback)
            since the transport has no per-feature context at classification
            time.
        """
        instance = cls.__new__(cls)
        instance.feature = error_code or "feature"
        instance.reason = message
        EeroException.__init__(instance, message, envelope=envelope, error_code=error_code)
        return instance


class EeroValidationException(EeroException):
    """Exception raised for validation errors.

    Constructed either directly, with a known field name (the original,
    client-side-validation shape used throughout the SDK), or via
    :meth:`from_response` for a validation error reported by the API itself.
    """

    def __init__(
        self,
        field: str,
        message: str,
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ):
        """Initialize the exception.

        Args:
            field: The name of the field that failed validation.
            message: A description of the validation failure.
            envelope: The raw, unmodified response envelope, or ``None``.
            error_code: The value of ``envelope["meta"]["error"]``, or
                ``None``.
        """
        self.field = field
        super().__init__(
            f"Validation error for '{field}': {message}",
            envelope=envelope,
            error_code=error_code,
        )

    @classmethod
    def from_response(
        cls,
        message: str,
        *,
        envelope: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ) -> "EeroValidationException":
        """Build a validation exception directly from an API response.

        Args:
            message: A pre-built, human-readable message from the transport.
            envelope: The raw, unmodified response envelope, or ``None``.
            error_code: The value of ``envelope["meta"]["error"]``, or
                ``None``.

        Returns:
            An :class:`EeroValidationException` with ``field`` set to
            ``"request"``, since the transport has no per-field context at
            classification time.
        """
        instance = cls.__new__(cls)
        instance.field = "request"
        EeroException.__init__(instance, message, envelope=envelope, error_code=error_code)
        return instance
