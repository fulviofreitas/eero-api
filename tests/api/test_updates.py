"""Tests for UpdatesAPI module.

Tests cover:
- Getting update information (raw response, via the updates link)
- Applying a pending update (empty-string body, reboot-class warning)
- id/path/URL polymorphism and parent-link preference
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.updates import UpdatesAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def updates_api(mock_session):
    """Create an UpdatesAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return UpdatesAPI(auth_api)


class TestUpdatesAPIInit:
    """Tests for UpdatesAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = UpdatesAPI(auth_api)

        assert api._auth_api is auth_api


class TestUpdatesAPIGetUpdates:
    """Tests for get_updates method."""

    @pytest.mark.asyncio
    async def test_get_updates_uses_default_template(self, updates_api, mock_session):
        """Test get_updates GETs the updates link built from the template."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"available": False})
        )

        result = await updates_api.get_updates("network_123")

        assert result["data"]["available"] is False
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/updates")

    @pytest.mark.asyncio
    async def test_get_updates_prefers_parent_link(self, updates_api, mock_session):
        """Test get_updates uses the network's published updates link."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"available": False})
        )
        parent = {"resources": {"updates": "/2.3/networks/network_123/updates"}}

        await updates_api.get_updates("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/updates")

    @pytest.mark.asyncio
    async def test_get_updates_not_authenticated(self, updates_api):
        """Test get_updates raises when not authenticated."""
        updates_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await updates_api.get_updates("network_123")


class TestUpdatesAPIApplyUpdate:
    """Tests for apply_update method."""

    @pytest.mark.asyncio
    async def test_apply_update_posts_empty_json_string(self, updates_api, mock_session, caplog):
        """Test apply_update POSTs the two-byte "" body and warns it reboots every node."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await updates_api.apply_update("network_123")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/networks/network_123/updates")
        assert call_args.kwargs["data"] == '""'
        assert any(
            "apply update for network" in m and "reboots every node" in m for m in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_apply_update_not_authenticated(self, updates_api):
        """Test apply_update raises when not authenticated."""
        updates_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await updates_api.apply_update("network_123")
