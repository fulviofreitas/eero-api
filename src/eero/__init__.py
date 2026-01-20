"""Eero API - Async Python client for Eero mesh WiFi networks."""

from .api import EeroAPI
from .client import EeroClient
from .exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroException,
    EeroNetworkException,
    EeroRateLimitException,
    EeroTimeoutException,
)
from .logging import SecureLoggerAdapter, get_secure_logger, redact_sensitive

__all__ = [
    "EeroAPI",
    "EeroClient",
    "EeroException",
    "EeroAPIException",
    "EeroAuthenticationException",
    "EeroNetworkException",
    "EeroRateLimitException",
    "EeroTimeoutException",
    # Secure logging utilities
    "get_secure_logger",
    "SecureLoggerAdapter",
    "redact_sensitive",
]

__version__ = "1.4.2"
