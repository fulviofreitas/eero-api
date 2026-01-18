"""Tests for SecurityAPI module.

Tests cover:
- Getting security settings
- WPA3 configuration
- Band steering control
- UPnP settings
- IPv6 settings
- Thread settings
- Combined security configuration
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.security import SecurityAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response

# ========================== SecurityAPI Init Tests ==========================


class TestSecurityAPIInit:
    """Tests for SecurityAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = SecurityAPI(auth_api)

        assert api._auth_api is auth_api


# ========================== Get Security Settings Tests ==========================


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
    async def test_get_security_settings_basic(self, security_api, mock_session):
        """Test getting basic security settings."""
        network_data = {
            "wpa3": True,
            "band_steering": True,
            "upnp": False,
            "ipv6_upstream": True,
            "ipv6_downstream": True,
            "thread": False,
            "dns_caching": True,
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await security_api.get_security_settings("network_123")

        assert result["wpa3"] is True
        assert result["band_steering"] is True
        assert result["upnp"] is False
        assert result["ipv6_upstream"] is True
        assert result["thread"] is False
        assert result["dns_caching"] is True

    @pytest.mark.asyncio
    async def test_get_security_settings_defaults(self, security_api, mock_session):
        """Test getting security settings with defaults."""
        network_data = {}
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await security_api.get_security_settings("network_123")

        assert result["wpa3"] is False
        assert result["band_steering"] is True  # Default is True
        assert result["upnp"] is True  # Default is True
        assert result["ipv6_upstream"] is False

    @pytest.mark.asyncio
    async def test_get_security_settings_with_security_object(self, security_api, mock_session):
        """Test getting security settings from nested security object."""
        network_data = {
            "security": {
                "wpa3": True,
                "firewall": "strict",
            },
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await security_api.get_security_settings("network_123")

        assert result["wpa3"] is True
        assert result["firewall"] == "strict"

    @pytest.mark.asyncio
    async def test_get_security_settings_not_authenticated(self, security_api):
        """Test get_security_settings raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await security_api.get_security_settings("network_123")


# ========================== Set WPA3 Tests ==========================


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
    async def test_enable_wpa3(self, security_api, mock_session):
        """Test enabling WPA3."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_wpa3("network_123", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"wpa3": True}

    @pytest.mark.asyncio
    async def test_disable_wpa3(self, security_api, mock_session):
        """Test disabling WPA3."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_wpa3("network_123", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"wpa3": False}

    @pytest.mark.asyncio
    async def test_set_wpa3_not_authenticated(self, security_api):
        """Test set_wpa3 raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_wpa3("network_123", True)


# ========================== Set Band Steering Tests ==========================


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
    async def test_enable_band_steering(self, security_api, mock_session):
        """Test enabling band steering."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_band_steering("network_123", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"band_steering": True}

    @pytest.mark.asyncio
    async def test_disable_band_steering(self, security_api, mock_session):
        """Test disabling band steering."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_band_steering("network_123", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"band_steering": False}

    @pytest.mark.asyncio
    async def test_set_band_steering_not_authenticated(self, security_api):
        """Test set_band_steering raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_band_steering("network_123", True)


# ========================== Set UPnP Tests ==========================


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
    async def test_enable_upnp(self, security_api, mock_session):
        """Test enabling UPnP."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_upnp("network_123", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"upnp": True}

    @pytest.mark.asyncio
    async def test_disable_upnp(self, security_api, mock_session):
        """Test disabling UPnP."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_upnp("network_123", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"upnp": False}

    @pytest.mark.asyncio
    async def test_set_upnp_not_authenticated(self, security_api):
        """Test set_upnp raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_upnp("network_123", True)


# ========================== Set IPv6 Tests ==========================


class TestSecurityAPISetIPv6:
    """Tests for set_ipv6 method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_enable_ipv6(self, security_api, mock_session):
        """Test enabling IPv6."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_ipv6("network_123", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {
            "ipv6_upstream": True,
            "ipv6_downstream": True,
        }

    @pytest.mark.asyncio
    async def test_disable_ipv6(self, security_api, mock_session):
        """Test disabling IPv6."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_ipv6("network_123", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {
            "ipv6_upstream": False,
            "ipv6_downstream": False,
        }

    @pytest.mark.asyncio
    async def test_set_ipv6_not_authenticated(self, security_api):
        """Test set_ipv6 raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_ipv6("network_123", True)


# ========================== Set Thread Tests ==========================


class TestSecurityAPISetThread:
    """Tests for set_thread method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_enable_thread(self, security_api, mock_session):
        """Test enabling Thread."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_thread("network_123", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"thread": True}

    @pytest.mark.asyncio
    async def test_disable_thread(self, security_api, mock_session):
        """Test disabling Thread."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.set_thread("network_123", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"thread": False}

    @pytest.mark.asyncio
    async def test_set_thread_not_authenticated(self, security_api):
        """Test set_thread raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.set_thread("network_123", True)


# ========================== Configure Security Tests ==========================


class TestSecurityAPIConfigureSecurity:
    """Tests for configure_security method."""

    @pytest.fixture
    def security_api(self, mock_session):
        """Create a SecurityAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SecurityAPI(auth_api)

    @pytest.mark.asyncio
    async def test_configure_multiple_settings(self, security_api, mock_session):
        """Test configuring multiple security settings at once."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.configure_security(
            "network_123",
            wpa3=True,
            band_steering=True,
            upnp=False,
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["wpa3"] is True
        assert payload["band_steering"] is True
        assert payload["upnp"] is False

    @pytest.mark.asyncio
    async def test_configure_security_with_ipv6(self, security_api, mock_session):
        """Test configuring security with IPv6."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await security_api.configure_security(
            "network_123",
            ipv6=True,
            thread=True,
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["ipv6_upstream"] is True
        assert payload["ipv6_downstream"] is True
        assert payload["thread"] is True

    @pytest.mark.asyncio
    async def test_configure_security_no_settings(self, security_api, mock_session):
        """Test configure_security returns False with no settings."""
        result = await security_api.configure_security("network_123")

        assert result is False

    @pytest.mark.asyncio
    async def test_configure_security_not_authenticated(self, security_api):
        """Test configure_security raises when not authenticated."""
        security_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await security_api.configure_security("network_123", wpa3=True)
