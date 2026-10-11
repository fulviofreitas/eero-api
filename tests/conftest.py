"""Shared pytest fixtures for the Eero CLI test suite.

This module provides reusable fixtures for testing:
- Mock EeroClient instances
- CLI context objects
- Mock network/device/eero data
- Rich console capturing
"""

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientSession
from click.testing import CliRunner
from rich.console import Console

from eero.const import CREDENTIAL_SCHEMA_VERSION

from .api.conftest import api_success_response, create_mock_response

# Import models and client (mocked in tests)
# These may not exist yet but tests will mock them


# ========================== Basic Fixtures ==========================


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click CliRunner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def isolated_runner(tmp_path: Path) -> CliRunner:
    """Create an isolated CliRunner with a temporary filesystem."""
    return CliRunner(
        env={
            "HOME": str(tmp_path),
            "XDG_CONFIG_HOME": str(tmp_path / ".config"),
        }
    )


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory."""
    config_dir = tmp_path / ".config" / "eero"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def mock_cookie_file(temp_config_dir: Path) -> Path:
    """Create a mock cookie file with valid session."""
    cookie_file = temp_config_dir / "cookies.json"
    cookie_file.write_text(
        json.dumps(
            {
                "session_id": "mock_session_id_67890",
                "refresh_token": None,
                "session_expiry": None,
            }
        )
    )
    return cookie_file


# ========================== Mock Data Fixtures ==========================


@dataclass
class MockNetwork:
    """Mock Network model for testing."""

    id: str = "net_12345"
    name: str = "Home Network"
    status: str = "connected"
    public_ip: str = "203.0.113.42"
    isp_name: str = "Test ISP"
    guest_network_enabled: bool = False
    guest_network_name: Optional[str] = "Guest Network"
    guest_network_password: Optional[str] = None
    speed_test: Optional[Dict[str, Any]] = None
    health: Optional[Dict[str, Any]] = None

    def model_dump(self, mode: str = "python") -> Dict[str, Any]:
        """Simulate Pydantic model_dump."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "public_ip": self.public_ip,
            "isp_name": self.isp_name,
            "guest_network_enabled": self.guest_network_enabled,
            "guest_network_name": self.guest_network_name,
            "guest_network_password": self.guest_network_password,
            "speed_test": self.speed_test,
            "health": self.health,
        }


@dataclass
class MockEero:
    """Mock Eero model for testing."""

    eero_id: str = "eero_abc123"
    serial: str = "A1B2C3D4E5"
    location: str = "Living Room"
    model: str = "eero Pro 6"
    status: str = "green"
    ip_address: str = "192.168.4.1"
    gateway: bool = True
    connection_type: str = "ethernet"

    def model_dump(self, mode: str = "python") -> Dict[str, Any]:
        """Simulate Pydantic model_dump."""
        return {
            "eero_id": self.eero_id,
            "serial": self.serial,
            "location": self.location,
            "model": self.model,
            "status": self.status,
            "ip_address": self.ip_address,
            "gateway": self.gateway,
            "connection_type": self.connection_type,
        }


@dataclass
class MockDevice:
    """Mock Device model for testing."""

    id: str = "device_xyz789"
    mac: str = "AA:BB:CC:DD:EE:FF"
    hostname: str = "test-device"
    display_name: str = "Test Device"
    nickname: Optional[str] = None
    ip: str = "192.168.4.100"
    ipv4: str = "192.168.4.100"
    status: str = "connected"
    connected: bool = True
    device_type: str = "computer"
    connection_type: str = "wireless"

    def model_dump(self, mode: str = "python") -> Dict[str, Any]:
        """Simulate Pydantic model_dump."""
        return {
            "id": self.id,
            "mac": self.mac,
            "hostname": self.hostname,
            "display_name": self.display_name,
            "nickname": self.nickname,
            "ip": self.ip,
            "ipv4": self.ipv4,
            "status": self.status,
            "connected": self.connected,
            "device_type": self.device_type,
            "connection_type": self.connection_type,
        }


@dataclass
class MockProfile:
    """Mock Profile model for testing."""

    id: str = "profile_kids"
    name: str = "Kids"
    paused: bool = False
    device_count: int = 3
    schedule_enabled: bool = False

    def model_dump(self, mode: str = "python") -> Dict[str, Any]:
        """Simulate Pydantic model_dump."""
        return {
            "id": self.id,
            "name": self.name,
            "paused": self.paused,
            "device_count": self.device_count,
            "schedule_enabled": self.schedule_enabled,
        }


