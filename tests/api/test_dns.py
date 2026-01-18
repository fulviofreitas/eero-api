"""Tests for DnsAPI module.

Tests cover:
- Getting DNS settings
- Setting DNS caching
- Custom DNS server configuration
- DNS mode presets (Google, Cloudflare, OpenDNS)
- IPv6 DNS settings
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.dns import DnsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response

# ========================== DnsAPI Init Tests ==========================


class TestDnsAPIInit:
    """Tests for DnsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = DnsAPI(auth_api)

        assert api._auth_api is auth_api


# ========================== Get DNS Settings Tests ==========================


class TestDnsAPIGetSettings:
    """Tests for get_dns_settings method."""

    @pytest.fixture
    def dns_api(self, mock_session):
        """Create a DnsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DnsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_dns_settings_basic(self, dns_api, mock_session):
        """Test getting basic DNS settings."""
        network_data = {
            "dns_caching": True,
            "ipv6_upstream": False,
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await dns_api.get_dns_settings("network_123")

        assert result["dns_caching"] is True
        assert result["ipv6_dns"] is False
        assert result["dns_mode"] == "auto"
        assert result["custom_dns"] == []

    @pytest.mark.asyncio
    async def test_get_dns_settings_with_dns_object(self, dns_api, mock_session):
        """Test getting DNS settings with dns object in response."""
        network_data = {
            "dns": {
                "mode": "custom",
                "servers": ["8.8.8.8", "8.8.4.4"],
                "caching": True,
            },
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await dns_api.get_dns_settings("network_123")

        assert result["dns_mode"] == "custom"
        assert result["custom_dns"] == ["8.8.8.8", "8.8.4.4"]
        assert result["dns_caching"] is True

    @pytest.mark.asyncio
    async def test_get_dns_settings_with_custom_dns_list(self, dns_api, mock_session):
        """Test getting DNS settings with custom_dns list."""
        network_data = {
            "custom_dns": ["1.1.1.1", "1.0.0.1"],
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await dns_api.get_dns_settings("network_123")

        assert result["dns_mode"] == "custom"
        assert result["custom_dns"] == ["1.1.1.1", "1.0.0.1"]

    @pytest.mark.asyncio
    async def test_get_dns_settings_not_authenticated(self, dns_api):
        """Test get_dns_settings raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await dns_api.get_dns_settings("network_123")


# ========================== Set DNS Caching Tests ==========================


class TestDnsAPISetCaching:
    """Tests for set_dns_caching method."""

    @pytest.fixture
    def dns_api(self, mock_session):
        """Create a DnsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DnsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_enable_dns_caching(self, dns_api, mock_session):
        """Test enabling DNS caching."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_caching("network_123", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"dns_caching": True}

    @pytest.mark.asyncio
    async def test_disable_dns_caching(self, dns_api, mock_session):
        """Test disabling DNS caching."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_caching("network_123", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"dns_caching": False}

    @pytest.mark.asyncio
    async def test_set_dns_caching_not_authenticated(self, dns_api):
        """Test set_dns_caching raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dns_api.set_dns_caching("network_123", True)


# ========================== Set Custom DNS Tests ==========================


class TestDnsAPISetCustomDNS:
    """Tests for set_custom_dns method."""

    @pytest.fixture
    def dns_api(self, mock_session):
        """Create a DnsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DnsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_custom_dns_single(self, dns_api, mock_session):
        """Test setting a single custom DNS server."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_custom_dns("network_123", ["8.8.8.8"])

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["8.8.8.8"]}

    @pytest.mark.asyncio
    async def test_set_custom_dns_two_servers(self, dns_api, mock_session):
        """Test setting two custom DNS servers."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_custom_dns("network_123", ["8.8.8.8", "8.8.4.4"])

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["8.8.8.8", "8.8.4.4"]}

    @pytest.mark.asyncio
    async def test_set_custom_dns_limits_to_two(self, dns_api, mock_session):
        """Test that more than 2 DNS servers are limited."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_custom_dns("network_123", ["8.8.8.8", "8.8.4.4", "1.1.1.1"])

        assert result is True
        call_args = mock_session.request.call_args
        # Should only include first 2 servers
        assert call_args.kwargs["json"] == {"custom_dns": ["8.8.8.8", "8.8.4.4"]}

    @pytest.mark.asyncio
    async def test_set_custom_dns_not_authenticated(self, dns_api):
        """Test set_custom_dns raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dns_api.set_custom_dns("network_123", ["8.8.8.8"])


# ========================== Clear Custom DNS Tests ==========================


class TestDnsAPIClearCustomDNS:
    """Tests for clear_custom_dns method."""

    @pytest.fixture
    def dns_api(self, mock_session):
        """Create a DnsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DnsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_clear_custom_dns(self, dns_api, mock_session):
        """Test clearing custom DNS servers."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.clear_custom_dns("network_123")

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": []}


# ========================== Set DNS Mode Tests ==========================


class TestDnsAPISetMode:
    """Tests for set_dns_mode method."""

    @pytest.fixture
    def dns_api(self, mock_session):
        """Create a DnsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DnsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_dns_mode_cloudflare(self, dns_api, mock_session):
        """Test setting DNS mode to Cloudflare."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_mode("network_123", "cloudflare")

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["1.1.1.1", "1.0.0.1"]}

    @pytest.mark.asyncio
    async def test_set_dns_mode_google(self, dns_api, mock_session):
        """Test setting DNS mode to Google."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_mode("network_123", "google")

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["8.8.8.8", "8.8.4.4"]}

    @pytest.mark.asyncio
    async def test_set_dns_mode_opendns(self, dns_api, mock_session):
        """Test setting DNS mode to OpenDNS."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_mode("network_123", "opendns")

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["208.67.222.222", "208.67.220.220"]}

    @pytest.mark.asyncio
    async def test_set_dns_mode_auto(self, dns_api, mock_session):
        """Test setting DNS mode to auto."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_mode("network_123", "auto")

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": []}

    @pytest.mark.asyncio
    async def test_set_dns_mode_custom(self, dns_api, mock_session):
        """Test setting DNS mode to custom with servers."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_mode(
            "network_123", "custom", custom_servers=["9.9.9.9", "149.112.112.112"]
        )

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["9.9.9.9", "149.112.112.112"]}

    @pytest.mark.asyncio
    async def test_set_dns_mode_invalid(self, dns_api, mock_session):
        """Test setting invalid DNS mode returns False."""
        result = await dns_api.set_dns_mode("network_123", "invalid_mode")

        assert result is False

    @pytest.mark.asyncio
    async def test_set_dns_mode_not_authenticated(self, dns_api):
        """Test set_dns_mode raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dns_api.set_dns_mode("network_123", "google")


# ========================== Set IPv6 DNS Tests ==========================


class TestDnsAPISetIPv6:
    """Tests for set_ipv6_dns method."""

    @pytest.fixture
    def dns_api(self, mock_session):
        """Create a DnsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DnsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_enable_ipv6_dns(self, dns_api, mock_session):
        """Test enabling IPv6 DNS."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_ipv6_dns("network_123", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"ipv6_upstream": True}

    @pytest.mark.asyncio
    async def test_disable_ipv6_dns(self, dns_api, mock_session):
        """Test disabling IPv6 DNS."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_ipv6_dns("network_123", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"ipv6_upstream": False}

    @pytest.mark.asyncio
    async def test_set_ipv6_dns_not_authenticated(self, dns_api):
        """Test set_ipv6_dns raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dns_api.set_ipv6_dns("network_123", True)
