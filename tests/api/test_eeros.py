"""Tests for EerosAPI module.

Tests cover:
- Getting eero device list / a single eero (raw response), including
  id/path/URL polymorphism and parent-link preference
- Rebooting eero devices (empty-string body)
- LED control (on/off, brightness) as form-encoded writes to the led_action link
- Location writes
- Nightlight discovery (via parent, via a first GET, and the
  feature-unavailable path) and writes with the enabled/brightness_percentage/
  schedule fields
- Connections reads
- Node/port power actions, LED cycling, nightlight brightness preview, and
  support diagnostics reads
- The uncharacterised-write warning on every unverified write
- That no method mutates its ``parent`` argument
"""

import copy
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.eeros import EerosAPI
from eero.exceptions import (
    EeroAuthenticationException,
    EeroFeatureUnavailableException,
    EeroNotFoundException,
    EeroValidationException,
)

from .conftest import api_error_response, api_success_response, create_mock_response


@pytest.fixture
def eeros_api(mock_session):
    """Create an EerosAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return EerosAPI(auth_api)


def _queue(mock_session, *responses):
    """Queue a sequence of mock responses returned by successive requests."""
    mock_session.request.side_effect = list(responses)


class TestEerosAPIInit:
    """Tests for EerosAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = EerosAPI(auth_api)

        assert api._auth_api is auth_api


class TestEerosAPIGetEeros:
    """Tests for get_eeros method."""

    @pytest.mark.asyncio
    async def test_get_eeros_uses_default_template(self, eeros_api, mock_session):
        """Test get_eeros builds the URL from the template when no parent is given."""
        mock_session.request.return_value = create_mock_response(200, api_success_response([]))

        result = await eeros_api.get_eeros("network_123")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/eeros")

    @pytest.mark.asyncio
    async def test_get_eeros_prefers_parent_link(self, eeros_api, mock_session):
        """Test get_eeros uses the network's published eeros link over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response([]))
        parent = {"resources": {"eeros": "/2.3/networks/network_123/eeros"}}
        parent_copy = copy.deepcopy(parent)

        await eeros_api.get_eeros("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/eeros")
        assert parent == parent_copy

    @pytest.mark.asyncio
    async def test_get_eeros_not_authenticated(self, eeros_api):
        """Test get_eeros raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await eeros_api.get_eeros("network_123")


class TestEerosAPIGetEero:
    """Tests for get_eero method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "eero_id,expected_suffix",
        [
            ("eero_001", "/2.2/eeros/eero_001"),
            ("/2.2/eeros/eero_001", "/2.2/eeros/eero_001"),
            ("https://api-user.e2ro.com/2.2/eeros/eero_001", "/2.2/eeros/eero_001"),
        ],
    )
    async def test_get_eero_accepts_id_path_or_url(
        self, eeros_api, mock_session, sample_eero_data, eero_id, expected_suffix
    ):
        """Test get_eero accepts a bare id, a path, or an absolute URL."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(sample_eero_data)
        )

        result = await eeros_api.get_eero("network_123", eero_id)

        assert result["data"]["serial"] == "ABC123456789"
        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith(expected_suffix)

    @pytest.mark.asyncio
    async def test_get_eero_prefers_parent_self_url(
        self, eeros_api, mock_session, sample_eero_data
    ):
        """Test get_eero uses the parent's own url over the template."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(sample_eero_data)
        )
        parent = {"url": "/2.3/eeros/eero_001"}

        await eeros_api.get_eero("network_123", "eero_001", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/eeros/eero_001")

    @pytest.mark.asyncio
    async def test_get_eero_not_authenticated(self, eeros_api):
        """Test get_eero raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.get_eero("network_123", "eero_001")


