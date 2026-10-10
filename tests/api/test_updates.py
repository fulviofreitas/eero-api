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
from eero.exceptions import EeroAuthenticationException, EeroValidationException

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


class TestUpdatesAPISetPreferredUpdateHour:
    """Tests for set_preferred_update_hour method."""

    @pytest.mark.asyncio
    async def test_posts_hour(self, updates_api, mock_session):
        """Test the verb, path, and JSON body."""
        envelope = api_success_response({})
        mock_session.request.return_value = create_mock_response(200, envelope)

        result = await updates_api.set_preferred_update_hour("network_123", 3)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/networks/network_123/updates/preferred_update_hour")
        assert call_args.kwargs["json"] == {"preferred_update_hour": 3}
        assert result == envelope

    @pytest.mark.asyncio
    async def test_accepts_network_path(self, updates_api, mock_session):
        """Test an API-returned network path is not doubled."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await updates_api.set_preferred_update_hour("/2.2/networks/network_123", 0)

        assert mock_session.request.call_args.args[1].endswith(
            "/2.2/networks/network_123/updates/preferred_update_hour"
        )

    @pytest.mark.asyncio
    async def test_warns_before_write(self, updates_api, mock_session, caplog):
        """Test the uncharacterised-write warning is logged."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await updates_api.set_preferred_update_hour("network_123", 23)

        assert any(r.levelno == logging.WARNING for r in caplog.records)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("hour", [-1, 24, True, "3", 3.0, None])
    async def test_rejects_invalid_hour(self, updates_api, mock_session, hour):
        """Test out-of-range or non-int hours raise before any request."""
        with pytest.raises(EeroValidationException):
            await updates_api.set_preferred_update_hour("network_123", hour)
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_authenticated(self, updates_api, mock_session):
        """Test it raises before any request when there is no token."""
        updates_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await updates_api.set_preferred_update_hour("network_123", 3)
        mock_session.request.assert_not_called()
