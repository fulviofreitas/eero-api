"""Tests for RoutingAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.routing import RoutingAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestRoutingAPIInit:
    """Tests for RoutingAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = RoutingAPI(auth_api)
        assert api._auth_api is auth_api


class TestRoutingAPIGetRouting:
    """Tests for get_routing method."""

    @pytest.fixture
    def routing_api(self, mock_session):
        """Create a RoutingAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return RoutingAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_routing_returns_raw_response(self, routing_api, mock_session):
        """Test get_routing returns raw response."""
        routing_data = {"routes": [], "mode": "automatic"}
        mock_response = create_mock_response(200, api_success_response(routing_data))
        mock_session.request.return_value = mock_response

        result = await routing_api.get_routing("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_routing_not_authenticated(self, routing_api):
        """Test get_routing raises when not authenticated."""
        routing_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await routing_api.get_routing("network_123")
