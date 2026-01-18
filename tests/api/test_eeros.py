"""Tests for EerosAPI module.

Tests cover:
- Getting eero device list
- Getting eero device details
- Rebooting eero devices
- LED control (on/off, brightness)
- Nightlight control (enable, brightness, schedule)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.eeros import EerosAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response

# ========================== EerosAPI Init Tests ==========================


class TestEerosAPIInit:
    """Tests for EerosAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = EerosAPI(auth_api)

        assert api._auth_api is auth_api


# ========================== GetEeros Tests ==========================


class TestEerosAPIGetEeros:
    """Tests for get_eeros method."""

    @pytest.fixture
    def eeros_api(self, mock_session):
        """Create an EerosAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return EerosAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_eeros_success(self, eeros_api, mock_session, sample_eero_data):
        """Test successful eeros retrieval."""
        eeros_list = [sample_eero_data]
        mock_response = create_mock_response(200, api_success_response(eeros_list))
        mock_session.request.return_value = mock_response

        result = await eeros_api.get_eeros("network_123")

        assert len(result) == 1
        assert result[0]["serial"] == "ABC123456789"

    @pytest.mark.asyncio
    async def test_get_eeros_nested_data_format(self, eeros_api, mock_session, sample_eero_data):
        """Test eeros retrieval with nested data format."""
        mock_response = create_mock_response(
            200, api_success_response({"data": [sample_eero_data]})
        )
        mock_session.request.return_value = mock_response

        result = await eeros_api.get_eeros("network_123")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_eeros_empty_list(self, eeros_api, mock_session):
        """Test eeros retrieval with empty list."""
        mock_response = create_mock_response(200, api_success_response([]))
        mock_session.request.return_value = mock_response

        result = await eeros_api.get_eeros("network_123")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_eeros_not_authenticated(self, eeros_api):
        """Test get_eeros raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await eeros_api.get_eeros("network_123")


# ========================== GetEero Tests ==========================


class TestEerosAPIGetEero:
    """Tests for get_eero method."""

    @pytest.fixture
    def eeros_api(self, mock_session):
        """Create an EerosAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return EerosAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_eero_success(self, eeros_api, mock_session, sample_eero_data):
        """Test successful eero retrieval."""
        mock_response = create_mock_response(200, api_success_response(sample_eero_data))
        mock_session.request.return_value = mock_response

        result = await eeros_api.get_eero("network_123", "eero_001")

        assert result["serial"] == "ABC123456789"
        assert result["model"] == "eero Pro 6E"

    @pytest.mark.asyncio
    async def test_get_eero_not_authenticated(self, eeros_api):
        """Test get_eero raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.get_eero("network_123", "eero_001")


# ========================== Reboot Tests ==========================


class TestEerosAPIReboot:
    """Tests for reboot_eero method."""

    @pytest.fixture
    def eeros_api(self, mock_session):
        """Create an EerosAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return EerosAPI(auth_api)

    @pytest.mark.asyncio
    async def test_reboot_success(self, eeros_api, mock_session):
        """Test successful eero reboot."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.reboot_eero("network_123", "eero_001")

        assert result is True

    @pytest.mark.asyncio
    async def test_reboot_not_authenticated(self, eeros_api):
        """Test reboot raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.reboot_eero("network_123", "eero_001")

    @pytest.mark.asyncio
    async def test_reboot_sends_empty_body(self, eeros_api, mock_session):
        """Test that reboot sends empty JSON body."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        await eeros_api.reboot_eero("network_123", "eero_001")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {}


# ========================== LED Status Tests ==========================


