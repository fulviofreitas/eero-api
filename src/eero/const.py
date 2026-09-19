"""Constants for the Eero API package."""

from enum import Enum
from typing import Final

# API Endpoints
API_HOST: Final[str] = "https://api-user.e2ro.com"


def api_endpoint(version: str) -> str:
    """Build the base endpoint URL for a given API version.

    This is the single place in the SDK that joins a version segment onto
    the API host. All version-scoped endpoint constants below are derived
    from this helper so there is exactly one URL-composition rule for
    "host + version".

    Args:
        version: The API version segment, e.g. ``"2.2"`` or ``"2.3"``.

    Returns:
        The base endpoint URL for that version, e.g.
        ``"https://api-user.e2ro.com/2.2"``.
    """
    return f"{API_HOST}/{version}"


# Default API version used by most families (networks, eeros, profiles,
# guest network, and the majority of resources).
API_VERSION_DEFAULT: Final[str] = "2.2"

# Device-mutation writes (pause/block/nickname/priority) are silently dropped on
# API version 2.2: the backend accepts the PUT and returns 200 OK but the change
# never persists server-side. Version 2.3 processes them correctly. Reads and
# other resources continue to use the default version (2.2). See issue #102.
API_VERSION_DEVICE_WRITES: Final[str] = "2.3"

# The multi-static-IP family is only served on 2.3.
API_VERSION_MULTISTATICIP: Final[str] = "2.3"

# Secondary WAN configuration (network-level and per-device) is only served
# on 2.3.
API_VERSION_SECONDARY_WAN: Final[str] = "2.3"

# API_VERSION is retained as an alias of API_VERSION_DEFAULT for backward
# compatibility with existing imports; new code should prefer the explicit,
# per-family constants above.
API_VERSION: Final[str] = API_VERSION_DEFAULT

API_ENDPOINT: Final[str] = api_endpoint(API_VERSION_DEFAULT)
DEVICE_UPDATE_ENDPOINT: Final[str] = api_endpoint(API_VERSION_DEVICE_WRITES)
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
