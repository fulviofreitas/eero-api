"""Tests for SqmAPI module.

Tests cover:
- Getting SQM settings (raw response, via the network's own URL)
- Setting the SQM boolean via a query parameter with no body
- id/path/URL polymorphism and parent-link preference
- The uncharacterised-write warning
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.sqm import SqmAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def sqm_api(mock_session):
    """Create a SqmAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return SqmAPI(auth_api)


class TestSqmAPIInit:
    """Tests for SqmAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = SqmAPI(auth_api)

        assert api._auth_api is auth_api


class TestSqmAPIGetSettings:
    """Tests for get_sqm_settings method."""

    @pytest.mark.asyncio
    async def test_get_sqm_settings_reads_network_envelope(self, sqm_api, mock_session):
        """Test get_sqm_settings GETs the network's own URL."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"sqm": True})
        )

        result = await sqm_api.get_sqm_settings("network_123")

        assert result["data"]["sqm"] is True
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123")

    @pytest.mark.asyncio
    async def test_get_sqm_settings_prefers_parent_self_url(self, sqm_api, mock_session):
        """Test get_sqm_settings uses the parent's own url over the template."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"sqm": True})
        )
        parent = {"url": "/2.3/networks/network_123"}

        await sqm_api.get_sqm_settings("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123")

    @pytest.mark.asyncio
    async def test_get_sqm_settings_not_authenticated(self, sqm_api):
        """Test get_sqm_settings raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.get_sqm_settings("network_123")


class TestSqmAPISetSqm:
    """Tests for set_sqm method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("enabled,expected", [(True, "true"), (False, "false")])
    async def test_set_sqm_sends_query_param_with_no_body(
        self, sqm_api, mock_session, caplog, enabled, expected
    ):
        """Test set_sqm PUTs to the settings link with sqm as a query param and no body."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await sqm_api.set_sqm("network_123", enabled)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/settings")
        assert call_args.kwargs["params"] == {"sqm": expected}
        assert "json" not in call_args.kwargs or call_args.kwargs["json"] is None
        assert "data" not in call_args.kwargs or call_args.kwargs["data"] is None
        assert any("set SQM for network" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_sqm_prefers_parent_link(self, sqm_api, mock_session):
        """Test set_sqm uses the network's published settings link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"settings": "/2.3/networks/network_123/settings"}}

        await sqm_api.set_sqm("network_123", True, parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/settings")

    @pytest.mark.asyncio
    async def test_set_sqm_not_authenticated(self, sqm_api):
        """Test set_sqm raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.set_sqm("network_123", True)
