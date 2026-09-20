"""Tests for DdnsAPI module.

Tests cover:
- enable/disable: no request body carrier, parent-link preference, the
  uncharacterised-write warning
- Not-authenticated errors on every method
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.ddns import DdnsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import create_mock_response


@pytest.fixture
def ddns_api(mock_session):
    """Create a DdnsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return DdnsAPI(auth_api)


class TestDdnsAPIInit:
    """Tests for DdnsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = DdnsAPI(auth_api)

        assert api._auth_api is auth_api


class TestDdnsAPIEnable:
    """Tests for enable method."""

    @pytest.mark.asyncio
    async def test_enable_sends_no_body(self, ddns_api, mock_session, caplog):
        """Test enable PUTs with no request body carrier and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await ddns_api.enable("network_123")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/ddns/enable")
        assert call_args.kwargs.get("json") is None
        assert call_args.kwargs.get("data") is None
        assert any("enable DDNS for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_enable_prefers_parent_link(self, ddns_api, mock_session):
        """Test enable uses the network's published ddns/enable link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"ddns_enable": "/2.3/networks/network_123/ddns/enable"}}

        await ddns_api.enable("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/ddns/enable")

    @pytest.mark.asyncio
    async def test_enable_not_authenticated(self, ddns_api):
        """Test enable raises when not authenticated."""
        ddns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await ddns_api.enable("network_123")


class TestDdnsAPIDisable:
    """Tests for disable method."""

    @pytest.mark.asyncio
    async def test_disable_sends_no_body(self, ddns_api, mock_session, caplog):
        """Test disable PUTs with no request body carrier and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await ddns_api.disable("network_123")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/ddns/disable")
        assert call_args.kwargs.get("json") is None
        assert call_args.kwargs.get("data") is None
        assert any("disable DDNS for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_disable_prefers_parent_link(self, ddns_api, mock_session):
        """Test disable uses the network's published ddns/disable link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"ddns_disable": "/2.3/networks/network_123/ddns/disable"}}

        await ddns_api.disable("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/ddns/disable")

    @pytest.mark.asyncio
    async def test_disable_not_authenticated(self, ddns_api):
        """Test disable raises when not authenticated."""
        ddns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await ddns_api.disable("network_123")
