"""Tests for DevicesAPI module.

Tests cover:
- Getting device list (raw response)
- Getting device details (raw response)
- Setting device nickname
- Blocking/unblocking devices
- Pausing device internet access
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.devices import DevicesAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestDevicesAPIInit:
    """Tests for DevicesAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = DevicesAPI(auth_api)

        assert api._auth_api is auth_api


class TestDevicesAPIGetDevices:
    """Tests for get_devices method."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_devices_returns_raw_response(
        self, devices_api, mock_session, sample_devices_list
    ):
        """Test get_devices returns raw API response."""
        expected_response = api_success_response(sample_devices_list)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.get_devices("network_123")

        # Raw response should include meta and data
        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_devices_not_authenticated(self, devices_api):
        """Test get_devices raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await devices_api.get_devices("network_123")


class TestDevicesAPIGetDevice:
    """Tests for get_device method."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_device_returns_raw_response(
        self, devices_api, mock_session, sample_device_data
    ):
        """Test get_device returns raw API response."""
        expected_response = api_success_response(sample_device_data)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.get_device("network_123", "device_abc")

        assert "meta" in result
        assert "data" in result
        assert result["data"]["mac"] == "AA:BB:CC:DD:EE:FF"
        assert result["data"]["nickname"] == "John's iPhone"

    @pytest.mark.asyncio
    async def test_get_device_not_authenticated(self, devices_api):
        """Test get_device raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await devices_api.get_device("network_123", "device_abc")