class TestEerosAPIReboot:
    """Tests for reboot_eero method."""

    @pytest.mark.asyncio
    async def test_reboot_posts_empty_json_string_to_reboot_link(self, eeros_api, mock_session):
        """Test reboot POSTs the two-byte "" body to the eero's reboot link."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        result = await eeros_api.reboot_eero("network_123", "eero_001")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/eeros/eero_001/reboot")
        assert call_args.kwargs["data"] == '""'
        assert call_args.kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_reboot_prefers_parent_link(self, eeros_api, mock_session):
        """Test reboot uses the eero's published reboot link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"reboot": "/2.3/eeros/eero_001/reboot"}}

        await eeros_api.reboot_eero("network_123", "eero_001", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/eeros/eero_001/reboot")

    @pytest.mark.asyncio
    async def test_reboot_not_authenticated(self, eeros_api):
        """Test reboot raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.reboot_eero("network_123", "eero_001")

    @pytest.mark.asyncio
    async def test_reboot_does_not_warn(self, eeros_api, mock_session, caplog):
        """Test reboot_eero does not carry the uncharacterised-write warning.

        The write is live-verified, so it must not carry the warning.
        """
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await eeros_api.reboot_eero("network_123", "eero_001")

        assert not any("not been fully characterised" in m for m in caplog.messages)


class TestEerosAPILedStatus:
    """Tests for LED status methods."""

    @pytest.mark.asyncio
    async def test_get_led_status_returns_raw_response(self, eeros_api, mock_session):
        """Test getting LED status returns raw response."""
        eero_data = {"serial": "ABC123", "led_on": True, "led_brightness": 75}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(eero_data)
        )

        result = await eeros_api.get_led_status("network_123", "eero_001")

        assert result["data"]["led_on"] is True
        assert result["data"]["led_brightness"] == 75

    @pytest.mark.asyncio
    async def test_get_led_status_not_authenticated(self, eeros_api):
        """Test get_led_status raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.get_led_status("network_123", "eero_001")


class TestEerosAPILedControl:
    """Tests for LED control methods."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("enabled,expected", [(True, "true"), (False, "false")])
    async def test_set_led_sends_form_encoded_led_on(
        self, eeros_api, mock_session, caplog, enabled, expected
    ):
        """Test set_led PUTs form-encoded led_on to the led_action link without warning.

        The write is live-verified, so it must not carry the
        uncharacterised-write warning.
        """
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await eeros_api.set_led("network_123", "eero_001", enabled)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/eeros/eero_001/led")
        assert call_args.kwargs["data"] == {"led_on": expected}
        assert "json" not in call_args.kwargs or call_args.kwargs["json"] is None
        assert not any("not been fully characterised" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_led_prefers_parent_link(self, eeros_api, mock_session):
        """Test set_led uses the eero's published led_action link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"led_action": "/2.3/eeros/eero_001/led"}}

        await eeros_api.set_led("network_123", "eero_001", True, parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/eeros/eero_001/led")

    @pytest.mark.asyncio
    async def test_set_led_not_authenticated(self, eeros_api):
        """Test set_led raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.set_led("network_123", "eero_001", True)


class TestEerosAPILedBrightness:
    """Tests for LED brightness control."""

    @pytest.mark.asyncio
    async def test_set_led_brightness_sends_form_encoded_value(
        self, eeros_api, mock_session, caplog
    ):
        """Test set_led_brightness PUTs form-encoded led_brightness without warning.

        The write is live-verified, so it must not carry the
        uncharacterised-write warning.
        """
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await eeros_api.set_led_brightness("network_123", "eero_001", 50)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["data"] == {"led_brightness": "50"}
        assert not any("not been fully characterised" in m for m in caplog.messages)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("brightness", [-1, 101, 3.5])
    async def test_set_led_brightness_rejects_out_of_range(self, eeros_api, brightness):
        """Test set_led_brightness rejects values outside [0, 100] or non-ints."""
        with pytest.raises(EeroValidationException):
            await eeros_api.set_led_brightness("network_123", "eero_001", brightness)

    @pytest.mark.asyncio
    async def test_set_led_brightness_not_authenticated(self, eeros_api):
        """Test set_led_brightness raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.set_led_brightness("network_123", "eero_001", 50)


class TestEerosAPISetLocation:
    """Tests for set_location method."""

    @pytest.mark.asyncio
    async def test_set_location_sends_form_encoded_location(self, eeros_api, mock_session, caplog):
        """Test set_location PUTs form-encoded location to the eero's own URL and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await eeros_api.set_location("network_123", "eero_001", "Living Room")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/eeros/eero_001")
        assert call_args.kwargs["data"] == {"location": "Living Room"}
        assert any("set location for eero" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_location_not_authenticated(self, eeros_api):
        """Test set_location raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.set_location("network_123", "eero_001", "Office")


class TestEerosAPINightlightGet:
    """Tests for getting nightlight settings."""

    @pytest.mark.asyncio
    async def test_get_nightlight_uses_parent_url(self, eeros_api, mock_session):
        """Test get_nightlight uses the nightlight URL from parent without an extra read."""
        nightlight_response = api_success_response({"enabled": True})
        mock_session.request.return_value = create_mock_response(200, nightlight_response)
        parent = {"nightlight": {"url": "/2.2/eeros/eero_beacon/nightlight"}}

        result = await eeros_api.get_nightlight("network_123", "eero_beacon", parent=parent)

        assert result["data"]["enabled"] is True
        assert mock_session.request.call_count == 1
        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.2/eeros/eero_beacon/nightlight")

    @pytest.mark.asyncio
    async def test_get_nightlight_discovers_url_via_one_get(self, eeros_api, mock_session):
        """Test get_nightlight falls back to a single GET of the eero when no parent is given."""
        eero_response = api_success_response(
            {"serial": "ABC123", "nightlight": {"url": "/2.2/eeros/eero_beacon/nightlight"}}
        )
        nightlight_response = api_success_response({"enabled": False})
        _queue(
            mock_session,
            create_mock_response(200, eero_response),
            create_mock_response(200, nightlight_response),
        )

        result = await eeros_api.get_nightlight("network_123", "eero_beacon")

        assert result["data"]["enabled"] is False
        assert mock_session.request.call_count == 2
        first_call, second_call = mock_session.request.call_args_list
        assert first_call.args[1].endswith("/2.2/eeros/eero_beacon")
        assert second_call.args[1].endswith("/2.2/eeros/eero_beacon/nightlight")

    @pytest.mark.asyncio
    async def test_get_nightlight_raises_when_unavailable(self, eeros_api, mock_session):
        """Test get_nightlight raises EeroFeatureUnavailableException with no nightlight field."""
        eero_response = api_success_response({"serial": "ABC123"})
        mock_session.request.return_value = create_mock_response(200, eero_response)

        with pytest.raises(EeroFeatureUnavailableException):
            await eeros_api.get_nightlight("network_123", "eero_no_beacon")

    @pytest.mark.asyncio
    async def test_get_nightlight_not_authenticated(self, eeros_api):
        """Test get_nightlight raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.get_nightlight("network_123", "eero_beacon")


class TestEerosAPINightlightSet:
    """Tests for setting nightlight settings."""

    @pytest.mark.asyncio
    async def test_set_nightlight_sends_only_supplied_fields(self, eeros_api, mock_session, caplog):
        """Test set_nightlight PUTs exactly enabled/brightness_percentage/schedule when given."""
        parent = {"nightlight": {"url": "/2.2/eeros/eero_beacon/nightlight"}}
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await eeros_api.set_nightlight(
                "network_123",
                "eero_beacon",
                enabled=True,
                brightness_percentage=60,
                schedule={"on": "20:00", "off": "06:00"},
                parent=parent,
            )

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/eeros/eero_beacon/nightlight")
        assert call_args.kwargs["json"] == {
            "enabled": True,
            "brightness_percentage": 60,
            "schedule": {"on": "20:00", "off": "06:00"},
        }
        assert any("set nightlight for eero" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_nightlight_does_not_mutate_parent(self, eeros_api, mock_session):
        """Test set_nightlight never mutates the parent envelope it reads."""
        parent = {"nightlight": {"url": "/2.2/eeros/eero_beacon/nightlight"}}
        parent_copy = copy.deepcopy(parent)
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await eeros_api.set_nightlight("network_123", "eero_beacon", enabled=True, parent=parent)

        assert parent == parent_copy

    @pytest.mark.asyncio
    async def test_set_nightlight_requires_at_least_one_field(self, eeros_api):
        """Test set_nightlight rejects a call with no fields supplied."""
        with pytest.raises(EeroValidationException):
            await eeros_api.set_nightlight(
                "network_123", "eero_beacon", parent={"nightlight": {"url": "/x"}}
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("brightness", [-1, 101])
    async def test_set_nightlight_rejects_out_of_range_brightness(self, eeros_api, brightness):
        """Test set_nightlight rejects an out-of-range brightness_percentage."""
        with pytest.raises(EeroValidationException):
            await eeros_api.set_nightlight(
                "network_123",
                "eero_beacon",
                brightness_percentage=brightness,
                parent={"nightlight": {"url": "/x"}},
            )

    @pytest.mark.asyncio
    async def test_set_nightlight_raises_when_unavailable(self, eeros_api, mock_session):
        """Test set_nightlight raises EeroFeatureUnavailableException with no nightlight."""
        eero_response = api_success_response({"serial": "ABC123"})
        mock_session.request.return_value = create_mock_response(200, eero_response)

        with pytest.raises(EeroFeatureUnavailableException):
            await eeros_api.set_nightlight("network_123", "eero_no_beacon", enabled=True)

    @pytest.mark.asyncio
    async def test_set_nightlight_not_authenticated(self, eeros_api):
        """Test set_nightlight raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.set_nightlight("network_123", "eero_beacon", enabled=True)


class TestEerosAPINightlightConvenience:
    """Tests for nightlight convenience methods."""

    @pytest.mark.asyncio
    async def test_set_nightlight_brightness_convenience(self, eeros_api, mock_session):
        """Test set_nightlight_brightness convenience method forwards brightness_percentage."""
        parent = {"nightlight": {"url": "/2.2/eeros/eero_beacon/nightlight"}}
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        result = await eeros_api.set_nightlight_brightness(
            "network_123", "eero_beacon", 80, parent=parent
        )

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"brightness_percentage": 80}

    @pytest.mark.asyncio
    async def test_set_nightlight_schedule_convenience(self, eeros_api, mock_session):
        """Test set_nightlight_schedule convenience method forwards schedule unchanged."""
        parent = {"nightlight": {"url": "/2.2/eeros/eero_beacon/nightlight"}}
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        schedule = {"enabled": True, "on": "21:00", "off": "07:00"}

        result = await eeros_api.set_nightlight_schedule(
            "network_123", "eero_beacon", schedule, parent=parent
        )

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"schedule": schedule}