@pytest.fixture
def mock_network() -> MockNetwork:
    """Create a mock network object."""
    return MockNetwork()


@pytest.fixture
def mock_networks() -> List[MockNetwork]:
    """Create a list of mock networks."""
    return [
        MockNetwork(id="net_1", name="Home Network", status="connected"),
        MockNetwork(id="net_2", name="Office Network", status="connected"),
    ]


@pytest.fixture
def mock_eeros() -> List[MockEero]:
    """Create a list of mock eero devices."""
    return [
        MockEero(
            eero_id="eero_1",
            location="Living Room",
            gateway=True,
            status="green",
        ),
        MockEero(
            eero_id="eero_2",
            location="Office",
            gateway=False,
            status="green",
            connection_type="wireless",
        ),
        MockEero(
            eero_id="eero_3",
            location="Bedroom",
            gateway=False,
            status="yellow",
            connection_type="wireless",
        ),
    ]


@pytest.fixture
def mock_devices() -> List[MockDevice]:
    """Create a list of mock client devices."""
    return [
        MockDevice(
            id="dev_1",
            display_name="iPhone",
            mac="AA:BB:CC:DD:EE:01",
            ip="192.168.4.101",
            connected=True,
        ),
        MockDevice(
            id="dev_2",
            display_name="MacBook Pro",
            mac="AA:BB:CC:DD:EE:02",
            ip="192.168.4.102",
            connected=True,
        ),
        MockDevice(
            id="dev_3",
            display_name="Smart TV",
            mac="AA:BB:CC:DD:EE:03",
            ip="192.168.4.103",
            connected=False,
        ),
    ]


@pytest.fixture
def mock_profiles() -> List[MockProfile]:
    """Create a list of mock profiles."""
    return [
        MockProfile(id="profile_1", name="Kids", device_count=3),
        MockProfile(id="profile_2", name="Parents", device_count=2),
    ]


# ========================== Mock Client Fixture ==========================


@pytest.fixture
def mock_eero_client(
    mock_network: MockNetwork,
    mock_networks: List[MockNetwork],
    mock_eeros: List[MockEero],
    mock_devices: List[MockDevice],
    mock_profiles: List[MockProfile],
):
    """Create a fully mocked EeroClient for testing.

    This fixture mocks the async context manager and all client methods.
    """
    client = AsyncMock()

    # Configure basic properties
    client.is_authenticated = True

    # Configure async methods
    client.get_networks = AsyncMock(return_value=mock_networks)
    client.get_network = AsyncMock(return_value=mock_network)
    client.get_eeros = AsyncMock(return_value=mock_eeros)
    client.get_eero = AsyncMock(return_value=mock_eeros[0])
    client.get_devices = AsyncMock(return_value=mock_devices)
    client.get_device = AsyncMock(return_value=mock_devices[0])
    client.get_profiles = AsyncMock(return_value=mock_profiles)
    client.get_profile = AsyncMock(return_value=mock_profiles[0])

    # Auth methods
    client.login = AsyncMock(return_value=True)
    client.verify = AsyncMock(return_value=True)
    client.logout = AsyncMock(return_value=True)

    # Mutation methods
    client.reboot_eero = AsyncMock(return_value=True)
    client.set_led = AsyncMock(return_value=True)
    client.set_led_brightness = AsyncMock(return_value=True)
    client.block_device = AsyncMock(return_value=True)
    client.set_device_nickname = AsyncMock(return_value=True)
    client.pause_profile = AsyncMock(return_value=True)
    client.set_network_name = AsyncMock(return_value=True)
    client.set_guest_network = AsyncMock(return_value=True)
    client.set_dns_mode = AsyncMock(return_value=True)
    client.set_dns_caching = AsyncMock(return_value=True)
    client.run_speed_test = AsyncMock(
        return_value={
            "down": {"value": 250},
            "up": {"value": 50},
            "latency": {"value": 15},
        }
    )

    # Settings methods
    client.get_dns_settings = AsyncMock(
        return_value={
            "dns_mode": "auto",
            "dns_caching": True,
            "custom_dns": [],
        }
    )
    client.get_security_settings = AsyncMock(
        return_value={
            "wpa3": True,
            "band_steering": True,
            "upnp": True,
            "ipv6_upstream": False,
            "thread": False,
        }
    )
    client.get_sqm_settings = AsyncMock(
        return_value={
            "enabled": True,
            "upload_bandwidth": 50,
            "download_bandwidth": 200,
        }
    )
    client.get_led_status = AsyncMock(
        return_value={
            "led_on": True,
            "led_brightness": 100,
        }
    )
    client.get_diagnostics = AsyncMock(
        return_value={
            "status": "healthy",
        }
    )
    client.get_updates = AsyncMock(
        return_value={
            "has_update": False,
            "target_firmware": "7.1.0",
        }
    )
    client.is_premium = AsyncMock(return_value=True)
    client.get_premium_status = AsyncMock(
        return_value={
            "plan": "eero Plus",
            "is_active": True,
        }
    )
    client.get_routing = AsyncMock(return_value={})
    client.get_thread = AsyncMock(return_value={})
    client.get_support = AsyncMock(return_value={})
    client.get_forwards = AsyncMock(return_value=[])
    client.get_reservations = AsyncMock(return_value=[])
    client.get_backup_network = AsyncMock(return_value={"enabled": False})
    client.get_backup_status = AsyncMock(return_value={})
    client.is_using_backup = AsyncMock(return_value=False)

    # Configure as async context manager
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=None)

    # Add internal API for auth tests
    client._api = MagicMock()
    client._api.auth = MagicMock()
    client._api.auth.clear_auth_data = AsyncMock()
    client._api.auth.resend_verification_code = AsyncMock()

    return client


