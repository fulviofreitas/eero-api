"""Tests for DevicesAPI module.

Tests cover:
- Getting device list
- Getting device details
- Setting device nickname
- Blocking/unblocking devices
- Device priority management
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.devices import DevicesAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestDevicesAPIInit:
    """Tests for DevicesAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = DevicesAPI(auth_api)

        assert api._auth_api is auth_api


class TestDevicesAPIGetDevices:
    """Tests for get_devices method."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_devices_success(self, devices_api, mock_session, sample_devices_list):
        """Test successful devices retrieval."""
        mock_response = create_mock_response(
            200, api_success_response({"data": sample_devices_list})
        )
        mock_session.request.return_value = mock_response

        result = await devices_api.get_devices("network_123")

        assert len(result) == 2
        assert result[0]["mac"] == "AA:BB:CC:DD:EE:FF"
        assert result[1]["mac"] == "11:22:33:44:55:66"

    @pytest.mark.asyncio
    async def test_get_devices_direct_list_format(
        self, devices_api, mock_session, sample_devices_list
    ):
        """Test devices retrieval with direct list format."""
        mock_response = create_mock_response(200, {"data": sample_devices_list, "meta": {}})
        mock_session.request.return_value = mock_response

        result = await devices_api.get_devices("network_123")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_devices_empty_list(self, devices_api, mock_session):
        """Test devices retrieval with empty list."""
        mock_response = create_mock_response(200, api_success_response([]))
        mock_session.request.return_value = mock_response

        result = await devices_api.get_devices("network_123")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_devices_not_authenticated(self, devices_api):
        """Test get_devices raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await devices_api.get_devices("network_123")


class TestDevicesAPIGetDevice:
    """Tests for get_device method."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_device_success(self, devices_api, mock_session, sample_device_data):
        """Test successful device retrieval."""
        mock_response = create_mock_response(200, api_success_response(sample_device_data))
        mock_session.request.return_value = mock_response

        result = await devices_api.get_device("network_123", "device_abc")

        assert result["mac"] == "AA:BB:CC:DD:EE:FF"
        assert result["nickname"] == "John's iPhone"

    @pytest.mark.asyncio
    async def test_get_device_not_authenticated(self, devices_api):
        """Test get_device raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await devices_api.get_device("network_123", "device_abc")


class TestDevicesAPISetNickname:
    """Tests for set_device_nickname method."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_nickname_success(self, devices_api, mock_session):
        """Test successful nickname change."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await devices_api.set_device_nickname("network_123", "device_abc", "My Device")

        assert result is True

    @pytest.mark.asyncio
    async def test_set_nickname_sends_correct_payload(self, devices_api, mock_session):
        """Test that correct payload is sent for nickname change."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        await devices_api.set_device_nickname("network_123", "device_abc", "New Name")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"nickname": "New Name"}

    @pytest.mark.asyncio
    async def test_set_nickname_not_authenticated(self, devices_api):
        """Test set_device_nickname raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await devices_api.set_device_nickname("network_123", "device_abc", "New Name")


class TestDevicesAPIBlockDevice:
    """Tests for block_device method."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_block_device_success(self, devices_api, mock_session):
        """Test successful device blocking."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await devices_api.block_device("network_123", "device_abc", True)

        assert result is True

    @pytest.mark.asyncio
    async def test_unblock_device_success(self, devices_api, mock_session):
        """Test successful device unblocking."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await devices_api.block_device("network_123", "device_abc", False)

        assert result is True

    @pytest.mark.asyncio
    async def test_block_device_sends_correct_payload(self, devices_api, mock_session):
        """Test that correct payload is sent for blocking."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        await devices_api.block_device("network_123", "device_abc", True)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"blocked": True}


class TestDevicesAPIPriority:
    """Tests for device priority management."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_device_priority(self, devices_api, mock_session):
        """Test getting device priority settings."""
        device_data = {
            "mac": "AA:BB:CC:DD:EE:FF",
            "prioritized": True,
            "priority": True,
            "priority_duration": 60,
            "priority_expires_at": "2024-01-01T12:00:00Z",
        }
        mock_response = create_mock_response(200, api_success_response(device_data))
        mock_session.request.return_value = mock_response

        result = await devices_api.get_device_priority("network_123", "device_abc")

        assert result["prioritized"] is True
        assert result["duration"] == 60
        assert result["expires_at"] == "2024-01-01T12:00:00Z"

    @pytest.mark.asyncio
    async def test_set_device_priority_enable(self, devices_api, mock_session):
        """Test enabling device priority."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await devices_api.set_device_priority(
            "network_123", "device_abc", prioritized=True
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_set_device_priority_with_duration(self, devices_api, mock_session):
        """Test enabling device priority with duration."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await devices_api.set_device_priority(
            "network_123", "device_abc", prioritized=True, duration_minutes=120
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["prioritized"] is True
        assert payload["priority_duration"] == 120

    @pytest.mark.asyncio
    async def test_set_device_priority_disable(self, devices_api, mock_session):
        """Test disabling device priority."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await devices_api.set_device_priority(
            "network_123", "device_abc", prioritized=False
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_prioritize_device_convenience(self, devices_api, mock_session):
        """Test prioritize_device convenience method."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await devices_api.prioritize_device("network_123", "device_abc", 60)

        assert result is True

    @pytest.mark.asyncio
    async def test_deprioritize_device_convenience(self, devices_api, mock_session):
        """Test deprioritize_device convenience method."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await devices_api.deprioritize_device("network_123", "device_abc")

        assert result is True

    @pytest.mark.asyncio
    async def test_get_prioritized_devices(self, devices_api, mock_session, sample_devices_list):
        """Test getting list of prioritized devices."""
        # Add priority to first device
        devices = sample_devices_list.copy()
        devices[0]["prioritized"] = True
        devices[1]["prioritized"] = False

        mock_response = create_mock_response(200, api_success_response({"data": devices}))
        mock_session.request.return_value = mock_response

        result = await devices_api.get_prioritized_devices("network_123")

        assert len(result) == 1
        assert result[0]["mac"] == "AA:BB:CC:DD:EE:FF"

    @pytest.mark.asyncio
    async def test_get_prioritized_devices_empty(self, devices_api, mock_session):
        """Test getting prioritized devices when none are prioritized."""
        devices = [
            {"mac": "AA:BB:CC:DD:EE:FF", "prioritized": False},
            {"mac": "11:22:33:44:55:66", "prioritized": False},
        ]
        mock_response = create_mock_response(200, api_success_response({"data": devices}))
        mock_session.request.return_value = mock_response

        result = await devices_api.get_prioritized_devices("network_123")

        assert result == []
