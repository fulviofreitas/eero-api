"""Tests for WanAPI module.

Tests cover:
- get_multistaticip: verified read on API version 2.3, parent-link
  preference, 404 propagation
- set_multistaticip: JSON body forwarded unchanged, on version 2.3
- set_secondary_wan_config: JSON body forwarded unchanged, on version 2.3,
  the settings-class reboot warning
- set_device_secondary_wan_access: JSON body, on version 2.3, the
  settings-class reboot warning
- Version pins enforced for every network and device form (bare ID, path, URL)
- Not-authenticated errors on every method
- get_multistaticip pinned to 2.3 for the id, path, URL and parent-link forms
- Unsafe network, device or link values rejected before any request
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.wan import WanAPI
from eero.exceptions import (
    EeroAuthenticationException,
    EeroNotFoundException,
    EeroValidationException,
)

from .conftest import api_error_response, api_success_response, create_mock_response

# Every form a caller may hold: a bare ID, an API-returned path, an absolute URL.
NETWORK_FORMS = [
    "n1",
    "/2.2/networks/n1",
    "https://api-user.e2ro.com/2.2/networks/n1",
]
PINNED_NETWORK_URL = "https://api-user.e2ro.com/2.3/networks/n1"


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


class TestWanAPIVersionPinnedWrites:
    """The 2.3 pin must survive a network path/URL, which keeps its own version."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("network", NETWORK_FORMS)
    @pytest.mark.parametrize(
        "method,args,kwargs,suffix",
        [
            ("set_multistaticip", ({"enabled": False},), {}, "multistaticip"),
            (
                "set_secondary_wan_config",
                ({"devices": []},),
                {},
                "devices/secondary_wan_config",
            ),
            (
                "set_device_secondary_wan_access",
                ("aabbccddeeff",),
                {"deny": True},
                "devices/aabbccddeeff",
            ),
        ],
    )
    async def test_write_pins_v2_3_for_every_network_form(
        self, wan_api, mock_session, network, method, args, kwargs, suffix
    ):
        """Each WAN write lands on 2.3 whichever network form the caller holds."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await getattr(wan_api, method)(network, *args, **kwargs)

        verb, url = mock_session.request.call_args.args[:2]
        assert verb == "PUT"
        assert url == f"{PINNED_NETWORK_URL}/{suffix}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("network", NETWORK_FORMS)
    @pytest.mark.parametrize(
        "mac",
        [
            "/2.2/networks/n1/devices/aabbccddeeff",
            "https://api-user.e2ro.com/2.2/networks/n1/devices/aabbccddeeff",
        ],
    )
    async def test_set_device_secondary_wan_access_pins_v2_3_for_path_form_mac(
        self, wan_api, mock_session, network, mac
    ):
        """A path/URL-form mac is an independent route to 2.2 and must still reach 2.3.

        Unlike the devices module, this call site does not normalise ``mac``
        with ``id_from_url``, so the resolved URL can carry the 2.2 version
        taken from the device path itself rather than from the network.
        """
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await wan_api.set_device_secondary_wan_access(network, mac, deny=True)

        verb, url = mock_session.request.call_args.args[:2]
        assert verb == "PUT"
        assert url == f"{PINNED_NETWORK_URL}/devices/aabbccddeeff"
class TestWanAPIGetMultistaticipPinnedUrlForms:
    """get_multistaticip lands on 2.3 whichever form the network and its link take."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "network",
        [
            "network_123",
            "/2.2/networks/network_123",
            "/2.3/networks/network_123",
            "https://api-user.e2ro.com/2.2/networks/network_123",
            "HTTPS://api-user.e2ro.com/2.2/networks/network_123",
            "hTTps://api-user.e2ro.com/2.2/networks/network_123",
        ],
        ids=["id", "path-2.2", "path-2.3", "url-2.2", "uppercase-scheme", "mixed-case-scheme"],
    )
    async def test_every_network_form_is_pinned_to_2_3(self, wan_api, mock_session, network):
        """A network path or URL carrying 2.2 is rewritten to the 2.3-only endpoint."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await wan_api.get_multistaticip(network)

        method, url = mock_session.request.call_args.args[:2]
        assert method == "GET"
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/multistaticip"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("version", ["2.2", "2.3"])
    async def test_parent_link_on_any_version_is_pinned_to_2_3(
        self, wan_api, mock_session, version
    ):
        """A published link on another version does not move the read off 2.3."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"resources": {"multistaticip": f"/{version}/networks/network_123/multistaticip"}}

        await wan_api.get_multistaticip("network_123", parent=parent)

        _, url = mock_session.request.call_args.args[:2]
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/multistaticip"


