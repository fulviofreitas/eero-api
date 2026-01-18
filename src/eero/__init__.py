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

__all__ = [
    "EeroAPI",
    "EeroClient",
    "EeroException",
    "EeroAPIException",
    "EeroAuthenticationException",
    "EeroNetworkException",
    "EeroRateLimitException",
    "EeroTimeoutException",
]

__version__ = "1.2.4"