class TestEerosAPILedStatus:
    """Tests for LED status methods."""

    @pytest.fixture
    def eeros_api(self, mock_session):
        """Create an EerosAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return EerosAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_led_status(self, eeros_api, mock_session):
        """Test getting LED status."""
        eero_data = {
            "serial": "ABC123",
            "led_on": True,
            "led_brightness": 75,
        }
        mock_response = create_mock_response(200, api_success_response(eero_data))
        mock_session.request.return_value = mock_response

        result = await eeros_api.get_led_status("network_123", "eero_001")

        assert result["led_on"] is True
        assert result["led_brightness"] == 75

    @pytest.mark.asyncio
    async def test_get_led_status_defaults(self, eeros_api, mock_session):
        """Test getting LED status with default values."""
        eero_data = {"serial": "ABC123"}  # No LED fields
        mock_response = create_mock_response(200, api_success_response(eero_data))
        mock_session.request.return_value = mock_response

        result = await eeros_api.get_led_status("network_123", "eero_001")

        assert result["led_on"] is True  # Default
        assert result["led_brightness"] is None

    @pytest.mark.asyncio
    async def test_get_led_status_not_authenticated(self, eeros_api):
        """Test get_led_status raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.get_led_status("network_123", "eero_001")


# ========================== LED Control Tests ==========================


class TestEerosAPILedControl:
    """Tests for LED control methods."""

    @pytest.fixture
    def eeros_api(self, mock_session):
        """Create an EerosAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return EerosAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_led_on(self, eeros_api, mock_session):
        """Test turning LED on."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_led("network_123", "eero_001", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"led_on": True}

    @pytest.mark.asyncio
    async def test_set_led_off(self, eeros_api, mock_session):
        """Test turning LED off."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_led("network_123", "eero_001", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"led_on": False}

    @pytest.mark.asyncio
    async def test_set_led_not_authenticated(self, eeros_api):
        """Test set_led raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.set_led("network_123", "eero_001", True)


# ========================== LED Brightness Tests ==========================


