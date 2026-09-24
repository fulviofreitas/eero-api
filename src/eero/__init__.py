"""Eero API - Async Python client for Eero mesh WiFi networks."""

from .api import EeroAPI
from .api.base import id_from_url
from .api.links import join_api_path, resolve_link, resource_url, self_url, sub_resource_url
from .client import EeroClient
from .errors import ErrorGroup, classify_error_code, exception_for_error
from .exceptions import (
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
from .logging import SecureLoggerAdapter, get_secure_logger, redact_sensitive

__all__ = [
    "EeroAPI",
    "EeroClient",
    "EeroException",
    "EeroAccessDeniedException",
    "EeroAPIException",
    "EeroAuthenticationException",
    "EeroClientBlockedException",
    "EeroFeatureUnavailableException",
    "EeroNetworkException",
    "EeroNotFoundException",
    "EeroPremiumRequiredException",
    "EeroRateLimitException",
    "EeroTimeoutException",
    "EeroValidationException",
    # Error catalogue
    "ErrorGroup",
    "classify_error_code",
    "exception_for_error",
    # URL / ID utilities
    "id_from_url",
    "join_api_path",
    "resolve_link",
    "resource_url",
    "self_url",
    "sub_resource_url",
    # Secure logging utilities
    "get_secure_logger",
    "SecureLoggerAdapter",
    "redact_sensitive",
]

__version__ = "8.0.4"
