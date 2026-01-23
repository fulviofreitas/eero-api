"""Shared fixtures for API tests.

This module provides reusable fixtures for testing the Eero API layer,
mocking HTTP responses and session management at the aiohttp boundary.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientResponseError, ClientSession

# ==================== Mock Response Helpers ====================


def create_mock_response(
    status: int = 200,
    json_data: Optional[Dict[str, Any]] = None,
    text: str = "",
    raise_for_status: bool = False,
) -> MagicMock:
    """Create a mock aiohttp response.

    Args:
        status: HTTP status code
        json_data: JSON response data
        text: Text response
        raise_for_status: Whether to raise on non-2xx status

    Returns:
        Mock response object
    """
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.text = AsyncMock(return_value=text or json.dumps(json_data or {}))
    mock_response.json = AsyncMock(return_value=json_data or {})

    if raise_for_status and status >= 400:
        mock_response.raise_for_status = MagicMock(
            side_effect=ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=status,
                message=text,
            )
        )
    else:
        mock_response.raise_for_status = MagicMock()

    # Make it work as an async context manager
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    return mock_response


def api_success_response(data: Any, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a standard Eero API success response structure.

    Args:
        data: Response data payload
        meta: Optional metadata (defaults to success)

    Returns:
        API response dictionary
    """
    return {
        "meta": meta or {"code": 200, "server_time": datetime.now().isoformat()},
        "data": data,
    }


def api_error_response(code: int, error: str, message: Optional[str] = None) -> Dict[str, Any]:
    """Create a standard Eero API error response structure.

    Args:
        code: Error code
        error: Error type string
        message: Optional error message

    Returns:
        API error response dictionary
    """
    return {
        "meta": {
            "code": code,
            "error": error,
            "message": message or error,
        }
    }


# ==================== Sample Data Fixtures ====================


@pytest.fixture
def sample_network_data() -> Dict[str, Any]:
    """Sample network data as returned by the API."""
    return {
        "id": "network_123",
        "url": "/2.2/networks/network_123",
        "name": "Home Network",
        "status": "connected",
        "wan_ip": "203.0.113.42",
        "timezone": "America/New_York",
        "geo_ip": {"isp": "Example ISP"},
        "ipv6_upstream": True,
        "band_steering": True,
        "thread": False,
        "upnp": True,
        "wpa3": True,
        "dns_caching": True,
        "guest_network": {
            "enabled": True,
            "name": "Guest Network",
            "password": "guest123",
        },
        "speed": {
            "down": {"value": 500.0, "units": "Mbps"},
            "up": {"value": 50.0, "units": "Mbps"},
        },
    }


@pytest.fixture
def sample_networks_list(sample_network_data) -> List[Dict[str, Any]]:
    """Sample list of networks."""
    return [
        sample_network_data,
        {
            "id": "network_456",
            "url": "/2.2/networks/network_456",
            "name": "Office Network",
            "status": "connected",
        },
    ]


@pytest.fixture
def sample_device_data() -> Dict[str, Any]:
    """Sample device data as returned by the API."""
    return {
        "url": "/2.2/networks/network_123/devices/device_abc",
        "mac": "AA:BB:CC:DD:EE:FF",
        "manufacturer": "Apple Inc.",
        "hostname": "iPhone",
        "nickname": "John's iPhone",
        "ip": "192.168.1.100",
        "connected": True,
        "blocked": False,
        "prioritized": False,
        "connection_type": "wireless",
        "source": {
            "location": "Living Room",
        },
    }


@pytest.fixture
def sample_devices_list(sample_device_data) -> List[Dict[str, Any]]:
    """Sample list of devices."""
    return [
        sample_device_data,
        {
            "url": "/2.2/networks/network_123/devices/device_def",
            "mac": "11:22:33:44:55:66",
            "manufacturer": "Samsung",
            "hostname": "Galaxy-S23",
            "nickname": None,
            "ip": "192.168.1.101",
            "connected": True,
            "blocked": False,
        },
    ]


