"""Shared fixtures for integration tests.

Provides fixtures for testing multi-component workflows
including mocked API servers and scenario builders.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def isolated_env(tmp_path):
    """Create an isolated environment for integration tests."""
    config_dir = tmp_path / ".eero"
    config_dir.mkdir()

    return {
        "config_dir": config_dir,
        "cookie_file": config_dir / "cookies.json",
        "config_file": config_dir / "config.yaml",
        "env": {"EERO_CONFIG_DIR": str(config_dir)},
    }


@pytest.fixture
def mock_aiohttp_session():
    """Create a mock aiohttp session for integration tests."""
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock()
    session.closed = False
    return session


@pytest.fixture
def sample_account_response():
    """Sample account API response."""
    return {
        "data": {
            "id": "user_12345",
            "email": {
                "address": "test@example.com",
                "verified": True,
            },
            "name": {"first": "Test", "last": "User"},
            "premium_status": "active",
        },
        "meta": {"code": 200},
    }


@pytest.fixture
def sample_networks_response():
    """Sample networks API response."""
    return {
        "data": [
            {
                "url": "/2.2/networks/network_001",
                "name": "Home Network",
                "status": "connected",
                "wan_ip": "203.0.113.42",
                "band_steering": True,
                "wpa3": True,
                "upnp": False,
                "thread": False,
                "sqm": True,
            },
            {
                "url": "/2.2/networks/network_002",
                "name": "Office Network",
                "status": "offline",
            },
        ],
        "meta": {"code": 200},
    }


@pytest.fixture
def sample_network_detail_response():
    """Sample network detail API response."""
    return {
        "data": {
            "url": "/2.2/networks/network_001",
            "name": "Home Network",
            "status": "connected",
            "wan_ip": "203.0.113.42",
            "gateway_ip": "192.168.4.1",
            "guest_network": {
                "enabled": True,
                "name": "Home Network Guest",
                "password": "guestpass123",
            },
            "dns_caching": True,
            "ipv6_upstream": False,
            "premium_status": "active",
        },
        "meta": {"code": 200},
    }


@pytest.fixture
def sample_eeros_response():
    """Sample eeros API response."""
    return {
        "data": [
            {
                "url": "/2.2/eeros/eero_001",
                "serial": "ABC123456789",
                "mac_address": "AA:BB:CC:DD:EE:FF",
                "model": "eero Pro 6E",
                "status": "green",
                "location": "Living Room",
                "gateway": True,
                "led_on": True,
                "led_brightness": 100,
                "connected_clients_count": 15,
            },
            {
                "url": "/2.2/eeros/eero_002",
                "serial": "DEF987654321",
                "mac_address": "11:22:33:44:55:66",
                "model": "eero Beacon",
                "status": "green",
                "location": "Bedroom",
                "gateway": False,
                "nightlight": {
                    "enabled": True,
                    "brightness": 75,
                },
            },
        ],
        "meta": {"code": 200},
    }


@pytest.fixture
def sample_devices_response():
    """Sample devices API response."""
    return {
        "data": [
            {
                "url": "/2.2/networks/network_001/devices/device_001",
                "mac": "AA:BB:CC:DD:EE:01",
                "hostname": "iPhone",
                "nickname": "John's iPhone",
                "ip": "192.168.4.101",
                "connected": True,
                "wireless": True,
                "manufacturer": "Apple Inc.",
            },
            {
                "url": "/2.2/networks/network_001/devices/device_002",
                "mac": "AA:BB:CC:DD:EE:02",
                "hostname": "MacBook",
                "ip": "192.168.4.102",
                "connected": True,
                "wireless": True,
                "manufacturer": "Apple Inc.",
            },
            {
                "url": "/2.2/networks/network_001/devices/device_003",
                "mac": "AA:BB:CC:DD:EE:03",
                "hostname": "Smart-TV",
                "ip": "192.168.4.103",
                "connected": True,
                "wireless": False,  # Wired device
                "manufacturer": "Samsung",
            },
        ],
        "meta": {"code": 200},
    }


@pytest.fixture
def sample_profiles_response():
    """Sample profiles API response."""
    return {
        "data": [
            {
                "url": "/2.2/networks/network_001/profiles/profile_001",
                "name": "Kids",
                "paused": False,
                "default": False,
                "state": {"value": "active"},
                "devices": [
                    {
                        "url": "/2.2/networks/network_001/devices/device_001",
                        "connected": True,
                        "wireless": True,
                    }
                ],
                "schedule": [],
                "proxied_nodes": [],
            },
            {
                "url": "/2.2/networks/network_001/profiles/profile_default",
                "name": "Default",
                "paused": False,
                "default": True,
                "state": {"value": "active"},
                "devices": [],
                "schedule": [],
                "proxied_nodes": [],
            },
        ],
        "meta": {"code": 200},
    }


@pytest.fixture
def mock_eero_api_server(
    mock_aiohttp_session,
    sample_account_response,
    sample_networks_response,
    sample_network_detail_response,
    sample_eeros_response,
    sample_devices_response,
    sample_profiles_response,
):
    """Create a mock API server that simulates the Eero API.

    This fixture can be used to test multi-step API workflows.
    """

    responses = {
        "account": sample_account_response,
        "networks": sample_networks_response,
        "network_detail": sample_network_detail_response,
        "eeros": sample_eeros_response,
        "devices": sample_devices_response,
        "profiles": sample_profiles_response,
        "success": {"meta": {"code": 200}},
    }

    def create_mock_response(response_type):
        response = MagicMock()
        data = responses.get(response_type, responses["success"])
        response.status = 200
        response.json = AsyncMock(return_value=data)
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock()
        return response

    return {
        "session": mock_aiohttp_session,
        "responses": responses,
        "create_response": create_mock_response,
    }
