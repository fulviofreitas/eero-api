"""Tests for ThreadAPI module.

Tests cover:
- Getting Thread status (raw response, via the thread link)
- Enabling/disabling Thread and updating its configuration (literal path)
- Regenerating Thread credentials (empty-string body)
- The uncharacterised-write warning on every write
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.thread import ThreadAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def thread_api(mock_session):
    """Create a ThreadAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return ThreadAPI(auth_api)


class TestThreadAPIInit:
    """Tests for ThreadAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = ThreadAPI(auth_api)

        assert api._auth_api is auth_api


class TestThreadAPIGetThread:
    """Tests for get_thread method."""

    @pytest.mark.asyncio
    async def test_get_thread_uses_default_template(self, thread_api, mock_session):
        """Test get_thread GETs the thread link built from the template."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"enabled": False})
        )

        result = await thread_api.get_thread("network_123")

        assert result["data"]["enabled"] is False
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/thread")

    @pytest.mark.asyncio
    async def test_get_thread_prefers_parent_link(self, thread_api, mock_session):
        """Test get_thread uses the network's published thread link."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"enabled": False})
        )
        parent = {"resources": {"thread": "/2.3/networks/network_123/thread"}}

        await thread_api.get_thread("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/thread")

    @pytest.mark.asyncio
    async def test_get_thread_not_authenticated(self, thread_api):
        """Test get_thread raises when not authenticated."""
        thread_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await thread_api.get_thread("network_123")


class TestThreadAPISetThreadEnabled:
    """Tests for set_thread_enabled method."""

    @pytest.mark.asyncio
    async def test_set_thread_enabled_sends_json_payload(self, thread_api, mock_session, caplog):
        """Test set_thread_enabled PUTs {"enabled": bool} to the literal thread path."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await thread_api.set_thread_enabled("network_123", True)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/thread")
        assert call_args.kwargs["json"] == {"enabled": True}
        assert any("set thread enabled for network" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_thread_enabled_not_authenticated(self, thread_api):
        """Test set_thread_enabled raises when not authenticated."""
        thread_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await thread_api.set_thread_enabled("network_123", True)


class TestThreadAPIUpdateThread:
    """Tests for update_thread method."""

    @pytest.mark.asyncio
    async def test_update_thread_sends_only_supplied_keys(self, thread_api, mock_session, caplog):
        """Test update_thread PUTs exactly the supplied keys to the literal thread path."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await thread_api.update_thread(
                "network_123", thread_enable=True, enable_credential_syncing=False
            )

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/thread")
        assert call_args.kwargs["json"] == {
            "thread_enable": True,
            "enable_credential_syncing": False,
        }
        assert any("update thread config for network" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_update_thread_requires_at_least_one_field(self, thread_api):
        """Test update_thread rejects a call with neither field supplied."""
        with pytest.raises(EeroValidationException):
            await thread_api.update_thread("network_123")

    @pytest.mark.asyncio
    async def test_update_thread_not_authenticated(self, thread_api):
        """Test update_thread raises when not authenticated."""
        thread_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await thread_api.update_thread("network_123", thread_enable=True)


class TestThreadAPIRegenerateCredentials:
    """Tests for regenerate_thread_credentials method."""

    @pytest.mark.asyncio
    async def test_regenerate_thread_credentials_posts_empty_json_string(
        self, thread_api, mock_session, caplog
    ):
        """Test regenerate_thread_credentials POSTs the two-byte "" body and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {"network": {}}}
        )

        with caplog.at_level(logging.WARNING):
            result = await thread_api.regenerate_thread_credentials("network_123")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/networks/network_123/thread")
        assert call_args.kwargs["data"] == '""'
        assert any("regenerate thread credentials for network" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_regenerate_thread_credentials_not_authenticated(self, thread_api):
        """Test regenerate_thread_credentials raises when not authenticated."""
        thread_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await thread_api.regenerate_thread_credentials("network_123")
