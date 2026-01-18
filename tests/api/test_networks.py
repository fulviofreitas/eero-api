"""Tests for NetworksAPI module.

Tests cover:
- Getting network list
- Getting network details
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
    async def test_get_networks_success(self, networks_api, mock_session, sample_networks_list):
        """Test successful networks retrieval."""
        mock_response = create_mock_response(
            200, api_success_response({"networks": sample_networks_list})
        )
        mock_session.request.return_value = mock_response

        result = await networks_api.get_networks()

        assert len(result) == 2
        assert result[0]["id"] == "network_123"
        assert result[1]["id"] == "network_456"

    @pytest.mark.asyncio
    async def test_get_networks_old_format(self, networks_api, mock_session, sample_networks_list):
        """Test networks retrieval with old API format."""
        # Old format has data.data array
        mock_response = create_mock_response(
            200, api_success_response({"data": sample_networks_list})
        )
        mock_session.request.return_value = mock_response

        result = await networks_api.get_networks()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_networks_direct_array_format(
        self, networks_api, mock_session, sample_networks_list
    ):
        """Test networks retrieval with direct array format."""
        mock_response = create_mock_response(200, {"data": sample_networks_list, "meta": {}})
        mock_session.request.return_value = mock_response

        result = await networks_api.get_networks()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_networks_not_authenticated(self, networks_api):
        """Test get_networks raises when not authenticated."""
        networks_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await networks_api.get_networks()

    @pytest.mark.asyncio
    async def test_get_networks_empty_uses_preferred(
        self, networks_api, mock_session, sample_network_data
    ):
        """Test that empty networks list uses preferred network ID."""
        networks_api._auth_api.preferred_network_id = "network_123"

        # First call returns empty, second call (get_network) returns data
        empty_response = create_mock_response(200, api_success_response({}))
        network_response = create_mock_response(200, api_success_response(sample_network_data))

        mock_session.request.side_effect = [empty_response, network_response]

        result = await networks_api.get_networks()

        assert len(result) == 1
        assert result[0]["id"] == "network_123"


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
    async def test_get_network_success(self, networks_api, mock_session, sample_network_data):
        """Test successful network retrieval."""
        mock_response = create_mock_response(200, api_success_response(sample_network_data))
        mock_session.request.return_value = mock_response

        result = await networks_api.get_network("network_123")

        assert result["id"] == "network_123"
        assert result["name"] == "Home Network"

    @pytest.mark.asyncio
    async def test_get_network_extracts_public_ip(
        self, networks_api, mock_session, sample_network_data
    ):
        """Test that get_network extracts public IP from wan_ip."""
        mock_response = create_mock_response(200, api_success_response(sample_network_data))
        mock_session.request.return_value = mock_response

        result = await networks_api.get_network("network_123")

        assert result.get("public_ip") == "203.0.113.42"

    @pytest.mark.asyncio
    async def test_get_network_extracts_isp_name(
        self, networks_api, mock_session, sample_network_data
    ):
        """Test that get_network extracts ISP name from geo_ip."""
        mock_response = create_mock_response(200, api_success_response(sample_network_data))
        mock_session.request.return_value = mock_response

        result = await networks_api.get_network("network_123")

        assert result.get("isp_name") == "Example ISP"

    @pytest.mark.asyncio
    async def test_get_network_extracts_guest_network(
        self, networks_api, mock_session, sample_network_data
    ):
        """Test that get_network extracts guest network info."""
        mock_response = create_mock_response(200, api_success_response(sample_network_data))
        mock_session.request.return_value = mock_response

        result = await networks_api.get_network("network_123")

        assert result.get("guest_network_enabled") is True
        assert result.get("guest_network_name") == "Guest Network"

    @pytest.mark.asyncio
    async def test_get_network_not_found_returns_minimal(self, networks_api, mock_session):
        """Test that 404 returns minimal network data."""
        mock_response = create_mock_response(404, None, "Not found")
        mock_session.request.return_value = mock_response

        result = await networks_api.get_network("network_unknown")

        assert result["id"] == "network_unknown"
        assert result["status"] == "unknown"

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
    async def test_set_guest_network_enable(self, networks_api, mock_session):
        """Test enabling guest network."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await networks_api.set_guest_network("network_123", enabled=True)

        assert result is True

    @pytest.mark.asyncio
    async def test_set_guest_network_with_credentials(self, networks_api, mock_session):
        """Test setting guest network with name and password."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await networks_api.set_guest_network(
            "network_123",
            enabled=True,
            name="My Guest Network",
            password="securepass123",
        )

        assert result is True
        # Verify payload includes name and password
        call_args = mock_session.request.call_args
        assert "json" in call_args.kwargs
        payload = call_args.kwargs["json"]
        assert payload["enabled"] is True
        assert payload["name"] == "My Guest Network"
        assert payload["password"] == "securepass123"

    @pytest.mark.asyncio
    async def test_set_guest_network_disable(self, networks_api, mock_session):
        """Test disabling guest network."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await networks_api.set_guest_network("network_123", enabled=False)

        assert result is True


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
    async def test_run_speed_test(self, networks_api, mock_session):
        """Test running a speed test."""
        speed_data = {
            "down": {"value": 500.0, "units": "Mbps"},
            "up": {"value": 50.0, "units": "Mbps"},
        }
        mock_response = create_mock_response(200, api_success_response(speed_data))
        mock_session.request.return_value = mock_response

        result = await networks_api.run_speed_test("network_123")

        assert result["down"]["value"] == 500.0
        assert result["up"]["value"] == 50.0


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
    async def test_reboot_network_success(self, networks_api, mock_session):
        """Test successful network reboot."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await networks_api.reboot_network("network_123")

        assert result is True

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
    async def test_get_premium_status_active(self, networks_api, mock_session):
        """Test getting active premium status."""
        network_data = {
            "id": "network_123",
            "premium_status": {"active": True, "features": ["ad-block", "malware"]},
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await networks_api.get_premium_status("network_123")

        assert result["premium_enabled"] is True
        assert result["premium_status"] == "active"

    @pytest.mark.asyncio
    async def test_get_premium_status_inactive(self, networks_api, mock_session):
        """Test getting inactive premium status."""
        network_data = {"id": "network_123"}
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await networks_api.get_premium_status("network_123")

        assert result["premium_enabled"] is False
        assert result["premium_status"] == "inactive"

    @pytest.mark.asyncio
    async def test_is_premium_true(self, networks_api, mock_session):
        """Test is_premium returns True for active subscription."""
        network_data = {
            "id": "network_123",
            "premium_status": {"active": True},
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await networks_api.is_premium("network_123")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_premium_false(self, networks_api, mock_session):
        """Test is_premium returns False without subscription."""
        network_data = {"id": "network_123"}
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await networks_api.is_premium("network_123")

        assert result is False


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
    async def test_set_network_name_success(self, networks_api, mock_session):
        """Test successful network name change."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await networks_api.set_network_name("network_123", "New Network Name")

        assert result is True

    @pytest.mark.asyncio
    async def test_set_network_name_sends_correct_payload(self, networks_api, mock_session):
        """Test that correct payload is sent for name change."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        await networks_api.set_network_name("network_123", "My Network")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"name": "My Network"}
