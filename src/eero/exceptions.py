"""Exceptions for the Eero API package."""


class EeroException(Exception):
    """Base exception for all Eero API errors."""

    def __init__(self, message: str = "An error occurred"):
        self.message = message
        super().__init__(message)


class EeroAuthenticationException(EeroException):
    """Exception raised for authentication errors."""

    pass


class EeroRateLimitException(EeroException):
    """Exception raised when rate limited by the API."""

    pass


class EeroNetworkException(EeroException):
    """Exception raised for network-related errors."""

    pass


class EeroAPIException(EeroException):
    """Exception raised for API errors."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API error {status_code}: {message}")


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
