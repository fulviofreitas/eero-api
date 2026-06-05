"""Constants for the Eero API package."""

from enum import Enum
from typing import Dict, Final

# API Endpoints
API_ENDPOINT: Final[str] = "https://api-user.e2ro.com/2.2"
LOGIN_ENDPOINT: Final[str] = f"{API_ENDPOINT}/login"
LOGIN_VERIFY_ENDPOINT: Final[str] = f"{API_ENDPOINT}/login/verify"
LOGOUT_ENDPOINT: Final[str] = f"{API_ENDPOINT}/logout"
ACCOUNT_ENDPOINT: Final[str] = f"{API_ENDPOINT}/account"

# The API has been observed to accept session-refresh requests at either of
# these paths.  Both are listed so the client can try them in order and remain
# functional regardless of which endpoint shape is active on the server.
LOGIN_REFRESH_ENDPOINT: Final[str] = f"{API_ENDPOINT}/login/refresh"
ACCOUNT_REFRESH_ENDPOINT: Final[str] = f"{API_ENDPOINT}/account/refresh"
REFRESH_ENDPOINTS: Final[tuple[str, ...]] = (LOGIN_REFRESH_ENDPOINT, ACCOUNT_REFRESH_ENDPOINT)

# Request headers
# Mobile-style User-Agent to reduce the chance of rate-limiting on cloud API
# endpoints that have been observed to treat non-mobile clients more aggressively.
DEFAULT_HEADERS: Final[Dict[str, str]] = {
    "User-Agent": "eero/3.0 (iPhone; iOS 17.0)",
    "Content-Type": "application/json",
}

# Cache timeouts (in seconds)
CACHE_TIMEOUT: Final[int] = 60  # Default cache timeout

# Response body size limit — guards against unbounded memory consumption
MAX_RESPONSE_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MiB

# Max characters of a response body to embed in error messages / logs.
# Caps log amplification when an upstream returns a hostile or oversized body.
MAX_ERROR_BODY_CHARS: Final[int] = 512

# Session keys
SESSION_TOKEN_KEY: Final[str] = "session_token"
REFRESH_TOKEN_KEY: Final[str] = "refresh_token"


class EeroDeviceType(str, Enum):
    """Enum for Eero device types."""

    GATEWAY = "gateway"
    BEACON = "beacon"
    EERO = "eero"
    BRIDGE = "bridge"
    UNKNOWN = "unknown"


class EeroNetworkStatus(str, Enum):
    """Enum for Eero network status."""

    ONLINE = "online"
    OFFLINE = "offline"
    UPDATING = "updating"
    UNKNOWN = "unknown"


class EeroDeviceStatus(str, Enum):
    """Enum for Eero device status."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"
