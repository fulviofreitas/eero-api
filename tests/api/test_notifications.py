"""Tests for NotificationsAPI module.

Tests cover:
- Reading notification settings, unread state, and history (raw responses)
- Setting notification settings and account push settings (JSON writes)
- Marking notifications read (empty-string-body POST)
- The uncharacterised-write warning on every unverified write
- Parent-link (network self-url) preference for one method
- Not-authenticated handling on every network-scoped method
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.notifications import NotificationsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def notifications_api(mock_session):
    """Create a NotificationsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return NotificationsAPI(auth_api)


class TestNotificationsAPIInit:
    """Tests for NotificationsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = NotificationsAPI(auth_api)

        assert api._auth_api is auth_api


class TestNotificationsAPIGetSettings:
    """Tests for get_settings method."""

    @pytest.mark.asyncio
    async def test_get_settings_returns_raw_response(self, notifications_api, mock_session):
        """Test get_settings GETs the notifications path."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"network.updated": True})
        )

        result = await notifications_api.get_settings("network_123")

        assert result["data"]["network.updated"] is True
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/notifications")

    @pytest.mark.asyncio
    async def test_get_settings_prefers_parent_self_url(self, notifications_api, mock_session):
        """Test get_settings uses the parent's own url over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"url": "/2.3/networks/network_123"}

        await notifications_api.get_settings("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/notifications")

    @pytest.mark.asyncio
    async def test_get_settings_not_authenticated(self, notifications_api):
        """Test get_settings raises when not authenticated."""
        notifications_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await notifications_api.get_settings("network_123")


class TestNotificationsAPISetSettings:
    """Tests for set_settings method."""

    @pytest.mark.asyncio
    async def test_set_settings_sends_json_payload_and_warns(
        self, notifications_api, mock_session, caplog
    ):
        """Test set_settings PUTs the caller's mapping as JSON and warns."""
        import logging

        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        settings = {"network.updated": False, "permissions.updates": True}

        with caplog.at_level(logging.WARNING):
            result = await notifications_api.set_settings("network_123", settings)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/notifications")
        assert call_args.kwargs["json"] == settings
        assert any("set notification settings for network" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_settings_not_authenticated(self, notifications_api):
        """Test set_settings raises when not authenticated."""
        notifications_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await notifications_api.set_settings("network_123", {"network.updated": True})


class TestNotificationsAPIHasUnread:
    """Tests for has_unread method."""

    @pytest.mark.asyncio
    async def test_has_unread_returns_raw_response(self, notifications_api, mock_session):
        """Test has_unread GETs the notifications/has_unread path."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"has_unread": True})
        )

        result = await notifications_api.has_unread("network_123")

        assert result["data"]["has_unread"] is True
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/notifications/has_unread")

    @pytest.mark.asyncio
    async def test_has_unread_not_authenticated(self, notifications_api):
        """Test has_unread raises when not authenticated."""
        notifications_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await notifications_api.has_unread("network_123")


class TestNotificationsAPIMarkRead:
    """Tests for mark_read method."""

    @pytest.mark.asyncio
    async def test_mark_read_posts_empty_json_string_and_warns(
        self, notifications_api, mock_session, caplog
    ):
        """Test mark_read POSTs the two-byte "" body and warns."""
        import logging

        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await notifications_api.mark_read("network_123")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/networks/network_123/notifications/mark_read")
        assert call_args.kwargs["data"] == '""'
        assert any("mark notifications read for network" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_mark_read_not_authenticated(self, notifications_api):
        """Test mark_read raises when not authenticated."""
        notifications_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await notifications_api.mark_read("network_123")


class TestNotificationsAPIGetHistory:
    """Tests for get_history method."""

    @pytest.mark.asyncio
    async def test_get_history_sends_timestamp_query_param(self, notifications_api, mock_session):
        """Test get_history GETs notifications_history with timestamp."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"notifications": []})
        )

        await notifications_api.get_history("network_123", timestamp="ts_1")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/notifications_history")
        assert call_args.kwargs["params"] == {"timestamp": "ts_1"}

    @pytest.mark.asyncio
    async def test_get_history_omits_timestamp_when_not_given(
        self, notifications_api, mock_session
    ):
        """Test get_history sends no query params when timestamp is omitted."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await notifications_api.get_history("network_123")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["params"] == {}

    @pytest.mark.asyncio
    async def test_get_history_not_authenticated(self, notifications_api):
        """Test get_history raises when not authenticated."""
        notifications_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await notifications_api.get_history("network_123")


class TestNotificationsAPISetPushSettings:
    """Tests for set_push_settings method."""

    @pytest.mark.asyncio
    async def test_set_push_settings_sends_json_payload_and_warns(
        self, notifications_api, mock_session, caplog
    ):
        """Test set_push_settings PUTs the caller's mapping as JSON to account/push_settings."""
        import logging

        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        settings = {"networkOffline": True, "nodeOffline": False}

        with caplog.at_level(logging.WARNING):
            result = await notifications_api.set_push_settings(settings)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/account/push_settings")
        assert call_args.kwargs["json"] == settings
        assert any("set account push settings" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_push_settings_not_authenticated(self, notifications_api):
        """Test set_push_settings raises when not authenticated."""
        notifications_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await notifications_api.set_push_settings({"networkOffline": True})