class TestDevicesAPISetNickname:
    """Tests for set_device_nickname method."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_nickname_returns_raw_response(self, devices_api, mock_session):
        """Test successful nickname change returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.set_device_nickname("network_123", "device_abc", "My Device")

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_nickname_sends_correct_payload(self, devices_api, mock_session):
        """Test that correct payload is sent for nickname change."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        await devices_api.set_device_nickname("network_123", "device_abc", "New Name")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"nickname": "New Name"}

    @pytest.mark.asyncio
    async def test_set_nickname_targets_v2_3_endpoint(self, devices_api, mock_session):
        """Test the nickname PUT targets the 2.3 endpoint (issue #102)."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        await devices_api.set_device_nickname("network_123", "device_abc", "New Name")

        method, url = mock_session.request.call_args.args[:2]
        assert method == "PUT"
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/devices/device_abc"

    @pytest.mark.asyncio
    async def test_set_nickname_not_authenticated(self, devices_api):
        """Test set_device_nickname raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await devices_api.set_device_nickname("network_123", "device_abc", "New Name")


class TestDevicesAPIBlockDevice:
    """Tests for block_device/unblock_device (delegate to BlacklistAPI).

    Blocking is managed via POST/DELETE on /blacklist (issue #109); these
    two methods simply delegate to `eero.api.blacklist.BlacklistAPI` rather
    than duplicating request building.
    """

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_block_device_posts_form_encoded_mac_to_blacklist(
        self, devices_api, mock_session
    ):
        """Test block_device form-POSTs the MAC to /blacklist (issue #109 shape)."""
        post_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = post_response

        result = await devices_api.block_device("network_123", "aa:bb:cc:11:22:33")

        assert "meta" in result
        method, url = mock_session.request.call_args.args[:2]
        assert method == "POST"
        assert url.endswith("networks/network_123/blacklist")
        assert mock_session.request.call_args.kwargs["data"] == {"mac": "aa:bb:cc:11:22:33"}

    @pytest.mark.asyncio
    async def test_unblock_device_deletes_from_blacklist(self, devices_api, mock_session):
        """Test unblock_device DELETEs /blacklist/{mac}."""
        delete_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = delete_response

        result = await devices_api.unblock_device("network_123", "aa:bb:cc:11:22:33")

        assert "meta" in result
        assert mock_session.request.call_count == 1
        method, url = mock_session.request.call_args.args[:2]
        assert method == "DELETE"
        assert url.endswith("networks/network_123/blacklist/aa:bb:cc:11:22:33")

    @pytest.mark.asyncio
    async def test_block_device_not_authenticated(self, devices_api):
        """Test block_device raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await devices_api.block_device("network_123", "aa:bb:cc:11:22:33")

    @pytest.mark.asyncio
    async def test_unblock_device_not_authenticated(self, devices_api):
        """Test unblock_device raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await devices_api.unblock_device("network_123", "aa:bb:cc:11:22:33")


class TestDevicesAPIUpdateDeviceViaLink:
    """Tests for update_device_via_link (unverified, warns)."""

    @pytest.fixture
    def devices_api(self, mock_session):
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_update_device_via_link_builds_template_url(self, devices_api, mock_session):
        """Test the write targets the default-version device URL by default."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await devices_api.update_device_via_link("network_123", "aabbccddeeff", nickname="New Name")

        method, url = mock_session.request.call_args.args[:2]
        assert method == "PUT"
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123/devices/aabbccddeeff"
        assert mock_session.request.call_args.kwargs["json"] == {"nickname": "New Name"}

    @pytest.mark.asyncio
    async def test_update_device_via_link_prefers_parent_self_url(self, devices_api, mock_session):
        """Test the write prefers the device's own self_url from parent."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"url": "/2.3/networks/network_123/devices/aabbccddeeff"}

        await devices_api.update_device_via_link(
            "network_123", "aabbccddeeff", paused=True, parent=parent
        )

        _, url = mock_session.request.call_args.args[:2]
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/devices/aabbccddeeff"

    @pytest.mark.asyncio
    async def test_update_device_via_link_only_sends_supplied_fields(
        self, devices_api, mock_session
    ):
        """Test omitted keyword args are not sent in the JSON body."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await devices_api.update_device_via_link(
            "network_123", "aabbccddeeff", profile="/2.2/networks/network_123/profiles/p_1"
        )

        payload = mock_session.request.call_args.kwargs["json"]
        assert payload == {"profile": "/2.2/networks/network_123/profiles/p_1"}

    @pytest.mark.asyncio
    async def test_update_device_via_link_not_authenticated(self, devices_api):
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)
        with pytest.raises(EeroAuthenticationException):
            await devices_api.update_device_via_link("network_123", "aabbccddeeff")


class TestDevicesAPISetDeviceType:
    """Tests for set_device_type (live-verified 2026-09-20, does not warn)."""

    @pytest.fixture
    def devices_api(self, mock_session):
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_device_type_sends_payload(self, devices_api, mock_session):
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await devices_api.set_device_type("network_123", "aabbccddeeff", "gateway")

        method, url = mock_session.request.call_args.args[:2]
        assert method == "PUT"
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123/devices/aabbccddeeff"
        assert mock_session.request.call_args.kwargs["json"] == {"device_type": "gateway"}

    @pytest.mark.asyncio
    async def test_set_device_type_does_not_warn(self, devices_api, mock_session, caplog):
        """Test set_device_type does not carry the uncharacterised-write warning.

        The write is live-verified, so it must not carry the warning.
        """
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await devices_api.set_device_type("network_123", "aabbccddeeff", "gateway")

        assert not any("not been fully characterised" in m for m in caplog.messages)


class TestDevicesAPILabels:
    """Tests for get_device_labels (read) / set_device_labels.

    set_device_labels is a verified NO-OP as of 2026-09-20: the PUT
    returns HTTP 200 but the value never shows up on a read-back, so it
    still carries the uncharacterised-write warning.
    """

    @pytest.fixture
    def devices_api(self, mock_session):
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_device_labels_gets_labels_path(self, devices_api, mock_session):
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await devices_api.get_device_labels("network_123", "aabbccddeeff")

        method, url = mock_session.request.call_args.args[:2]
        assert method == "GET"
        assert url.endswith("networks/network_123/devices/aabbccddeeff/labels")

    @pytest.mark.asyncio
    async def test_set_device_labels_sends_query_params_not_body(self, devices_api, mock_session):
        """Test labels are sent as query params on the PUT, not a JSON/form body."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await devices_api.set_device_labels(
            "network_123", "aabbccddeeff", make_label="Acme", model_label="X1"
        )

        call = mock_session.request.call_args
        assert call.args[0] == "PUT"
        assert call.kwargs["params"] == {"make_label": "Acme", "model_label": "X1"}
        assert "json" not in call.kwargs
        assert "data" not in call.kwargs


class TestDevicesAPIGetDevicesQueryParams:
    """Tests for the optional thread/proxied_node query params on get_devices."""

    @pytest.fixture
    def devices_api(self, mock_session):
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("thread", "proxied_node", "expected"),
        [
            (True, None, {"thread": "true"}),
            (False, None, {"thread": "false"}),
            (None, True, {"proxied_node": "true"}),
            (True, False, {"thread": "true", "proxied_node": "false"}),
            (None, None, {}),
        ],
    )
    async def test_get_devices_query_params(
        self, devices_api, mock_session, thread, proxied_node, expected
    ):
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": []}
        )

        await devices_api.get_devices("network_123", thread=thread, proxied_node=proxied_node)

        params = mock_session.request.call_args.kwargs.get("params")
        assert params == (expected or None)

    @pytest.mark.asyncio
    async def test_get_devices_prefers_parent_link(self, devices_api, mock_session):
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": []}
        )
        parent = {
            "url": "/2.2/networks/network_123",
            "resources": {"devices": "/2.3/networks/network_123/devices"},
        }

        await devices_api.get_devices("network_123", parent=parent)

        _, url = mock_session.request.call_args.args[:2]
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/devices"


class TestDevicesAPIPauseDevice:
    """Tests for pause_device method."""

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_pause_device_returns_raw_response(self, devices_api, mock_session):
        """Test successful device pausing returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await devices_api.pause_device("network_123", "device_abc", True)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_pause_device_sends_correct_payload(self, devices_api, mock_session):
        """Test that correct payload is sent for pausing."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        await devices_api.pause_device("network_123", "device_abc", True)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"paused": True}

    @pytest.mark.asyncio
    async def test_pause_device_targets_v2_3_endpoint(self, devices_api, mock_session):
        """Test the pause PUT targets the 2.3 endpoint (issue #102).

        On 2.2 the backend returns 200 OK but silently ignores the mutation, so
        the write must go to 2.3 for the pause to actually persist.
        """
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        await devices_api.pause_device("network_123", "device_abc", True)

        method, url = mock_session.request.call_args.args[:2]
        assert method == "PUT"
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/devices/device_abc"

    @pytest.mark.asyncio
    async def test_pause_device_not_authenticated(self, devices_api):
        """Test pause_device raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await devices_api.pause_device("network_123", "device_abc", True)
