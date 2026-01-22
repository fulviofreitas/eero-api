"""Tests for DevicesAPI module.

Tests cover:
- Getting device list (raw response)
- Getting device details (raw response)
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
    async def test_get_devices_returns_raw_response(
        self, devices_api, mock_session, sample_devices_list
    ):
        """Test get_devices returns raw API response."""
        expected_response = api_success_response(sample_devices_list)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.get_devices("network_123")

        # Raw response should include meta and data
        assert "meta" in result
        assert "data" in result

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
    async def test_get_device_returns_raw_response(
        self, devices_api, mock_session, sample_device_data
    ):
        """Test get_device returns raw API response."""
        expected_response = api_success_response(sample_device_data)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.get_device("network_123", "device_abc")

        assert "meta" in result
        assert "data" in result
        assert result["data"]["mac"] == "AA:BB:CC:DD:EE:FF"
        assert result["data"]["nickname"] == "John's iPhone"

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
    async def test_set_nickname_returns_raw_response(self, devices_api, mock_session):
        """Test successful nickname change returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.set_device_nickname("network_123", "device_abc", "My Device")

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_nickname_sends_correct_payload(self, devices_api, mock_session):
        """Test that correct payload is sent for nickname change."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
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
    async def test_block_device_returns_raw_response(self, devices_api, mock_session):
        """Test successful device blocking returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.block_device("network_123", "device_abc", True)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_block_device_sends_correct_payload(self, devices_api, mock_session):
        """Test that correct payload is sent for blocking."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        await devices_api.block_device("network_123", "device_abc", True)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"blocked": True}


class TestDevicesAPIPauseDevice:
    """Tests for pause_device method."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_pause_device_returns_raw_response(self, devices_api, mock_session):
        """Test successful device pausing returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.pause_device("network_123", "device_abc", True)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_pause_device_sends_correct_payload(self, devices_api, mock_session):
        """Test that correct payload is sent for pausing."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        await devices_api.pause_device("network_123", "device_abc", True)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"paused": True}

    @pytest.mark.asyncio
    async def test_pause_device_not_authenticated(self, devices_api):
        """Test pause_device raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await devices_api.pause_device("network_123", "device_abc", True)



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
    async def test_set_device_priority_returns_raw_response(self, devices_api, mock_session):
        """Test enabling device priority returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.set_device_priority(
            "network_123", "device_abc", prioritized=True
        )

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_device_priority_with_duration(self, devices_api, mock_session):
        """Test enabling device priority with duration."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.set_device_priority(
            "network_123", "device_abc", prioritized=True, duration_minutes=120
        )

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["prioritized"] is True
        assert payload["priority_duration"] == 120

