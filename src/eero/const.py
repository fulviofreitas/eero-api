"""Constants for the Eero API package."""

from enum import Enum
from typing import Dict, Final

# API Endpoints
API_ENDPOINT: Final[str] = "https://api-user.e2ro.com/2.2"
LOGIN_ENDPOINT: Final[str] = f"{API_ENDPOINT}/login"
LOGIN_VERIFY_ENDPOINT: Final[str] = f"{API_ENDPOINT}/login/verify"
LOGOUT_ENDPOINT: Final[str] = f"{API_ENDPOINT}/logout"
ACCOUNT_ENDPOINT: Final[str] = f"{API_ENDPOINT}/account"

# Request headers
DEFAULT_HEADERS: Final[Dict[str, str]] = {
    "User-Agent": "eero-api/1.0.0",
    "Content-Type": "application/json",
}

# Cache timeouts (in seconds)
CACHE_TIMEOUT: Final[int] = 60  # Default cache timeout

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
