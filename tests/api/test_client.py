"""Tests for EeroClient high-level client.

Tests cover:
- Client initialization and configuration
- Cache management and expiry
- Network ID resolution
- Context manager lifecycle
"""

import time
from unittest.mock import AsyncMock

import pytest

from eero.client import EeroClient
from eero.exceptions import (
    EeroAuthenticationException,
    EeroException,
    EeroValidationException,
)


class TestEeroClientInit:
    """Tests for EeroClient initialization."""

    def test_default_init(self):
        """Test default initialization."""
        client = EeroClient()

        assert client._cache_timeout == 60
        assert client._api is not None
        assert client._cache is not None

    def test_init_with_custom_timeout(self):
        """Test initialization with custom cache timeout."""
        client = EeroClient(cache_timeout=120)

        assert client._cache_timeout == 120

    def test_init_with_session(self, mock_session):
        """Test initialization with existing session."""
        client = EeroClient(session=mock_session)

        assert client._api.auth._session is mock_session

    def test_init_with_cookie_file(self):
        """Test initialization with cookie file."""
        client = EeroClient(cookie_file="/path/to/cookies.json", use_keyring=False)

        assert client._api.auth._cookie_file == "/path/to/cookies.json"

    def test_init_cache_structure(self):
        """Test that cache has proper structure."""
        client = EeroClient()

        expected_keys = ["account", "networks", "network", "eeros", "devices", "profiles"]
        for key in expected_keys:
            assert key in client._cache


class TestEeroClientAuthentication:
    """Tests for EeroClient authentication properties."""

    def test_is_authenticated_false_by_default(self):
        """Test that client is not authenticated by default."""
        client = EeroClient()

        assert client.is_authenticated is False

    def test_is_authenticated_delegates_to_api(self, mock_session):
        """Test that is_authenticated delegates to API."""
        client = EeroClient(session=mock_session)

        # Mock the underlying auth API's session to make it appear authenticated
        from datetime import datetime, timedelta

        client._api.auth._credentials.session_id = "test_session"
        client._api.auth._credentials.session_expiry = datetime.now() + timedelta(days=1)

        assert client.is_authenticated is True


class TestEeroClientCache:
    """Tests for EeroClient caching functionality."""

    def test_is_cache_valid_empty(self):
        """Test cache validity check with empty cache."""
        client = EeroClient()

        assert client._is_cache_valid("nonexistent") is False

    def test_is_cache_valid_fresh(self):
        """Test cache validity check with fresh data."""
        client = EeroClient(cache_timeout=60)
        client._cache["networks"] = {"data": [], "timestamp": time.monotonic()}

        assert client._is_cache_valid("networks") is True

    def test_is_cache_valid_expired(self):
        """Test cache validity check with expired data."""
        client = EeroClient(cache_timeout=60)
        client._cache["networks"] = {
            "data": [],
            "timestamp": time.monotonic() - 120,  # Expired
        }

        assert client._is_cache_valid("networks") is False

    def test_is_cache_valid_with_subkey(self):
        """Test cache validity check with subkey."""
        client = EeroClient(cache_timeout=60)
        client._cache["network"]["network_123"] = {
            "data": {},
            "timestamp": time.monotonic(),
        }

        assert client._is_cache_valid("network", "network_123") is True
        assert client._is_cache_valid("network", "network_456") is False

    def test_update_cache(self):
        """Test updating cache entry."""
        client = EeroClient()
        test_data = {"name": "Test Network"}

        client._update_cache("networks", None, test_data)

        assert client._cache["networks"]["data"] == test_data
        assert "timestamp" in client._cache["networks"]

    def test_update_cache_with_subkey(self):
        """Test updating cache entry with subkey."""
        client = EeroClient()
        test_data = {"id": "network_123", "name": "Test"}

        client._update_cache("network", "network_123", test_data)

        assert client._cache["network"]["network_123"]["data"] == test_data

    def test_get_from_cache(self):
        """Test getting data from cache."""
        client = EeroClient()
        test_data = {"name": "Test"}
        client._cache["networks"] = {"data": test_data, "timestamp": time.monotonic()}

        result = client._get_from_cache("networks")

        assert result == test_data

    def test_get_from_cache_with_subkey(self):
        """Test getting data from cache with subkey."""
        client = EeroClient()
        test_data = {"id": "network_123"}
        client._cache["network"]["network_123"] = {
            "data": test_data,
            "timestamp": time.monotonic(),
        }

        result = client._get_from_cache("network", "network_123")

        assert result == test_data

    def test_get_from_cache_missing(self):
        """Test getting data from cache when missing."""
        client = EeroClient()

        result = client._get_from_cache("nonexistent")

        assert result is None

    def test_clear_cache(self):
        """Test clearing all cache."""
        client = EeroClient()
        client._cache["networks"] = {"data": [{"id": "test"}], "timestamp": time.monotonic()}
        client._cache["network"]["network_123"] = {
            "data": {"id": "network_123"},
            "timestamp": time.monotonic(),
        }

        client.clear_cache()

        assert client._cache["networks"]["data"] is None
        assert client._cache["network"] == {}