class TestEerosAPILedBrightness:
    """Tests for LED brightness control."""

    @pytest.fixture
    def eeros_api(self, mock_session):
        """Create an EerosAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return EerosAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_led_brightness(self, eeros_api, mock_session):
        """Test setting LED brightness."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_led_brightness("network_123", "eero_001", 50)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"led_brightness": 50}

    @pytest.mark.asyncio
    async def test_set_led_brightness_clamps_min(self, eeros_api, mock_session):
        """Test that brightness is clamped to minimum 0."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        await eeros_api.set_led_brightness("network_123", "eero_001", -10)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"led_brightness": 0}

    @pytest.mark.asyncio
    async def test_set_led_brightness_clamps_max(self, eeros_api, mock_session):
        """Test that brightness is clamped to maximum 100."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        await eeros_api.set_led_brightness("network_123", "eero_001", 150)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"led_brightness": 100}

    @pytest.mark.asyncio
    async def test_set_led_brightness_not_authenticated(self, eeros_api):
        """Test set_led_brightness raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.set_led_brightness("network_123", "eero_001", 50)


# ========================== Nightlight Get Tests ==========================


class TestEerosAPINightlightGet:
    """Tests for getting nightlight settings."""

    @pytest.fixture
    def eeros_api(self, mock_session):
        """Create an EerosAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return EerosAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_nightlight_supported(self, eeros_api, mock_session):
        """Test getting nightlight settings when supported."""
        eero_data = {
            "serial": "ABC123",
            "nightlight": {
                "enabled": True,
                "brightness": 75,
                "brightness_percentage": 75,
                "ambient_light_enabled": False,
                "schedule": {"on": "20:00", "off": "06:00"},
            },
        }
        mock_response = create_mock_response(200, api_success_response(eero_data))
        mock_session.request.return_value = mock_response

        result = await eeros_api.get_nightlight("network_123", "eero_beacon")

        assert result["supported"] is True
        assert result["enabled"] is True
        assert result["brightness"] == 75
        assert result["ambient_light_enabled"] is False
        assert result["schedule"]["on"] == "20:00"

    @pytest.mark.asyncio
    async def test_get_nightlight_not_supported(self, eeros_api, mock_session):
        """Test getting nightlight settings when not supported."""
        eero_data = {"serial": "ABC123"}  # No nightlight field
        mock_response = create_mock_response(200, api_success_response(eero_data))
        mock_session.request.return_value = mock_response

        result = await eeros_api.get_nightlight("network_123", "eero_pro")

        assert result["supported"] is False
        assert result["enabled"] is False
        assert result["brightness"] == 0

    @pytest.mark.asyncio
    async def test_get_nightlight_not_authenticated(self, eeros_api):
        """Test get_nightlight raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.get_nightlight("network_123", "eero_beacon")


# ========================== Nightlight Set Tests ==========================


class TestEerosAPINightlightSet:
    """Tests for setting nightlight settings."""

    @pytest.fixture
    def eeros_api(self, mock_session):
        """Create an EerosAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return EerosAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_nightlight_enabled(self, eeros_api, mock_session):
        """Test enabling nightlight."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_nightlight("network_123", "eero_beacon", enabled=True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"nightlight": {"enabled": True}}

    @pytest.mark.asyncio
    async def test_set_nightlight_brightness(self, eeros_api, mock_session):
        """Test setting nightlight brightness."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_nightlight("network_123", "eero_beacon", brightness=50)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"nightlight": {"brightness": 50}}

    @pytest.mark.asyncio
    async def test_set_nightlight_brightness_clamped(self, eeros_api, mock_session):
        """Test that nightlight brightness is clamped to 0-100."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        await eeros_api.set_nightlight("network_123", "eero_beacon", brightness=150)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"nightlight": {"brightness": 100}}

    @pytest.mark.asyncio
    async def test_set_nightlight_schedule(self, eeros_api, mock_session):
        """Test setting nightlight schedule."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_nightlight(
            "network_123",
            "eero_beacon",
            schedule_enabled=True,
            schedule_on="20:00",
            schedule_off="06:00",
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["nightlight"]["schedule"]["enabled"] is True
        assert payload["nightlight"]["schedule"]["on"] == "20:00"
        assert payload["nightlight"]["schedule"]["off"] == "06:00"

    @pytest.mark.asyncio
    async def test_set_nightlight_ambient_light(self, eeros_api, mock_session):
        """Test setting ambient light mode."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_nightlight(
            "network_123", "eero_beacon", ambient_light_enabled=True
        )

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"nightlight": {"ambient_light_enabled": True}}

    @pytest.mark.asyncio
    async def test_set_nightlight_multiple_settings(self, eeros_api, mock_session):
        """Test setting multiple nightlight settings at once."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_nightlight(
            "network_123",
            "eero_beacon",
            enabled=True,
            brightness=75,
            ambient_light_enabled=False,
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["nightlight"]["enabled"] is True
        assert payload["nightlight"]["brightness"] == 75
        assert payload["nightlight"]["ambient_light_enabled"] is False

    @pytest.mark.asyncio
    async def test_set_nightlight_no_settings_returns_false(self, eeros_api, mock_session):
        """Test that setting no nightlight settings returns False."""
        result = await eeros_api.set_nightlight("network_123", "eero_beacon")

        assert result is False

    @pytest.mark.asyncio
    async def test_set_nightlight_not_authenticated(self, eeros_api):
        """Test set_nightlight raises when not authenticated."""
        eeros_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await eeros_api.set_nightlight("network_123", "eero_beacon", enabled=True)


# ========================== Nightlight Convenience Methods ==========================


class TestEerosAPINightlightConvenience:
    """Tests for nightlight convenience methods."""

    @pytest.fixture
    def eeros_api(self, mock_session):
        """Create an EerosAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return EerosAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_nightlight_brightness_convenience(self, eeros_api, mock_session):
        """Test set_nightlight_brightness convenience method."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_nightlight_brightness("network_123", "eero_beacon", 80)

        assert result is True

    @pytest.mark.asyncio
    async def test_set_nightlight_schedule_convenience(self, eeros_api, mock_session):
        """Test set_nightlight_schedule convenience method."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await eeros_api.set_nightlight_schedule(
            "network_123", "eero_beacon", True, "21:00", "07:00"
        )

        assert result is True
