"""Tests for NetworksAPI module.

Tests cover:
- Getting network list (raw response)
- Getting network details (raw response)
- Setting guest network
- Running speed tests
- Rebooting network
- Premium status checking
- Setting network name
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.networks import NetworksAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestNetworksAPIInit:
    """Tests for NetworksAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = NetworksAPI(auth_api)

        assert api._auth_api is auth_api


class TestNetworksAPIGetNetworks:
    """Tests for get_networks method."""

    @pytest.fixture
    def networks_api(self, mock_session):
        """Create a NetworksAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        auth_api.preferred_network_id = None
        api = NetworksAPI(auth_api)
        return api

    @pytest.mark.asyncio
    async def test_get_networks_returns_raw_response(
        self, networks_api, mock_session, sample_networks_list
    ):
        """Test get_networks returns raw API response."""
        expected_response = api_success_response({"networks": sample_networks_list})
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await networks_api.get_networks()

        # Raw response should include meta and data
        assert "meta" in result
        assert "data" in result
        assert result["data"]["networks"] == sample_networks_list

    @pytest.mark.asyncio
    async def test_get_networks_not_authenticated(self, networks_api):
        """Test get_networks raises when not authenticated."""
        networks_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await networks_api.get_networks()


class TestNetworksAPIGetNetwork:
    """Tests for get_network method."""

    @pytest.fixture
    def networks_api(self, mock_session):
        """Create a NetworksAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return NetworksAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_network_returns_raw_response(
        self, networks_api, mock_session, sample_network_data
    ):
        """Test get_network returns raw API response."""
        expected_response = api_success_response(sample_network_data)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await networks_api.get_network("network_123")

        # Raw response should include meta and data
        assert "meta" in result
        assert "data" in result
        assert result["data"]["id"] == "network_123"
        assert result["data"]["name"] == "Home Network"
        # Original field names are preserved (no transformation)
        assert result["data"]["wan_ip"] == "203.0.113.42"
        assert result["data"]["geo_ip"]["isp"] == "Example ISP"

    @pytest.mark.asyncio
    async def test_get_network_not_authenticated(self, networks_api):
        """Test get_network raises when not authenticated."""
        networks_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await networks_api.get_network("network_123")


class TestNetworksAPIGuestNetwork:
    """Tests for guest network management."""

    @pytest.fixture
    def networks_api(self, mock_session):
        """Create a NetworksAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return NetworksAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_guest_network_returns_raw_response(self, networks_api, mock_session):
        """Test enabling guest network returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await networks_api.set_guest_network("network_123", enabled=True)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_guest_network_with_credentials(self, networks_api, mock_session):
        """Test setting guest network with name and password."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await networks_api.set_guest_network(
            "network_123",
            enabled=True,
            name="My Guest Network",
            password="securepass123",
        )

        assert "meta" in result
        # Verify payload includes name and password
        call_args = mock_session.request.call_args
        assert "json" in call_args.kwargs
        payload = call_args.kwargs["json"]
        assert payload["enabled"] is True
        assert payload["name"] == "My Guest Network"
        assert payload["password"] == "securepass123"


class TestNetworksAPISpeedTest:
    """Tests for speed test functionality."""

    @pytest.fixture
    def networks_api(self, mock_session):
        """Create a NetworksAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return NetworksAPI(auth_api)

    @pytest.mark.asyncio
    async def test_run_speed_test_returns_raw_response(self, networks_api, mock_session):
        """Test running a speed test returns raw response."""
        speed_data = {
            "down": {"value": 500.0, "units": "Mbps"},
            "up": {"value": 50.0, "units": "Mbps"},
        }
        expected_response = api_success_response(speed_data)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await networks_api.run_speed_test("network_123")

        assert "meta" in result
        assert "data" in result
        assert result["data"]["down"]["value"] == 500.0
        assert result["data"]["up"]["value"] == 50.0


class TestNetworksAPIReboot:
    """Tests for network reboot functionality."""

    @pytest.fixture
    def networks_api(self, mock_session):
        """Create a NetworksAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return NetworksAPI(auth_api)

    @pytest.mark.asyncio
    async def test_reboot_network_returns_raw_response(self, networks_api, mock_session):
        """Test successful network reboot returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await networks_api.reboot_network("network_123")

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_reboot_network_not_authenticated(self, networks_api):
        """Test reboot raises when not authenticated."""
        networks_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await networks_api.reboot_network("network_123")


class TestNetworksAPIPremium:
    """Tests for premium status checking."""

    @pytest.fixture
    def networks_api(self, mock_session):
        """Create a NetworksAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return NetworksAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_premium_status_returns_raw_response(self, networks_api, mock_session):
        """Test getting premium status returns raw response."""
        network_data = {
            "id": "network_123",
            "premium_status": {"active": True, "features": ["ad-block", "malware"]},
        }
        expected_response = api_success_response(network_data)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await networks_api.get_premium_status("network_123")

        assert "meta" in result
        assert "data" in result
        # Raw response includes the original premium_status field
        assert result["data"]["premium_status"]["active"] is True


class TestNetworksAPISetName:
    """Tests for setting network name."""

    @pytest.fixture
    def networks_api(self, mock_session):
        """Create a NetworksAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return NetworksAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_network_name_returns_raw_response(self, networks_api, mock_session):
        """Test successful network name change returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await networks_api.set_network_name("network_123", "New Network Name")

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_network_name_sends_correct_payload(self, networks_api, mock_session):
        """Test that correct payload is sent for name change."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        await networks_api.set_network_name("network_123", "My Network")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"name": "My Network"}
