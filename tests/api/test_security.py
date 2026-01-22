"""Tests for SecurityAPI module.

Tests cover security settings like WPA3, band steering, UPnP, IPv6, and Thread.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.security import SecurityAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestSecurityAPIInit:
    """Tests for SecurityAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = SecurityAPI(auth_api)
        assert api._auth_api is auth_api


class TestSecurityAPIGetSettings:
    """Tests for get_security_settings method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_security_settings_returns_raw_response(self, security_api, mock_session):
        """Test getting security settings returns raw response."""
        network_data = {
            "wpa3": True,
            "band_steering": True,
            "upnp": False,
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await security_api.get_security_settings("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_security_settings_not_authenticated(self, security_api):
        """Test get_security_settings raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await security_api.get_security_settings("network_123")


class TestSecurityAPISetWPA3:
    """Tests for set_wpa3 method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_wpa3_returns_raw_response(self, security_api, mock_session):
        """Test setting WPA3 returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_wpa3("network_123", True)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"wpa3": True}

    @pytest.mark.asyncio
    async def test_set_wpa3_not_authenticated(self, security_api):
        """Test set_wpa3 raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_wpa3("network_123", True)


class TestSecurityAPISetBandSteering:
    """Tests for set_band_steering method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_band_steering_returns_raw_response(self, security_api, mock_session):
        """Test setting band steering returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_band_steering("network_123", True)

        assert "meta" in result


class TestSecurityAPISetUPnP:
    """Tests for set_upnp method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_upnp_returns_raw_response(self, security_api, mock_session):
        """Test setting UPnP returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_upnp("network_123", True)

        assert "meta" in result


class TestSecurityAPIConfigure:
    """Tests for configure_security method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_configure_security_returns_raw_response(self, security_api, mock_session):
        """Test configure_security returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await security_api.configure_security("network_123", wpa3=True, upnp=False)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_configure_security_not_authenticated(self, security_api):
        """Test configure_security raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.configure_security("network_123", wpa3=True)