#: Every WanAPI request method, as (label, call) where `call` takes
#: (api, network, mac) and returns the awaitable to invoke.
WAN_NETWORK_CALLS = [
    ("get_multistaticip", lambda api, network, mac: api.get_multistaticip(network)),
    ("set_multistaticip", lambda api, network, mac: api.set_multistaticip(network, {})),
    (
        "set_secondary_wan_config",
        lambda api, network, mac: api.set_secondary_wan_config(network, {}),
    ),
    (
        "set_device_secondary_wan_access",
        lambda api, network, mac: api.set_device_secondary_wan_access(network, mac, deny=True),
    ),
]


class TestWanAPIUnsafeUrlsRejectedBeforeTransport:
    """No WAN method sends a request for a network or device that is not one safe path."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "label, call", WAN_NETWORK_CALLS, ids=[c[0] for c in WAN_NETWORK_CALLS]
    )
    @pytest.mark.parametrize("control", ["\n", "\t", "\r", " ", "\x00"])
    async def test_control_character_in_network_raises(
        self, wan_api, mock_session, label, call, control
    ):
        """A control character in a network id, path or URL raises before transport."""
        for network in (
            f"net{control}work_123",
            f"/2.2/networks/network_123{control}",
            f"https://api-user.e2ro.com/2.2/networks/network_123{control}",
            f"HTTPS://api-user.e2ro.com/2.2/networks/net{control}work_123",
        ):
            with pytest.raises(EeroValidationException):
                await call(wan_api, network, "AA:BB:CC:DD:EE:FF")

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "label, call", WAN_NETWORK_CALLS, ids=[c[0] for c in WAN_NETWORK_CALLS]
    )
    @pytest.mark.parametrize(
        "network",
        [
            "/2.2/account",
            "/2.2/networks/network_123/../../account",
            "/2.2/networks/network_123?x=1",
            "/2.2/networks/%2e%2e/account",
        ],
        ids=["other-family", "dotdot", "query", "encoded-dotdot"],
    )
    async def test_path_that_is_not_one_network_raises(
        self, wan_api, mock_session, label, call, network
    ):
        """A path naming another resource, or carrying dot segments or a query, raises."""
        with pytest.raises(EeroValidationException):
            await call(wan_api, network, "AA:BB:CC:DD:EE:FF")

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("control", ["\n", "\t", "\r", " ", "\x00"])
    async def test_get_multistaticip_parent_link_with_control_character_raises(
        self, wan_api, mock_session, control
    ):
        """A published link carrying a control character is refused, not pinned."""
        parent = {"resources": {"multistaticip": f"/2.2/networks/network_123/multi{control}"}}

        with pytest.raises(EeroValidationException):
            await wan_api.get_multistaticip("network_123", parent=parent)

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "mac",
        ["AA:BB:CC:DD:EE:FF\n", "AA:BB:CC\t:DD:EE:FF", "..", "AA:BB:CC:DD:EE:FF?x=1", ""],
        ids=["newline", "tab", "dotdot", "query", "empty"],
    )
    async def test_set_device_secondary_wan_access_unsafe_mac_raises(
        self, wan_api, mock_session, mac
    ):
        """A device identifier that is not one safe path segment raises before transport."""
        with pytest.raises(EeroValidationException):
            await wan_api.set_device_secondary_wan_access("network_123", mac, deny=True)

        mock_session.request.assert_not_called()
