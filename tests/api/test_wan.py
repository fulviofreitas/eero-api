"""Tests for WanAPI module.

Tests cover:
- get_multistaticip: verified read on API version 2.3, parent-link
  preference, 404 propagation
- set_multistaticip: JSON body forwarded unchanged, on version 2.3
- set_secondary_wan_config: JSON body forwarded unchanged, on version 2.3,
  the settings-class reboot warning
- set_device_secondary_wan_access: JSON body, on version 2.3, the
  settings-class reboot warning
- Not-authenticated errors on every method
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.wan import WanAPI
from eero.exceptions import EeroAuthenticationException, EeroNotFoundException

from .conftest import api_error_response, api_success_response, create_mock_response


@pytest.fixture
def wan_api(mock_session):
    """Create a WanAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return WanAPI(auth_api)


class TestWanAPIInit:
    """Tests for WanAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = WanAPI(auth_api)

        assert api._auth_api is auth_api


class TestWanAPIGetMultistaticip:
    """Tests for get_multistaticip method."""

    @pytest.mark.asyncio
    async def test_get_multistaticip_uses_version_2_3(self, wan_api, mock_session):
        """Test get_multistaticip GETs the multistaticip sub-resource on API 2.3."""
        expected = {"enabled": True, "type": "P"}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(expected)
        )

        result = await wan_api.get_multistaticip("network_123")

        assert result["data"] == expected
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.3/networks/network_123/multistaticip")

    @pytest.mark.asyncio
    async def test_get_multistaticip_prefers_parent_link(self, wan_api, mock_session):
        """Test get_multistaticip uses the published link over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"resources": {"multistaticip": "/2.3/networks/network_123/multistaticip"}}

        await wan_api.get_multistaticip("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/multistaticip")

    @pytest.mark.asyncio
    async def test_get_multistaticip_raises_not_found(self, wan_api, mock_session):
        """Test get_multistaticip surfaces the documented 404 for networks without the feature."""
        mock_session.request.return_value = create_mock_response(
            404,
            api_error_response(404, "error.network.multistaticip_not_found"),
        )

        with pytest.raises(EeroNotFoundException):
            await wan_api.get_multistaticip("network_123")

    @pytest.mark.asyncio
    async def test_get_multistaticip_not_authenticated(self, wan_api):
        """Test get_multistaticip raises when not authenticated."""
        wan_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await wan_api.get_multistaticip("network_123")


class TestWanAPISetMultistaticip:
    """Tests for set_multistaticip method."""

    @pytest.mark.asyncio
    async def test_set_multistaticip_forwards_body_unchanged(self, wan_api, mock_session, caplog):
        """Test set_multistaticip PUTs the caller's mapping unchanged, on version 2.3."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        config = {
            "enabled": True,
            "type": "P",
            "multistaticip_settings": {"router_ip": "203.0.113.1"},
        }

        with caplog.at_level(logging.WARNING):
            await wan_api.set_multistaticip("network_123", config)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.3/networks/network_123/multistaticip")
        assert call_args.kwargs["json"] == config
        assert any(
            "set multi-static-IP configuration for network" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_set_multistaticip_not_authenticated(self, wan_api):
        """Test set_multistaticip raises when not authenticated."""
        wan_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await wan_api.set_multistaticip("network_123", {})


class TestWanAPISetSecondaryWanConfig:
    """Tests for set_secondary_wan_config method."""

    @pytest.mark.asyncio
    async def test_set_secondary_wan_config_forwards_body_unchanged(
        self, wan_api, mock_session, caplog
    ):
        """Test set_secondary_wan_config PUTs the mapping unchanged, on version 2.3, and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        config = {"devices": [{"mac": "AA:BB:CC:DD:EE:FF", "secondary_wan_deny_access": True}]}

        with caplog.at_level(logging.WARNING):
            await wan_api.set_secondary_wan_config("network_123", config)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.3/networks/network_123/devices/secondary_wan_config")
        assert call_args.kwargs["json"] == config
        assert any(
            "set secondary WAN configuration for network" in message and "reboot" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_set_secondary_wan_config_not_authenticated(self, wan_api):
        """Test set_secondary_wan_config raises when not authenticated."""
        wan_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await wan_api.set_secondary_wan_config("network_123", {})


class TestWanAPISetDeviceSecondaryWanAccess:
    """Tests for set_device_secondary_wan_access method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("deny", [True, False])
    async def test_set_device_secondary_wan_access_sends_json(
        self, wan_api, mock_session, caplog, deny
    ):
        """Test set_device_secondary_wan_access PUTs the deny flag, on version 2.3, and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await wan_api.set_device_secondary_wan_access(
                "network_123", "AA:BB:CC:DD:EE:FF", deny=deny
            )

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.3/networks/network_123/devices/AA:BB:CC:DD:EE:FF")
        assert call_args.kwargs["json"] == {"secondary_wan_deny_access": deny}
        assert any(
            "set secondary WAN access for device" in message and "reboot" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_set_device_secondary_wan_access_not_authenticated(self, wan_api):
        """Test set_device_secondary_wan_access raises when not authenticated."""
        wan_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await wan_api.set_device_secondary_wan_access(
                "network_123", "AA:BB:CC:DD:EE:FF", deny=True
            )