@pytest.fixture
def patch_eero_client(mock_eero_client):
    """Patch EeroClient to return the mock client."""
    with patch("eero.cli.utils.EeroClient") as mock_class:
        # Configure the class to return our mock client
        mock_class.return_value = mock_eero_client
        # Also handle async context manager at class level
        mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_eero_client)
        mock_class.return_value.__aexit__ = AsyncMock(return_value=None)
        yield mock_class


# ========================== Console Fixtures ==========================


@pytest.fixture
def mock_console() -> MagicMock:
    """Create a mock Rich console for testing output."""
    console = MagicMock(spec=Console)
    console.print = MagicMock()
    console.status = MagicMock()
    console.status.return_value.__enter__ = MagicMock()
    console.status.return_value.__exit__ = MagicMock()
    return console


@pytest.fixture
def capture_console(capsys) -> Console:
    """Create a Console that captures output for assertions."""
    return Console(force_terminal=False, no_color=True, width=120)


# ========================== Exception Fixtures ==========================


@pytest.fixture
def auth_exception():
    """Create an authentication exception."""
    from eero.exceptions import EeroAuthenticationException

    return EeroAuthenticationException("Session expired")


@pytest.fixture
def not_found_exception():
    """Create a not found exception."""
    from eero.exceptions import EeroNotFoundException

    return EeroNotFoundException("Eero", "eero_xyz")


@pytest.fixture
def api_exception():
    """Create an API exception."""
    from eero.exceptions import EeroAPIException

    return EeroAPIException(500, "Internal server error")


@pytest.fixture
def premium_exception():
    """Create a premium required exception."""
    from eero.exceptions import EeroPremiumRequiredException

    return EeroPremiumRequiredException("Content filtering")


# ========================== API-layer Fixtures ==========================
# These live here, not in tests/api/conftest.py: pytest binds a conftest's fixtures to the
# one Directory node it was collected under, and listing a file directly under tests/
# between two tests/api files makes pytest rebuild that node, orphaning the fixtures
# (issue #175). The root conftest's node is never rebuilt.


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
    """A current-schema (v2) persisted credential record."""
    return {
        "session_id": "session_valid_id",
        "schema_version": CREDENTIAL_SCHEMA_VERSION,
    }


@pytest.fixture
def legacy_session_data() -> Dict[str, Any]:
    """A pre-schema-version (7.x or earlier) persisted credential record.

    Carries fields the current schema no longer supports (``refresh_token``,
    ``session_expiry``) and lacks the ``schema_version`` marker entirely,
    which is what triggers migration on load.
    """
    return {
        "session_id": "session_legacy_id",
        "refresh_token": "rt_legacy_refresh",
        "session_expiry": (datetime.now() - timedelta(days=1)).isoformat(),
    }


@pytest.fixture
def legacy_user_token_data() -> Dict[str, Any]:
    """A pre-schema-version record using the even older ``user_token`` key."""
    return {
        "user_token": "session_from_user_token",
        "session_expiry": (datetime.now() + timedelta(days=30)).isoformat(),
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
