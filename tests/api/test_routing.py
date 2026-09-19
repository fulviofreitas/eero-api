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

    @pytest.mark.asyncio
    async def test_get_routing_builds_default_version_template_url(self, routing_api, mock_session):
        """Test the template fallback stays on the default (2.2) API version."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await routing_api.get_routing("network_123")

        _, url = mock_session.request.call_args.args[:2]
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123/routing"

    @pytest.mark.asyncio
    async def test_get_routing_prefers_parent_routing_link(self, routing_api, mock_session):
        """Test the network's routing link (served on 2.3) is preferred over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {
            "url": "/2.2/networks/network_123",
            "resources": {"routing": "/2.3/networks/network_123/routing"},
        }

        await routing_api.get_routing("network_123", parent=parent)

        _, url = mock_session.request.call_args.args[:2]
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/routing"
