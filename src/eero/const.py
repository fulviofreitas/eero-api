"""Constants for the Eero API package."""

from enum import Enum
from typing import Final

# API Endpoints
API_HOST: Final[str] = "https://api-user.e2ro.com"
API_VERSION: Final[str] = "2.2"
API_ENDPOINT: Final[str] = f"{API_HOST}/{API_VERSION}"

# Device-mutation writes (pause/block/nickname/priority) are silently dropped on
# API version 2.2: the backend accepts the PUT and returns 200 OK but the change
# never persists server-side. Version 2.3 processes them correctly. Reads and
# other resources continue to use API_ENDPOINT (2.2). See issue #102.
DEVICE_UPDATE_ENDPOINT: Final[str] = f"{API_HOST}/2.3"
LOGIN_ENDPOINT: Final[str] = f"{API_ENDPOINT}/login"
LOGIN_VERIFY_ENDPOINT: Final[str] = f"{API_ENDPOINT}/login/verify"
LOGIN_RESEND_ENDPOINT: Final[str] = f"{LOGIN_ENDPOINT}/resend"
LOGIN_REFRESH_ENDPOINT: Final[str] = f"{API_ENDPOINT}/login/refresh"
LOGOUT_ENDPOINT: Final[str] = f"{API_ENDPOINT}/logout"
ACCOUNT_ENDPOINT: Final[str] = f"{API_ENDPOINT}/account"

# The logout endpoint expects a form body with a single field literally named
# "Cookie", whose value is the session-cookie-shaped string "s=<token>" -- not
# a JSON payload and not the actual HTTP Cookie header.
LOGOUT_COOKIE_FIELD_NAME: Final[str] = "Cookie"
SESSION_COOKIE_PREFIX: Final[str] = "s="

# Request headers
# Mobile-style User-Agent to reduce the chance of rate-limiting on cloud API
# endpoints that have been observed to treat non-mobile clients more aggressively.
DEFAULT_USER_AGENT: Final[str] = "eero/3.0 (iPhone; iOS 17.0)"

# Default value for the X-Accept-Language header sent on every request.
DEFAULT_ACCEPT_LANGUAGE: Final[str] = "en-US"

# Cache timeouts (in seconds)
CACHE_TIMEOUT: Final[int] = 60  # Default cache timeout

# Response body size limit — guards against unbounded memory consumption
MAX_RESPONSE_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MiB

# Fixed delay between bounded GET retries (transport errors / 5xx only).
GET_RETRY_DELAY_SECONDS: Final[float] = 0.5

# Version marker written to every persisted credential record (see
# api/auth_storage.py). A record loaded without this key predates the marker
# -- possibly carrying now-unsupported fields such as a legacy user_token,
# refresh_token, or session_expiry -- and is migrated in place on load.
CREDENTIAL_SCHEMA_VERSION: Final[int] = 2


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