class TestEeroClientContextManager:
    """Tests for EeroClient async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_enters_api(self, mock_session, mock_keyring):
        """Test that entering context manager enters API."""
        client = EeroClient(session=mock_session, use_keyring=True)

        # Mock the API's context manager
        client._api.__aenter__ = AsyncMock(return_value=client._api)
        client._api.__aexit__ = AsyncMock(return_value=None)

        async with client as ctx:
            assert ctx is client

        client._api.__aenter__.assert_awaited_once()
        client._api.__aexit__.assert_awaited_once()


class TestEeroClientEnsureNetworkId:
    """Tests for _ensure_network_id method."""

    @pytest.mark.asyncio
    async def test_returns_provided_network_id(self, mock_session):
        """Test that provided network ID is returned directly."""
        client = EeroClient(session=mock_session)

        result = await client._ensure_network_id("network_123", auto_discover=False)

        assert result == "network_123"

    @pytest.mark.asyncio
    async def test_uses_preferred_network_id(self, mock_session):
        """Test that preferred network ID is used when available."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = "preferred_network"

        result = await client._ensure_network_id(None, auto_discover=False)

        assert result == "preferred_network"

    @pytest.mark.asyncio
    async def test_raises_without_network_id(self, mock_session):
        """Test that exception is raised when no network ID available."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client._ensure_network_id(None, auto_discover=False)

    @pytest.mark.asyncio
    async def test_auto_discover_networks(self, mock_session, sample_networks_list):
        """Test auto-discovery when no network ID provided."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        # Mock networks API - returns raw response format
        raw_response = {
            "meta": {"code": 200},
            "data": {"networks": sample_networks_list},
        }
        client._api.networks.get_networks = AsyncMock(return_value=raw_response)

        result = await client._ensure_network_id(None, auto_discover=True)

        assert result == "network_123"
        client._api.networks.get_networks.assert_awaited_once()


class TestEeroClientCacheIntegration:
    """Integration tests for cache behavior."""

    @pytest.mark.asyncio
    async def test_cache_timeout_respected(self, mock_session):
        """Test that cache timeout is respected."""
        # Very short timeout for testing
        client = EeroClient(session=mock_session, cache_timeout=1)

        # Populate cache
        client._update_cache("networks", None, [{"id": "test"}])
        assert client._is_cache_valid("networks") is True

        # Wait for cache to expire
        import asyncio

        await asyncio.sleep(1.1)

        assert client._is_cache_valid("networks") is False

    def test_multiple_subkey_caching(self):
        """Test caching multiple items with subkeys."""
        client = EeroClient()

        # Cache multiple networks
        client._update_cache("network", "net_1", {"name": "Network 1"})
        client._update_cache("network", "net_2", {"name": "Network 2"})
        client._update_cache("network", "net_3", {"name": "Network 3"})

        assert client._get_from_cache("network", "net_1")["name"] == "Network 1"
        assert client._get_from_cache("network", "net_2")["name"] == "Network 2"
        assert client._get_from_cache("network", "net_3")["name"] == "Network 3"

    def test_cache_independence(self):
        """Test that different cache keys are independent."""
        client = EeroClient()

        client._update_cache("networks", None, [{"id": "list"}])
        client._update_cache("network", "net_1", {"id": "single"})

        # Clear one, other should remain
        client._cache["networks"]["data"] = None

        assert client._get_from_cache("networks") is None
        assert client._get_from_cache("network", "net_1") is not None


