"""Tests for DevicesAPI module.

Tests cover:
- Getting device list (raw response)
- Getting device details (raw response)
- Setting device nickname
- Blocking/unblocking devices
- Device priority management
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.devices import DevicesAPI
from eero.exceptions import EeroAPIException, EeroAuthenticationException

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
    """Tests for block_device method (routes through /blacklist, not device PUT).

    The Eero cloud API silently ignores PUT /devices/{id} with {"blocked": bool}.
    Blocking is managed via POST/DELETE on /blacklist (issue #109).
    """

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.fixture
    def device_response(self):
        """Raw API response returned by get_device, including colon-format MAC."""
        return {
            "meta": {"code": 200},
            "data": {
                "url": "/2.2/networks/network_123/devices/device_abc",
                "mac": "AA:BB:CC:11:22:33",
                "nickname": "Test Device",
                "connected": True,
                "blocked": False,
            },
        }

    @pytest.mark.asyncio
    async def test_block_device_fetches_device_first(
        self, devices_api, mock_session, device_response
    ):
        """Test block_device calls get_device to resolve the MAC before POSTing."""
        get_device_response = create_mock_response(200, device_response)
        post_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.side_effect = [get_device_response, post_response]

        await devices_api.block_device("network_123", "device_abc", True)

        # First call must be GET /devices/{id}
        first_call_method, first_call_url = mock_session.request.call_args_list[0].args[:2]
        assert first_call_method == "GET"
        assert "devices/device_abc" in first_call_url

    @pytest.mark.asyncio
    async def test_block_device_posts_mac_to_blacklist(
        self, devices_api, mock_session, device_response
    ):
        """Test blocking POSTs the colon-format MAC to /blacklist (issue #109)."""
        get_device_response = create_mock_response(200, device_response)
        post_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.side_effect = [get_device_response, post_response]

        result = await devices_api.block_device("network_123", "device_abc", True)

        assert "meta" in result
        second_call = mock_session.request.call_args_list[1]
        method, url = second_call.args[:2]
        assert method == "POST"
        assert url.endswith("networks/network_123/blacklist")
        assert second_call.kwargs["json"] == {"mac": "AA:BB:CC:11:22:33"}

    @pytest.mark.asyncio
    async def test_block_device_resolved_mac_is_colon_format(
        self, devices_api, mock_session, device_response
    ):
        """Test that the MAC sent to /blacklist is in colon-separated format."""
        get_device_response = create_mock_response(200, device_response)
        post_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.side_effect = [get_device_response, post_response]

        await devices_api.block_device("network_123", "device_abc", True)

        second_call = mock_session.request.call_args_list[1]
        sent_mac = second_call.kwargs["json"]["mac"]
        # Colon-format: five colons, six two-char hex groups
        assert sent_mac.count(":") == 5
        assert sent_mac == "AA:BB:CC:11:22:33"

    @pytest.mark.asyncio
    async def test_unblock_device_deletes_from_blacklist(self, devices_api, mock_session):
        """Test unblocking DELETEs /blacklist/{device_id} without fetching the device."""
        delete_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = delete_response

        result = await devices_api.block_device("network_123", "device_abc", False)

        assert "meta" in result
        assert mock_session.request.call_count == 1
        method, url = mock_session.request.call_args.args[:2]
        assert method == "DELETE"
        assert url.endswith("networks/network_123/blacklist/device_abc")

    @pytest.mark.asyncio
    async def test_unblock_does_not_call_get_device(self, devices_api, mock_session):
        """Test unblock path skips the get_device lookup (no MAC resolution needed)."""
        delete_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = delete_response

        await devices_api.block_device("network_123", "device_abc", False)

        # Only one HTTP call: DELETE /blacklist/{device_id}
        assert mock_session.request.call_count == 1
        method, _ = mock_session.request.call_args.args[:2]
        assert method == "DELETE"

    @pytest.mark.asyncio
    async def test_block_device_returns_raw_response(
        self, devices_api, mock_session, device_response
    ):
        """Test block_device returns the raw API response from the blacklist POST."""
        get_device_response = create_mock_response(200, device_response)
        post_resp_data = {"meta": {"code": 200}, "data": {"blacklisted": True}}
        post_response = create_mock_response(200, post_resp_data)
        mock_session.request.side_effect = [get_device_response, post_response]

        result = await devices_api.block_device("network_123", "device_abc", True)

        assert result["meta"]["code"] == 200

    @pytest.mark.asyncio
    async def test_block_device_not_authenticated(self, devices_api):
        """Test block_device raises when not authenticated."""
        devices_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await devices_api.block_device("network_123", "device_abc", True)

    @pytest.mark.asyncio
    async def test_block_device_raises_when_device_response_missing_mac(
        self, devices_api, mock_session
    ):
        """Test block(True) raises EeroAPIException(502) if get_device omits `mac`.

        Guards the documented Raises contract: without a MAC we can't build the
        blacklist POST payload, so we must fail loudly instead of silently
        misbehaving. The blacklist POST must NOT be attempted in this case.
        """
        malformed = {"meta": {"code": 200}, "data": {"nickname": "no-mac-device"}}
        get_device_response = create_mock_response(200, malformed)
        mock_session.request.return_value = get_device_response

        with pytest.raises(EeroAPIException) as exc_info:
            await devices_api.block_device("network_123", "device_abc", True)

        assert exc_info.value.status_code == 502
        assert "missing 'mac' field" in str(exc_info.value)
        # Only the get_device call happened; no POST to /blacklist was attempted.
        assert mock_session.request.call_count == 1
        assert mock_session.request.call_args.args[0] == "GET"


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


class TestDevicesAPIPriority:
    """Tests for device priority management.

    set_device_priority is deprecated (issue #111): Eero's cloud API no longer
    exposes device-level priority. The method still performs a PUT and returns 200
    OK, but the change has no observable effect on the network.
    """

    @pytest.fixture
    def devices_api(self, mock_session):
        """Create a DevicesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DevicesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_device_priority_emits_deprecation_warning(self, devices_api, mock_session):
        """Test that calling set_device_priority raises DeprecationWarning (issue #111)."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        with pytest.warns(DeprecationWarning, match="set_device_priority is a no-op"):
            await devices_api.set_device_priority("network_123", "device_abc", prioritized=True)

    @pytest.mark.asyncio
    async def test_set_device_priority_warning_mentions_issue_url(self, devices_api, mock_session):
        """Test the DeprecationWarning message includes the tracking issue URL."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        with pytest.warns(DeprecationWarning, match="issues/111"):
            await devices_api.set_device_priority("network_123", "device_abc", prioritized=True)

    @pytest.mark.asyncio
    async def test_set_device_priority_warning_mentions_v6_removal(self, devices_api, mock_session):
        """Test the DeprecationWarning message mentions scheduled removal in v6.0.0."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        with pytest.warns(DeprecationWarning, match="v6.0.0"):
            await devices_api.set_device_priority("network_123", "device_abc", prioritized=True)

    @pytest.mark.asyncio
    async def test_set_device_priority_returns_raw_response(self, devices_api, mock_session):
        """Test enabling device priority returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        with pytest.warns(DeprecationWarning):
            result = await devices_api.set_device_priority(
                "network_123", "device_abc", prioritized=True
            )

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_device_priority_with_duration(self, devices_api, mock_session):
        """Test enabling device priority with duration."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        with pytest.warns(DeprecationWarning):
            result = await devices_api.set_device_priority(
                "network_123", "device_abc", prioritized=True, duration_minutes=120
            )

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["prioritized"] is True
        assert payload["priority_duration"] == 120

    @pytest.mark.asyncio
    async def test_set_device_priority_targets_v2_3_endpoint(self, devices_api, mock_session):
        """Test the priority PUT still targets the 2.3 endpoint (issue #102)."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        with pytest.warns(DeprecationWarning):
            await devices_api.set_device_priority("network_123", "device_abc", prioritized=True)

        method, url = mock_session.request.call_args.args[:2]
        assert method == "PUT"
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/devices/device_abc"