class TestEerosAPIConnections:
    """Tests for get_connections method."""

    @pytest.mark.asyncio
    async def test_get_connections_uses_default_template(self, eeros_api, mock_session):
        """Test get_connections GETs the connections link built from the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response([]))

        result = await eeros_api.get_connections("network_123", "eero_001")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/eeros/eero_001/connections")

    @pytest.mark.asyncio
    async def test_get_connections_prefers_parent_link(self, eeros_api, mock_session):
        """Test get_connections uses the eero's published connections link."""
        mock_session.request.return_value = create_mock_response(200, api_success_response([]))
        parent = {"resources": {"connections": "/2.3/eeros/eero_001/connections"}}

        await eeros_api.get_connections("network_123", "eero_001", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/eeros/eero_001/connections")

    @pytest.mark.asyncio
    async def test_get_connections_not_authenticated(self, eeros_api):
        """Test get_connections raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.get_connections("network_123", "eero_001")


class TestEerosAPINodeAction:
    """Tests for node_action method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action", ["POWER_CYCLE_ALL_PORTS", "POWER_CYCLE_ALL_PORTS_AND_REBOOT"]
    )
    async def test_node_action_sends_json(self, eeros_api, mock_session, caplog, action):
        """Test node_action POSTs the action and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await eeros_api.node_action("eero_001", action)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/eeros/eero_001/action")
        assert call_args.kwargs["json"] == {"action": action}
        assert any("node action" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_node_action_prefers_parent_link(self, eeros_api, mock_session):
        """Test node_action uses the eero's published action link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"action": "/2.3/eeros/eero_001/action"}}

        await eeros_api.node_action("eero_001", "POWER_CYCLE_ALL_PORTS", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/eeros/eero_001/action")

    @pytest.mark.asyncio
    async def test_node_action_rejects_invalid_action(self, eeros_api):
        """Test node_action rejects an undeclared action value."""
        with pytest.raises(EeroValidationException):
            await eeros_api.node_action("eero_001", "REBOOT")

    @pytest.mark.asyncio
    async def test_node_action_not_authenticated(self, eeros_api):
        """Test node_action raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.node_action("eero_001", "POWER_CYCLE_ALL_PORTS")


class TestEerosAPIPortAction:
    """Tests for port_action method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "action",
        [
            "ENABLE_DATA",
            "DISABLE_DATA",
            "ENABLE_POE",
            "DISABLE_POE",
            "ENABLE_PORT",
            "DISABLE_PORT",
            "RESTART_POWER",
            "ENABLE_PORT_SECURITY",
            "DISABLE_PORT_SECURITY",
        ],
    )
    async def test_port_action_sends_json(self, eeros_api, mock_session, caplog, action):
        """Test port_action POSTs the action to the port's action sub-resource and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await eeros_api.port_action("eero_001", "1", action)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/eeros/eero_001/ports/1/action")
        assert call_args.kwargs["json"] == {"action": action}
        assert any("port action" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_port_action_rejects_invalid_action(self, eeros_api):
        """Test port_action rejects an undeclared action value."""
        with pytest.raises(EeroValidationException):
            await eeros_api.port_action("eero_001", "1", "DISABLE_EVERYTHING")

    @pytest.mark.asyncio
    async def test_port_action_not_authenticated(self, eeros_api):
        """Test port_action raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.port_action("eero_001", "1", "ENABLE_DATA")


