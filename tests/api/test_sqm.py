"""Tests for SqmAPI module (Smart Queue Management).

Tests cover:
- Getting SQM settings
- Enabling/disabling SQM
- Setting bandwidth limits
- Configuring SQM with all options
- Auto mode configuration
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.sqm import SqmAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response

# ========================== SqmAPI Init Tests ==========================


class TestSqmAPIInit:
    """Tests for SqmAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = SqmAPI(auth_api)

        assert api._auth_api is auth_api


# ========================== Get SQM Settings Tests ==========================


class TestSqmAPIGetSettings:
    """Tests for get_sqm_settings method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_sqm_settings_with_sqm_object(self, sqm_api, mock_session):
        """Test getting SQM settings from sqm object."""
        network_data = {
            "sqm": {
                "enabled": True,
                "upload_bandwidth": 100,
                "download_bandwidth": 500,
                "mode": "manual",
            },
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await sqm_api.get_sqm_settings("network_123")

        assert result["enabled"] is True
        assert result["upload_bandwidth"] == 100
        assert result["download_bandwidth"] == 500
        assert result["mode"] == "manual"

    @pytest.mark.asyncio
    async def test_get_sqm_settings_with_sqm_boolean(self, sqm_api, mock_session):
        """Test getting SQM settings when sqm is boolean."""
        network_data = {"sqm": True}
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await sqm_api.get_sqm_settings("network_123")

        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_sqm_settings_from_bandwidth_control(self, sqm_api, mock_session):
        """Test getting SQM settings from bandwidth_control field."""
        network_data = {
            "bandwidth_control": {
                "enabled": True,
                "upload": 50,
                "download": 200,
            },
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await sqm_api.get_sqm_settings("network_123")

        assert result["enabled"] is True
        assert result["upload_bandwidth"] == 50
        assert result["download_bandwidth"] == 200

    @pytest.mark.asyncio
    async def test_get_sqm_settings_from_qos(self, sqm_api, mock_session):
        """Test getting SQM settings from qos field."""
        network_data = {
            "qos": {"enabled": True},
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await sqm_api.get_sqm_settings("network_123")

        assert result["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_sqm_settings_defaults(self, sqm_api, mock_session):
        """Test getting SQM settings with defaults."""
        network_data = {}
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await sqm_api.get_sqm_settings("network_123")

        assert result["enabled"] is False
        assert result["upload_bandwidth"] is None
        assert result["download_bandwidth"] is None
        assert result["mode"] == "auto"

    @pytest.mark.asyncio
    async def test_get_sqm_settings_not_authenticated(self, sqm_api):
        """Test get_sqm_settings raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await sqm_api.get_sqm_settings("network_123")


# ========================== Set SQM Enabled Tests ==========================


class TestSqmAPISetEnabled:
    """Tests for set_sqm_enabled method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_enable_sqm(self, sqm_api, mock_session):
        """Test enabling SQM."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_enabled("network_123", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"sqm": {"enabled": True}}

    @pytest.mark.asyncio
    async def test_disable_sqm(self, sqm_api, mock_session):
        """Test disabling SQM."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_enabled("network_123", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"sqm": {"enabled": False}}

    @pytest.mark.asyncio
    async def test_set_sqm_enabled_not_authenticated(self, sqm_api):
        """Test set_sqm_enabled raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.set_sqm_enabled("network_123", True)


# ========================== Set SQM Bandwidth Tests ==========================


class TestSqmAPISetBandwidth:
    """Tests for set_sqm_bandwidth method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_upload_bandwidth(self, sqm_api, mock_session):
        """Test setting upload bandwidth."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_bandwidth("network_123", upload_mbps=50)

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["enabled"] is True
        assert payload["sqm"]["upload_bandwidth"] == 50

    @pytest.mark.asyncio
    async def test_set_download_bandwidth(self, sqm_api, mock_session):
        """Test setting download bandwidth."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_bandwidth("network_123", download_mbps=200)

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["enabled"] is True
        assert payload["sqm"]["download_bandwidth"] == 200

    @pytest.mark.asyncio
    async def test_set_both_bandwidths(self, sqm_api, mock_session):
        """Test setting both upload and download bandwidth."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_bandwidth("network_123", upload_mbps=100, download_mbps=500)

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["enabled"] is True
        assert payload["sqm"]["upload_bandwidth"] == 100
        assert payload["sqm"]["download_bandwidth"] == 500

    @pytest.mark.asyncio
    async def test_set_sqm_bandwidth_not_authenticated(self, sqm_api):
        """Test set_sqm_bandwidth raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.set_sqm_bandwidth("network_123", upload_mbps=50)


# ========================== Configure SQM Tests ==========================


class TestSqmAPIConfigure:
    """Tests for configure_sqm method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_configure_sqm_enabled_with_bandwidth(self, sqm_api, mock_session):
        """Test configuring SQM enabled with bandwidth."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.configure_sqm(
            "network_123",
            enabled=True,
            upload_mbps=100,
            download_mbps=500,
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["enabled"] is True
        assert payload["sqm"]["upload_bandwidth"] == 100
        assert payload["sqm"]["download_bandwidth"] == 500

    @pytest.mark.asyncio
    async def test_configure_sqm_disabled(self, sqm_api, mock_session):
        """Test configuring SQM disabled ignores bandwidth."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.configure_sqm(
            "network_123",
            enabled=False,
            upload_mbps=100,  # Should be ignored
            download_mbps=500,  # Should be ignored
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["enabled"] is False
        # Bandwidth should not be included when disabled
        assert "upload_bandwidth" not in payload["sqm"]
        assert "download_bandwidth" not in payload["sqm"]

    @pytest.mark.asyncio
    async def test_configure_sqm_not_authenticated(self, sqm_api):
        """Test configure_sqm raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.configure_sqm("network_123", enabled=True)


# ========================== Set SQM Auto Tests ==========================


class TestSqmAPISetAuto:
    """Tests for set_sqm_auto method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_sqm_auto(self, sqm_api, mock_session):
        """Test setting SQM to auto mode."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_auto("network_123")

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["enabled"] is True
        assert payload["sqm"]["mode"] == "auto"

    @pytest.mark.asyncio
    async def test_set_sqm_auto_not_authenticated(self, sqm_api):
        """Test set_sqm_auto raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.set_sqm_auto("network_123")