class TestEeroClientReservationWrites:
    """Tests for reservation write wrappers on EeroClient."""

    @pytest.mark.asyncio
    async def test_create_reservation_delegates(self, mock_session):
        """Test create_reservation passes through to the API layer."""
        client = EeroClient(session=mock_session)
        payload = {"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.1.50", "description": "nas"}
        expected = {"meta": {"code": 201}, "data": {"id": "res_1"}}
        client._api.reservations.create_reservation = AsyncMock(return_value=expected)

        result = await client.create_reservation(payload, network_id="network_123")

        assert result == expected
        client._api.reservations.create_reservation.assert_awaited_once_with("network_123", payload)

    @pytest.mark.asyncio
    async def test_create_reservation_requires_network_id(self, mock_session):
        """Test create_reservation raises when no network ID is available."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client.create_reservation({"mac": "aa:bb:cc:dd:ee:ff"})

    @pytest.mark.asyncio
    async def test_create_reservation_propagates_auth_error(self, mock_session):
        """Test create_reservation propagates authentication errors."""
        client = EeroClient(session=mock_session)
        client._api.reservations.create_reservation = AsyncMock(
            side_effect=EeroAuthenticationException("Not authenticated")
        )

        with pytest.raises(EeroAuthenticationException):
            await client.create_reservation({"mac": "aa:bb:cc:dd:ee:ff"}, network_id="network_123")

    @pytest.mark.asyncio
    async def test_update_reservation_delegates(self, mock_session):
        """Test update_reservation passes through to the API layer."""
        client = EeroClient(session=mock_session)
        payload = {"ip": "192.168.1.51"}
        expected = {"meta": {"code": 200}, "data": {"id": "res_1"}}
        client._api.reservations.update_reservation = AsyncMock(return_value=expected)

        result = await client.update_reservation("res_1", payload, network_id="network_123")

        assert result == expected
        client._api.reservations.update_reservation.assert_awaited_once_with(
            "network_123", "res_1", payload
        )

    @pytest.mark.asyncio
    async def test_update_reservation_requires_network_id(self, mock_session):
        """Test update_reservation raises when no network ID is available."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client.update_reservation("res_1", {"ip": "192.168.1.51"})

    @pytest.mark.asyncio
    async def test_update_reservation_propagates_auth_error(self, mock_session):
        """Test update_reservation propagates authentication errors."""
        client = EeroClient(session=mock_session)
        client._api.reservations.update_reservation = AsyncMock(
            side_effect=EeroAuthenticationException("Not authenticated")
        )

        with pytest.raises(EeroAuthenticationException):
            await client.update_reservation("res_1", {}, network_id="network_123")

    @pytest.mark.asyncio
    async def test_delete_reservation_delegates(self, mock_session):
        """Test delete_reservation passes through to the API layer."""
        client = EeroClient(session=mock_session)
        expected = {"meta": {"code": 200}, "data": {}}
        client._api.reservations.delete_reservation = AsyncMock(return_value=expected)

        result = await client.delete_reservation("res_1", network_id="network_123")

        assert result == expected
        client._api.reservations.delete_reservation.assert_awaited_once_with("network_123", "res_1")

    @pytest.mark.asyncio
    async def test_delete_reservation_requires_network_id(self, mock_session):
        """Test delete_reservation raises when no network ID is available."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client.delete_reservation("res_1")

    @pytest.mark.asyncio
    async def test_delete_reservation_propagates_auth_error(self, mock_session):
        """Test delete_reservation propagates authentication errors."""
        client = EeroClient(session=mock_session)
        client._api.reservations.delete_reservation = AsyncMock(
            side_effect=EeroAuthenticationException("Not authenticated")
        )

        with pytest.raises(EeroAuthenticationException):
            await client.delete_reservation("res_1", network_id="network_123")


class TestEeroClientForwardWrites:
    """Tests for port forward write wrappers on EeroClient."""

    @pytest.mark.asyncio
    async def test_create_forward_delegates(self, mock_session):
        """Test create_forward passes through to the API layer."""
        client = EeroClient(session=mock_session)
        payload = {
            "ip": "192.168.1.50",
            "protocol": "tcp",
            "port_external": 8080,
            "port_internal": 80,
            "description": "web",
        }
        expected = {"meta": {"code": 201}, "data": {"id": "fwd_1"}}
        client._api.forwards.create_forward = AsyncMock(return_value=expected)

        result = await client.create_forward(payload, network_id="network_123")

        assert result == expected
        client._api.forwards.create_forward.assert_awaited_once_with("network_123", payload)

    @pytest.mark.asyncio
    async def test_create_forward_requires_network_id(self, mock_session):
        """Test create_forward raises when no network ID is available."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client.create_forward({"ip": "192.168.1.50", "protocol": "tcp"})

    @pytest.mark.asyncio
    async def test_create_forward_propagates_auth_error(self, mock_session):
        """Test create_forward propagates authentication errors."""
        client = EeroClient(session=mock_session)
        client._api.forwards.create_forward = AsyncMock(
            side_effect=EeroAuthenticationException("Not authenticated")
        )

        with pytest.raises(EeroAuthenticationException):
            await client.create_forward(
                {"ip": "192.168.1.50", "protocol": "tcp"}, network_id="network_123"
            )

    @pytest.mark.asyncio
    async def test_delete_forward_delegates(self, mock_session):
        """Test delete_forward passes through to the API layer."""
        client = EeroClient(session=mock_session)
        expected = {"meta": {"code": 200}, "data": {}}
        client._api.forwards.delete_forward = AsyncMock(return_value=expected)

        result = await client.delete_forward("forward_1", network_id="network_123")

        assert result == expected
        client._api.forwards.delete_forward.assert_awaited_once_with("network_123", "forward_1")

    @pytest.mark.asyncio
    async def test_delete_forward_requires_network_id(self, mock_session):
        """Test delete_forward raises when no network ID is available."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client.delete_forward("forward_1")

    @pytest.mark.asyncio
    async def test_delete_forward_propagates_auth_error(self, mock_session):
        """Test delete_forward propagates authentication errors."""
        client = EeroClient(session=mock_session)
        client._api.forwards.delete_forward = AsyncMock(
            side_effect=EeroAuthenticationException("Not authenticated")
        )

        with pytest.raises(EeroAuthenticationException):
            await client.delete_forward("forward_1", network_id="network_123")


# ========================== DNS facade ==========================


class TestEeroClientDns:
    """Tests for the EeroClient DNS wrappers.

    These cover the facade itself rather than DnsAPI: argument order across the
    delegation boundary, and cache invalidation after a write. A DnsAPI-level
    test cannot catch a dropped or transposed argument here (issue #123).
    """

    @pytest.fixture
    def client(self, mock_session):
        """A client with a preferred network and a stubbed DNS API."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = "network_123"
        for name in (
            "get_dns_settings",
            "set_dns_caching",
            "set_custom_dns",
            "set_custom_dns_ipv4",
            "set_custom_dns_ipv6",
            "clear_custom_dns",
            "set_dns_mode",
            "set_ipv6_dns",
        ):
            setattr(client._api.dns, name, AsyncMock(return_value={"meta": {"code": 200}}))
        return client

    @pytest.mark.asyncio
    async def test_set_custom_dns_delegates_network_id_first(self, client):
        """Test network_id leads and the server list follows, not the reverse."""
        await client.set_custom_dns(["1.1.1.1", "1.0.0.1"])

        client._api.dns.set_custom_dns.assert_called_once_with(
            "network_123", ["1.1.1.1", "1.0.0.1"]
        )

    @pytest.mark.asyncio
    async def test_set_custom_dns_ipv4_delegates(self, client):
        """Test the IPv4 wrapper reaches the IPv4 method with the right order."""
        await client.set_custom_dns_ipv4(["8.8.8.8"])

        client._api.dns.set_custom_dns_ipv4.assert_called_once_with("network_123", ["8.8.8.8"])

    @pytest.mark.asyncio
    async def test_set_custom_dns_ipv6_delegates(self, client):
        """Test the IPv6 wrapper reaches the IPv6 method, not the IPv4 one."""
        await client.set_custom_dns_ipv6(["2606:4700:4700::1111"])

        client._api.dns.set_custom_dns_ipv6.assert_called_once_with(
            "network_123", ["2606:4700:4700::1111"]
        )
        client._api.dns.set_custom_dns_ipv4.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_custom_dns_forwards_family(self, client):
        """Test the family argument survives the delegation."""
        await client.clear_custom_dns(family="ipv6")

        client._api.dns.clear_custom_dns.assert_called_once_with("network_123", "ipv6")

    @pytest.mark.asyncio
    async def test_clear_custom_dns_defaults_to_both_families(self, client):
        """Test omitting family clears both."""
        await client.clear_custom_dns()

        client._api.dns.clear_custom_dns.assert_called_once_with("network_123", None)

    @pytest.mark.asyncio
    async def test_set_dns_caching_delegates(self, client):
        """Test the enabled flag is not transposed with network_id."""
        await client.set_dns_caching(True)

        client._api.dns.set_dns_caching.assert_called_once_with("network_123", True)

    @pytest.mark.asyncio
    async def test_set_dns_mode_delegates(self, client):
        """Test mode and servers arrive in the documented order."""
        await client.set_dns_mode("custom", ["9.9.9.9"])

        client._api.dns.set_dns_mode.assert_called_once_with("network_123", "custom", ["9.9.9.9"])

    @pytest.mark.asyncio
    async def test_set_ipv6_dns_delegates(self, client):
        """Test the ipv6_upstream toggle reaches DnsAPI."""
        await client.set_ipv6_dns(True)

        client._api.dns.set_ipv6_dns.assert_called_once_with("network_123", True)

    @pytest.mark.asyncio
    async def test_explicit_network_id_overrides_preferred(self, client):
        """Test an explicit network_id wins over the preferred network."""
        await client.set_custom_dns(["1.1.1.1"], network_id="network_999")

        client._api.dns.set_custom_dns.assert_called_once_with("network_999", ["1.1.1.1"])

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "call",
        [
            lambda c: c.set_custom_dns(["1.1.1.1"]),
            lambda c: c.set_custom_dns_ipv4(["1.1.1.1"]),
            lambda c: c.set_custom_dns_ipv6(["2606:4700:4700::1111"]),
            lambda c: c.clear_custom_dns(),
            lambda c: c.set_dns_caching(True),
            lambda c: c.set_dns_mode("auto"),
            lambda c: c.set_ipv6_dns(True),
        ],
    )
    async def test_writes_invalidate_the_network_cache(self, client, call):
        """Test every DNS write evicts the cached network snapshot.

        DNS settings live inside the network resource, so a stale snapshot would
        report pre-write state for up to the cache TTL.
        """
        client._cache["network"]["network_123"] = {
            "data": {"dns": {"mode": "custom"}},
            "timestamp": time.monotonic(),
        }

        await call(client)

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_write_leaves_other_networks_cached(self, client):
        """Test invalidation is scoped to the network being written."""
        for net in ("network_123", "network_456"):
            client._cache["network"][net] = {"data": {}, "timestamp": time.monotonic()}

        await client.set_custom_dns(["1.1.1.1"])

        assert "network_123" not in client._cache["network"]
        assert "network_456" in client._cache["network"]

    @pytest.mark.asyncio
    async def test_invalidation_is_safe_when_nothing_cached(self, client):
        """Test writing with a cold cache does not raise."""
        client._cache["network"].pop("network_123", None)

        await client.set_custom_dns(["1.1.1.1"])

        client._api.dns.set_custom_dns.assert_called_once()

    @pytest.mark.asyncio
    async def test_reads_do_not_invalidate_the_cache(self, client):
        """Test get_dns_settings leaves the cached snapshot alone."""
        client._cache["network"]["network_123"] = {"data": {}, "timestamp": time.monotonic()}

        await client.get_dns_settings()

        assert "network_123" in client._cache["network"]

    @pytest.mark.asyncio
    async def test_requires_network_id(self, mock_session):
        """Test a DNS write with no network available raises rather than guessing."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client.set_custom_dns(["1.1.1.1"])

    @pytest.mark.asyncio
    async def test_propagates_validation_error(self, client):
        """Test validation errors from DnsAPI are not swallowed by the facade."""
        client._api.dns.set_custom_dns = AsyncMock(
            side_effect=EeroValidationException("dns_servers", "bad")
        )

        with pytest.raises(EeroValidationException):
            await client.set_custom_dns(["nope"])

    @pytest.mark.asyncio
    async def test_failed_write_does_not_invalidate_cache(self, client):
        """Test a raising write leaves the cache intact.

        Evicting on failure would force a needless refetch of state that never
        changed.
        """
        client._cache["network"]["network_123"] = {"data": {}, "timestamp": time.monotonic()}
        client._api.dns.set_custom_dns = AsyncMock(
            side_effect=EeroValidationException("dns_servers", "bad")
        )

        with pytest.raises(EeroValidationException):
            await client.set_custom_dns(["nope"])

        assert "network_123" in client._cache["network"]
