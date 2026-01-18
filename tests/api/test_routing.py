"""Unit tests for the RoutingAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.routing import RoutingAPI
from eero.exceptions import EeroAuthenticationException


class TestRoutingAPIInitialization:
    """Tests for RoutingAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test RoutingAPI initializes with auth API."""
        api = RoutingAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetRouting:
    """Tests for get_routing method."""

    async def test_get_routing_success(self, mock_auth_api, mock_api_response):
        """Test successful routing retrieval."""
        api = RoutingAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        routing_data = {
            "mode": "bridge",
            "gateway_ip": "192.168.1.1",
            "subnet_mask": "255.255.255.0",
            "dhcp_enabled": True,
            "double_nat_detected": False,
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(routing_data)
            result = await api.get_routing("network123")

            assert result == routing_data
            mock_get.assert_called_once_with(
                "networks/network123/routing",
                auth_token="test_token",
            )

    async def test_get_routing_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_routing returns empty dict for missing data."""
        api = RoutingAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_routing("network123")

            assert result == {}

    async def test_get_routing_not_authenticated(self, mock_auth_api):
        """Test get_routing raises exception when not authenticated."""
        api = RoutingAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_routing("network123")


class TestUpdateRouting:
    """Tests for update_routing method."""

    async def test_update_routing_success(self, mock_auth_api, mock_api_response):
        """Test successful routing update."""
        api = RoutingAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        routing_config = {
            "mode": "router",
            "dhcp_enabled": True,
        }

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_routing("network123", routing_config)

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/routing",
                auth_token="test_token",
                json=routing_config,
            )

    async def test_update_routing_change_mode(self, mock_auth_api, mock_api_response):
        """Test routing update to change mode."""
        api = RoutingAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        routing_config = {"mode": "bridge"}

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_routing("network123", routing_config)

            assert result is True

    async def test_update_routing_failure(self, mock_auth_api, mock_api_response):
        """Test update_routing returns false on failure."""
        api = RoutingAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 400}}
            result = await api.update_routing("network123", {})

            assert result is False

    async def test_update_routing_not_authenticated(self, mock_auth_api):
        """Test update_routing raises exception when not authenticated."""
        api = RoutingAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.update_routing("network123", {})