@pytest.fixture
def sample_eero_data() -> Dict[str, Any]:
    """Sample eero device data."""
    return {
        "url": "/2.2/networks/network_123/eeros/eero_001",
        "serial": "ABC123456789",
        "model": "eero Pro 6E",
        "location": "Living Room",
        "led_on": True,
        "nightlight": {"enabled": False, "schedule": None},
        "status": "green",
        "gateway": True,
        "connected_clients_count": 15,
    }


@pytest.fixture
def sample_profile_data() -> Dict[str, Any]:
    """Sample profile data."""
    return {
        "url": "/2.2/networks/network_123/profiles/profile_001",
        "name": "Kids",
        "paused": False,
        "devices": [
            {"url": "/2.2/networks/network_123/devices/device_abc"},
        ],
        "block_illegal_content": True,
        "block_violent_content": False,
    }


@pytest.fixture
def sample_login_response() -> Dict[str, Any]:
    """Sample login response with user token."""
    return api_success_response({"user_token": "ut_login_token_12345"})


@pytest.fixture
def sample_verify_response(sample_network_data) -> Dict[str, Any]:
    """Sample verification response."""
    return api_success_response(
        {
            "user": {"id": "user_123", "email": "test@example.com"},
            "networks": {
                "data": [
                    {
                        "id": sample_network_data["id"],
                        "url": sample_network_data["url"],
                    }
                ]
            },
        }
    )


# ==================== Mock Session Fixtures ====================


@pytest.fixture
def mock_cookie_jar():
    """Create a mock cookie jar."""
    jar = MagicMock()
    jar.clear = MagicMock()
    jar.update_cookies = MagicMock()
    return jar


@pytest.fixture
def mock_session(mock_cookie_jar):
    """Create a mock aiohttp ClientSession.

    This is the primary fixture for mocking HTTP requests.
    Configure responses by setting mock_session.request.return_value.
    """
    session = MagicMock(spec=ClientSession)
    session.cookie_jar = mock_cookie_jar

    # Make request method return an async context manager
    session.request = MagicMock()

    # Default to successful empty response
    default_response = create_mock_response(200, api_success_response({}))
    session.request.return_value = default_response

    # Add convenience methods that delegate to request
    session.get = MagicMock(return_value=default_response)
    session.post = MagicMock(return_value=default_response)
    session.put = MagicMock(return_value=default_response)
    session.delete = MagicMock(return_value=default_response)

    # Async context manager support
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.close = AsyncMock()

    return session


@pytest.fixture
def mock_keyring():
    """Mock keyring module for secure storage tests."""
    with patch("eero.api.auth_storage.keyring") as mock:
        mock.get_password = MagicMock(return_value=None)
        mock.set_password = MagicMock()
        mock.delete_password = MagicMock()
        yield mock


# ==================== Auth State Fixtures ====================


@pytest.fixture
def valid_session_data() -> Dict[str, Any]:
    """Valid session data for authenticated state."""
    return {
        "session_id": "session_valid_id",
        "refresh_token": "rt_refresh_token",
        "preferred_network_id": "network_123",
        "session_expiry": (datetime.now() + timedelta(days=30)).isoformat(),
    }


@pytest.fixture
def expired_session_data() -> Dict[str, Any]:
    """Expired session data."""
    return {
        "session_id": "session_expired_id",
        "refresh_token": "rt_expired_refresh",
        "preferred_network_id": "network_123",
        "session_expiry": (datetime.now() - timedelta(days=1)).isoformat(),
    }


# ==================== Auth API Fixtures ====================


@pytest.fixture
def mock_auth_api(mock_session):
    """Create a mock AuthAPI for testing API modules.

    This fixture provides a mock AuthAPI that can be used with any
    AuthenticatedAPI subclass. Configure auth token by setting:
    mock_auth_api.get_auth_token = AsyncMock(return_value="token")
    """
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="test_auth_token")
    auth_api._base_url = "https://api.e.eero.com"
    return auth_api


@pytest.fixture
def mock_api_response():
    """Create a helper function for generating API responses.

    Returns a function that wraps data in the standard Eero API response format.
    """

    def _create_response(data: Any) -> Dict[str, Any]:
        return api_success_response(data)

    return _create_response
