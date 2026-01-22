"""Tests for DnsAPI module.

Tests cover:
- Getting DNS settings (raw response)
- Setting DNS caching
- Custom DNS server configuration
- DNS mode presets
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.dns import DnsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestDnsAPIInit:
    """Tests for DnsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = DnsAPI(auth_api)

        assert api._auth_api is auth_api


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
    async def test_get_dns_settings_returns_raw_response(self, dns_api, mock_session):
        """Test getting DNS settings returns raw response."""
        network_data = {
            "dns_caching": True,
            "ipv6_upstream": False,
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await dns_api.get_dns_settings("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_dns_settings_not_authenticated(self, dns_api):
        """Test get_dns_settings raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await dns_api.get_dns_settings("network_123")


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
    async def test_set_dns_caching_returns_raw_response(self, dns_api, mock_session):
        """Test setting DNS caching returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_caching("network_123", True)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"dns_caching": True}

    @pytest.mark.asyncio
    async def test_set_dns_caching_not_authenticated(self, dns_api):
        """Test set_dns_caching raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dns_api.set_dns_caching("network_123", True)


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
    async def test_set_custom_dns_returns_raw_response(self, dns_api, mock_session):
        """Test setting custom DNS returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_custom_dns("network_123", ["8.8.8.8"])

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["8.8.8.8"]}

    @pytest.mark.asyncio
    async def test_set_custom_dns_limits_to_two(self, dns_api, mock_session):
        """Test that more than 2 DNS servers are limited."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_custom_dns("network_123", ["8.8.8.8", "8.8.4.4", "1.1.1.1"])

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["8.8.8.8", "8.8.4.4"]}

    @pytest.mark.asyncio
    async def test_set_custom_dns_not_authenticated(self, dns_api):
        """Test set_custom_dns raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dns_api.set_custom_dns("network_123", ["8.8.8.8"])


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
    async def test_clear_custom_dns_returns_raw_response(self, dns_api, mock_session):
        """Test clearing custom DNS returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await dns_api.clear_custom_dns("network_123")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": []}


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
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_mode("network_123", "cloudflare")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["1.1.1.1", "1.0.0.1"]}

    @pytest.mark.asyncio
    async def test_set_dns_mode_google(self, dns_api, mock_session):
        """Test setting DNS mode to Google."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_mode("network_123", "google")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": ["8.8.8.8", "8.8.4.4"]}

    @pytest.mark.asyncio
    async def test_set_dns_mode_auto(self, dns_api, mock_session):
        """Test setting DNS mode to auto."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_mode("network_123", "auto")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"custom_dns": []}

    @pytest.mark.asyncio
    async def test_set_dns_mode_invalid_returns_raw(self, dns_api, mock_session):
        """Test setting invalid DNS mode returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_dns_mode("network_123", "invalid_mode")

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_dns_mode_not_authenticated(self, dns_api):
        """Test set_dns_mode raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dns_api.set_dns_mode("network_123", "google")


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
    async def test_set_ipv6_dns_returns_raw_response(self, dns_api, mock_session):
        """Test setting IPv6 DNS returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await dns_api.set_ipv6_dns("network_123", True)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"ipv6_upstream": True}

    @pytest.mark.asyncio
    async def test_set_ipv6_dns_not_authenticated(self, dns_api):
        """Test set_ipv6_dns raises when not authenticated."""
        dns_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await dns_api.set_ipv6_dns("network_123", True)