class TestEerosAPILedCycle:
    """Tests for led_cycle method."""

    @pytest.mark.asyncio
    async def test_led_cycle_sends_form_encoded_body(self, eeros_api, mock_session, caplog):
        """Test led_cycle POSTs form-encoded colors/duration/time_per_color and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await eeros_api.led_cycle(
                "eero-serial-placeholder",
                colors=["red", "green"],
                duration="10",
                time_per_color="5",
            )

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/eeros/eero-serial-placeholder/led_cycle")
        assert call_args.kwargs["data"] == {
            "colors[]": ["red", "green"],
            "duration": "10",
            "time_per_color": "5",
        }
        assert any("cycle LED for eero" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_led_cycle_not_authenticated(self, eeros_api):
        """Test led_cycle raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.led_cycle(
                "eero-serial-placeholder", colors=["red"], duration="1", time_per_color="1"
            )


class TestEerosAPINightlightOverride:
    """Tests for nightlight_override method."""

    @pytest.mark.asyncio
    async def test_nightlight_override_sends_form_encoded_value(
        self, eeros_api, mock_session, caplog
    ):
        """Test nightlight_override POSTs form-encoded brightness_percentage and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await eeros_api.nightlight_override("eero_001", brightness_percentage=42)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/eeros/eero_001/nightlight/override")
        assert call_args.kwargs["data"] == {"brightness_percentage": "42"}
        assert any("override nightlight preview for eero" in message for message in caplog.messages)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("brightness", [-1, 101, 3.5])
    async def test_nightlight_override_rejects_out_of_range(self, eeros_api, brightness):
        """Test nightlight_override rejects values outside [0, 100] or non-ints."""
        with pytest.raises(EeroValidationException):
            await eeros_api.nightlight_override("eero_001", brightness_percentage=brightness)

    @pytest.mark.asyncio
    async def test_nightlight_override_not_authenticated(self, eeros_api):
        """Test nightlight_override raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.nightlight_override("eero_001", brightness_percentage=50)


class TestEerosAPIGetEeroSupport:
    """Tests for get_eero_support method."""

    @pytest.mark.asyncio
    async def test_get_eero_support_returns_raw_response(self, eeros_api, mock_session):
        """Test get_eero_support GETs the support sub-resource."""
        expected = {"diagnostics": []}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(expected)
        )

        result = await eeros_api.get_eero_support("eero-serial-placeholder")

        assert result["data"] == expected
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/eeros/eero-serial-placeholder/support")

    @pytest.mark.asyncio
    async def test_get_eero_support_raises_not_found(self, eeros_api, mock_session):
        """Test get_eero_support surfaces the observed 404 on nodes without diagnostics."""
        mock_session.request.return_value = create_mock_response(
            404, api_error_response(404, "error.eero.support_not_found")
        )

        with pytest.raises(EeroNotFoundException):
            await eeros_api.get_eero_support("eero-serial-placeholder")

    @pytest.mark.asyncio
    async def test_get_eero_support_not_authenticated(self, eeros_api):
        """Test get_eero_support raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.get_eero_support("eero-serial-placeholder")
