"""Tests for EeroClient high-level client.

Tests cover:
- Client initialization and configuration
- Cache management and expiry
- Network ID resolution
- Context manager lifecycle
"""

import inspect
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api import EeroAPI
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

        # A present session token is what makes the client authenticated.
        client._api.auth._credentials.session_id = "test_session"

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
            "res_1", payload, network="network_123"
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


class TestEeroClientCoreOptions:
    """Tests for the keyword-only core transport options forwarded to AuthAPI."""

    def test_defaults_forwarded_to_auth_api(self):
        """Test the default option values reach AuthAPI unchanged."""
        client = EeroClient()

        assert client._api.auth._send_legacy_cookie is True
        assert client._api.auth._accept_language == "en-US"
        assert client._api.auth._get_retries == 0

    def test_custom_values_forwarded_to_auth_api(self):
        """Test explicit option values reach AuthAPI unchanged."""
        client = EeroClient(
            send_legacy_cookie=False,
            accept_language="fr-FR",
            get_retries=3,
        )

        assert client._api.auth._send_legacy_cookie is False
        assert client._api.auth._accept_language == "fr-FR"
        assert client._api.auth._get_retries == 3


class TestEeroClientDataUsage:
    """Tests for the EeroClient data-usage wrappers.

    These cover the facade's delegation boundary (network resolution, argument
    forwarding, and cache behaviour) rather than DataUsageAPI itself.
    """

    START = "2026-07-01T00:00:00Z"
    END = "2026-07-02T00:00:00Z"

    @pytest.fixture
    def client(self, mock_session):
        """A client with a preferred network and a stubbed DataUsageAPI."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = "network_123"
        for name in (
            "get_data_usage",
            "get_breakdown",
            "get_devices_usage",
            "get_device_usage",
            "get_eeros_summary",
            "get_eero_usage",
            "get_profile_usage",
            "get_unprofiled_devices",
            "get_unprofiled_summary",
            "get_report_settings",
            "set_report_settings",
        ):
            setattr(
                client._api.data_usage,
                name,
                AsyncMock(return_value={"meta": {"code": 200}, "data": {}}),
            )
        return client

    @pytest.mark.asyncio
    async def test_get_data_usage_resolves_network_and_forwards_args(self, client):
        """Test network_id resolution and pass-through of the raw envelope."""
        result = await client.get_data_usage(start=self.START, end=self.END, cadence="daily")

        assert result == {"meta": {"code": 200}, "data": {}}
        client._api.data_usage.get_data_usage.assert_called_once_with(
            "network_123", start=self.START, end=self.END, cadence="daily", timezone=None
        )

    @pytest.mark.asyncio
    async def test_get_device_data_usage_forwards_device_mac(self, client):
        """Test the device MAC leads the domain call's positional args."""
        await client.get_device_data_usage(
            "device_mac_aa", start=self.START, end=self.END, cadence="hourly"
        )

        client._api.data_usage.get_device_usage.assert_called_once_with(
            "network_123",
            "device_mac_aa",
            start=self.START,
            end=self.END,
            cadence="hourly",
            timezone=None,
        )

    @pytest.mark.asyncio
    async def test_get_eero_data_usage_forwards_eero_id(self, client):
        """Test the eero ID reaches the domain call."""
        await client.get_eero_data_usage("eero_1", start=self.START, end=self.END, cadence="daily")

        client._api.data_usage.get_eero_usage.assert_called_once_with(
            "network_123", "eero_1", start=self.START, end=self.END, cadence="daily", timezone=None
        )

    @pytest.mark.asyncio
    async def test_get_profile_data_usage_forwards_profile_id(self, client):
        """Test the profile ID reaches the domain call."""
        await client.get_profile_data_usage(
            "profile_1", start=self.START, end=self.END, cadence="daily"
        )

        client._api.data_usage.get_profile_usage.assert_called_once_with(
            "network_123",
            "profile_1",
            start=self.START,
            end=self.END,
            cadence="daily",
            timezone=None,
        )

    @pytest.mark.asyncio
    async def test_get_devices_data_usage_forwards_profile_id(self, client):
        """Test the optional profile_id filter reaches the domain call."""
        await client.get_devices_data_usage(
            start=self.START, end=self.END, profile_id="profile_abc"
        )

        client._api.data_usage.get_devices_usage.assert_called_once_with(
            "network_123",
            start=self.START,
            end=self.END,
            cadence=None,
            timezone=None,
            profile_id="profile_abc",
        )

    @pytest.mark.asyncio
    async def test_data_usage_reads_are_not_cached(self, client):
        """Test consecutive reads always call through, never serve a cached copy.

        The data-usage family is time-windowed, so caching it would silently
        serve stale or mismatched windows.
        """
        await client.get_data_usage(start=self.START, end=self.END, cadence="daily")
        await client.get_data_usage(start=self.START, end=self.END, cadence="daily")

        assert client._api.data_usage.get_data_usage.await_count == 2

    @pytest.mark.asyncio
    async def test_set_report_settings_forwards_args_and_invalidates_cache(self, client):
        """Test the write forwards cadence/notification_day and drops the network cache."""
        client._cache["network"]["network_123"] = {"data": {}, "timestamp": time.monotonic()}

        await client.set_data_usage_report_settings(cadence="daily", notification_day="monday")

        client._api.data_usage.set_report_settings.assert_called_once_with(
            "network_123", cadence="daily", notification_day="monday"
        )
        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_get_report_settings_delegates(self, client):
        """Test the read wrapper resolves the network and delegates."""
        await client.get_data_usage_report_settings()

        client._api.data_usage.get_report_settings.assert_called_once_with("network_123")

    @pytest.mark.asyncio
    async def test_requires_network_id(self, mock_session):
        """Test a data-usage read with no network available raises."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client.get_data_usage(start=self.START, end=self.END, cadence="daily")


class TestEeroClientOuicheck:
    """Tests for the EeroClient OUI check wrapper."""

    @pytest.mark.asyncio
    async def test_get_ouicheck_resolves_network_and_forwards_args(self, mock_session):
        """Test network_id resolution and serial/version pass-through."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = "network_123"
        client._api.ouicheck.get_ouicheck = AsyncMock(
            return_value={"meta": {"code": 200}, "data": {}}
        )

        result = await client.get_ouicheck(serial="serial_example", version="1.0.0-example")

        assert result == {"meta": {"code": 200}, "data": {}}
        client._api.ouicheck.get_ouicheck.assert_called_once_with(
            "network_123", serial="serial_example", version="1.0.0-example"
        )

    @pytest.mark.asyncio
    async def test_requires_network_id(self, mock_session):
        """Test an OUI check with no network available raises."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client.get_ouicheck(serial="serial_example", version="1.0.0-example")


# ========================== Domain-call signature binding ==========================
#
# Phase 3 facade rebuild: every wrapper on EeroClient forwards to a domain
# method on EeroAPI. This table is the single source of truth for what each
# wrapper forwards -- (dotted attribute path on a real EeroAPI instance,
# positional args, keyword args) -- as it would be called with a fresh
# cached parent envelope available. `inspect.signature(...).bind(...)`
# against the REAL domain method catches a wrapper calling a method that no
# longer exists, or with the wrong arity/keyword names, independent of any
# mocking elsewhere in this file.

_PLACEHOLDER_PARENT: Dict[str, Any] = {"meta": {"code": 200}, "data": {}}

#: (dotted attribute path under EeroAPI, positional args, keyword args)
DOMAIN_CALL_SHAPES = [
    # eeros
    ("eeros.get_eeros", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("eeros.get_eero", ("net", "eero"), {"parent": _PLACEHOLDER_PARENT}),
    ("eeros.reboot_eero", ("net", "eero"), {"parent": _PLACEHOLDER_PARENT}),
    ("eeros.get_led_status", ("net", "eero"), {"parent": _PLACEHOLDER_PARENT}),
    ("eeros.set_led", ("net", "eero", True), {"parent": _PLACEHOLDER_PARENT}),
    ("eeros.set_led_brightness", ("net", "eero", 50), {"parent": _PLACEHOLDER_PARENT}),
    ("eeros.set_location", ("net", "eero", "loc"), {"parent": _PLACEHOLDER_PARENT}),
    ("eeros.get_nightlight", ("net", "eero"), {"parent": _PLACEHOLDER_PARENT}),
    (
        "eeros.set_nightlight",
        ("net", "eero"),
        {
            "enabled": True,
            "brightness_percentage": 50,
            "schedule": {},
            "parent": _PLACEHOLDER_PARENT,
        },
    ),
    ("eeros.get_connections", ("net", "eero"), {"parent": _PLACEHOLDER_PARENT}),
    # networks
    ("networks.get_networks", (), {}),
    ("networks.get_network", ("net",), {}),
    ("networks.get_premium_status", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("networks.set_network_name", ("net", "name"), {"parent": _PLACEHOLDER_PARENT}),
    ("networks.set_network_password", ("net", "pwd"), {"parent": _PLACEHOLDER_PARENT}),
    ("networks.clear_network_password", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("networks.get_guest_network", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    (
        "networks.set_guest_network",
        ("net",),
        {"enabled": True, "name": None, "parent": _PLACEHOLDER_PARENT},
    ),
    ("networks.set_guest_password", ("net", "pwd"), {}),
    ("networks.clear_guest_password", ("net",), {}),
    ("networks.run_speed_test", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    (
        "networks.get_speed_tests",
        ("net",),
        {
            "limit": None,
            "start_time": None,
            "end_time": None,
            "parent": _PLACEHOLDER_PARENT,
        },
    ),
    # devices
    (
        "devices.get_devices",
        ("net",),
        {"thread": None, "proxied_node": None, "parent": _PLACEHOLDER_PARENT},
    ),
    ("devices.get_device", ("net", "dev"), {}),
    ("devices.set_device_nickname", ("net", "dev", "nick"), {}),
    ("devices.block_device", ("net", "dev"), {}),
    ("devices.unblock_device", ("net", "dev"), {}),
    ("devices.pause_device", ("net", "dev", True), {}),
    (
        "devices.update_device_via_link",
        ("net", "dev"),
        {
            "nickname": None,
            "paused": None,
            "profile": None,
            "parent": _PLACEHOLDER_PARENT,
        },
    ),
    ("devices.set_device_type", ("net", "dev", "type"), {}),
    ("devices.get_device_labels", ("net", "dev"), {}),
    (
        "devices.set_device_labels",
        ("net", "dev"),
        {
            "make_label": None,
            "model_label": None,
            "version_label": None,
            "type_label": None,
        },
    ),
    # profiles
    ("profiles.get_profiles", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("profiles.get_profile", ("net", "prof"), {}),
    ("profiles.pause_profile", ("net", "prof", True), {}),
    (
        "profiles.create_profile",
        ("net", "name"),
        {"devices": None, "paused": None, "parent": _PLACEHOLDER_PARENT},
    ),
    ("profiles.rename_profile", ("net", "prof", "name"), {}),
    ("profiles.delete_profile", ("net", "prof"), {}),
    ("profiles.get_profile_devices", ("net", "prof"), {}),
    ("profiles.set_profile_devices", ("net", "prof", []), {}),
    # diagnostics
    ("diagnostics.get_diagnostics", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    (
        "diagnostics.run_diagnostics",
        ("net",),
        {"device": None, "symptom": None, "parent": _PLACEHOLDER_PARENT},
    ),
    # insights
    (
        "insights.get_insights",
        ("net",),
        {"start": "s", "end": "e", "insight_type": "t", "cadence": "daily"},
    ),
    (
        "insights.get_devices_insights",
        ("net",),
        {
            "start": "s",
            "end": "e",
            "cadence": "daily",
            "insight_type": "t",
            "parent": _PLACEHOLDER_PARENT,
        },
    ),
    (
        "insights.get_device_insights",
        ("net", "dev"),
        {"start": "s", "end": "e", "cadence": "daily", "insight_type": "t"},
    ),
    (
        "insights.get_profiles_insights",
        ("net",),
        {
            "start": "s",
            "end": "e",
            "cadence": "daily",
            "insight_type": "t",
            "parent": _PLACEHOLDER_PARENT,
        },
    ),
    (
        "insights.get_profile_insights",
        ("net", "prof"),
        {"start": "s", "end": "e", "cadence": "daily", "insight_type": "t"},
    ),
    (
        "insights.get_profile_devices_insights",
        ("net", "prof"),
        {"start": "s", "end": "e", "cadence": "daily", "insight_type": "t"},
    ),
    # routing / thread / support / blacklist
    ("routing.get_routing", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("thread.get_thread", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("thread.set_thread_enabled", ("net", True), {}),
    (
        "thread.update_thread",
        ("net",),
        {"thread_enable": None, "enable_credential_syncing": None},
    ),
    ("thread.regenerate_thread_credentials", ("net",), {}),
    ("support.get_support", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("blacklist.get_blacklist", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    # reservations / forwards
    ("reservations.get_reservations", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("reservations.create_reservation", ("net", {}), {"parent": _PLACEHOLDER_PARENT}),
    ("reservations.update_reservation", ("res", {}), {"network": "net"}),
    ("reservations.delete_reservation", ("net", "res"), {"delete_forwards": True}),
    ("forwards.get_forwards", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("forwards.create_forward", ("net", {}), {"parent": _PLACEHOLDER_PARENT}),
    ("forwards.update_forward", ("fwd", {}), {"network": "net"}),
    ("forwards.delete_forward", ("net", "fwd"), {}),
    # transfer
    ("transfer.get_transfer_stats", ("net", None), {"parent": _PLACEHOLDER_PARENT}),
    # data usage
    (
        "data_usage.get_data_usage",
        ("net",),
        {"start": "s", "end": "e", "cadence": "daily", "timezone": None},
    ),
    (
        "data_usage.get_breakdown",
        ("net",),
        {"start": "s", "end": "e", "cadence": None, "timezone": None},
    ),
    (
        "data_usage.get_devices_usage",
        ("net",),
        {"start": "s", "end": "e", "cadence": None, "timezone": None, "profile_id": None},
    ),
    (
        "data_usage.get_device_usage",
        ("net", "mac"),
        {"start": "s", "end": "e", "cadence": "daily", "timezone": None},
    ),
    (
        "data_usage.get_eeros_summary",
        ("net",),
        {"start": "s", "end": "e", "cadence": "daily", "timezone": None},
    ),
    (
        "data_usage.get_eero_usage",
        ("net", "eero"),
        {"start": "s", "end": "e", "cadence": "daily", "timezone": None},
    ),
    (
        "data_usage.get_profile_usage",
        ("net", "prof"),
        {"start": "s", "end": "e", "cadence": "daily", "timezone": None},
    ),
    (
        "data_usage.get_unprofiled_devices",
        ("net",),
        {"start": "s", "end": "e", "cadence": None, "timezone": None},
    ),
    (
        "data_usage.get_unprofiled_summary",
        ("net",),
        {"start": "s", "end": "e", "cadence": "daily", "timezone": None},
    ),
    ("data_usage.get_report_settings", ("net",), {}),
    (
        "data_usage.set_report_settings",
        ("net",),
        {"cadence": "daily", "notification_day": "monday"},
    ),
    # ac_compat / ouicheck / updates
    ("ac_compat.get_ac_compat", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    (
        "ouicheck.get_ouicheck",
        ("net",),
        {"serial": "s", "version": "v", "parent": _PLACEHOLDER_PARENT},
    ),
    ("updates.get_updates", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("updates.apply_update", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    # backup
    ("backup.get_backup_internet", ("net",), {}),
    ("backup.set_backup_internet", ("net", True), {}),
    ("backup.get_cellular_backup_usage", ("net",), {}),
    ("backup.get_cellular_backup_events", ("net",), {}),
    # schedule
    ("schedule.get_schedules", ("net", "prof"), {}),
    (
        "schedule.create_schedule",
        ("net", "prof"),
        {"name": "n", "days": [], "start": "s", "end": "e", "enabled": True},
    ),
    (
        "schedule.update_schedule",
        ({},),
        {"name": None, "days": None, "start": None, "end": None, "enabled": None},
    ),
    ("schedule.delete_schedule", ({},), {}),
    ("schedule.clear_profile_schedule", ("net", "prof"), {}),
    ("schedule.enable_bedtime", ("net", "prof", "s", "e", None), {}),
    # dns
    ("dns.get_dns_settings", ("net",), {}),
    ("dns.set_dns_caching", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    ("dns.set_custom_dns", ("net", []), {"parent": _PLACEHOLDER_PARENT}),
    ("dns.set_custom_dns_ipv4", ("net", []), {"parent": _PLACEHOLDER_PARENT}),
    ("dns.set_custom_dns_ipv6", ("net", []), {"parent": _PLACEHOLDER_PARENT}),
    ("dns.clear_custom_dns", ("net", None), {"parent": _PLACEHOLDER_PARENT}),
    ("dns.set_dns_mode", ("net", "auto", None), {"parent": _PLACEHOLDER_PARENT}),
    # sqm
    ("sqm.get_sqm_settings", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("sqm.set_sqm", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    # security
    ("security.get_security_settings", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("security.set_wpa3", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    ("security.set_band_steering", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    ("security.set_upnp", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    ("security.set_ipv6", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    (
        "security.configure_security",
        ("net",),
        {
            "wpa3": None,
            "band_steering": None,
            "upnp": None,
            "ipv6": None,
            "parent": _PLACEHOLDER_PARENT,
        },
    ),
]


class TestDomainCallSignatureBinding:
    """Every EeroClient wrapper's forwarded call binds against the real domain method.

    This guards against a wrapper calling a method that no longer exists, or
    calling an existing method with the wrong arity or keyword names -- a
    class of bug a mocked ``assert_called_with`` test cannot catch, because
    the mock never validates against the real signature.
    """

    @pytest.fixture
    def api(self) -> EeroAPI:
        """A real (unauthenticated, no I/O) EeroAPI instance to inspect."""
        return EeroAPI()

    @pytest.mark.parametrize("dotted_path, args, kwargs", DOMAIN_CALL_SHAPES)
    def test_forwarded_call_binds_to_real_domain_signature(self, api, dotted_path, args, kwargs):
        """Test the wrapper's forwarded (args, kwargs) shape binds to the live method."""
        *attr_path, method_name = dotted_path.split(".")
        target = api
        for attr in attr_path:
            target = getattr(target, attr)
        method = getattr(target, method_name)

        sig = inspect.signature(method)
        sig.bind(*args, **kwargs)  # raises TypeError on any mismatch

    def test_shape_table_covers_every_domain_module_used_by_the_client(self, api):
        """Test the table above touches every domain API the client delegates to."""
        exercised = {shape[0].split(".")[0] for shape in DOMAIN_CALL_SHAPES}
        expected = {
            "eeros",
            "networks",
            "devices",
            "profiles",
            "diagnostics",
            "insights",
            "routing",
            "thread",
            "support",
            "blacklist",
            "reservations",
            "forwards",
            "transfer",
            "data_usage",
            "ac_compat",
            "ouicheck",
            "updates",
            "backup",
            "schedule",
            "dns",
            "sqm",
            "security",
        }
        assert expected <= exercised


# ========================== Removed wrappers stay removed ==========================


class TestRemovedWrappersAreAbsent:
    """Wrappers for domain methods that no longer exist must not reappear.

    Each of these was removed because the underlying domain method was
    deleted, renamed, or had its request shape changed incompatibly during
    the v2.0 raw-response migration.
    """

    @pytest.mark.parametrize(
        "name",
        [
            # SQM: bandwidth/mode/auto variants never existed as real fields.
            "set_sqm_enabled",
            "configure_sqm",
            # Backup: renamed/replaced by the backup-internet family.
            "get_backup_network",
            "get_backup_status",
            "set_backup_network",
            "configure_backup_network",
            # Profiles: content-filter/block-list/blocked-applications were
            # never real profile fields (silent no-ops).
            "get_blocked_applications",
            "set_blocked_applications",
            # Schedule: replaced by the schedule sub-resource family.
            "get_profile_schedule",
            "set_profile_schedule",
            # Devices: the three-argument block_device(id, blocked, net) form
            # was replaced by separate block_device()/unblock_device().
        ],
    )
    def test_wrapper_is_absent(self, name):
        """Test the removed wrapper name is not an attribute of EeroClient."""
        client = EeroClient()
        assert not hasattr(client, name)

    def test_block_device_no_longer_accepts_a_blocked_flag(self):
        """Test block_device is the two-argument (device_id, network_id) form."""
        client = EeroClient()
        sig = inspect.signature(client.block_device)
        with pytest.raises(TypeError):
            sig.bind("device_id", True, network_id="network_123")
        # The current two-argument form binds cleanly.
        sig.bind("device_id", network_id="network_123")

    def test_unblock_device_exists_as_its_own_wrapper(self):
        """Test unblock_device is a distinct wrapper, not a block_device(False) call."""
        client = EeroClient()
        assert hasattr(client, "unblock_device")


# ========================== Link-aware parent resolution ==========================


class TestClientParentResolutionHelpers:
    """Tests for the private cache-lookup helpers that build `parent=` kwargs."""

    def test_network_parent_kwargs_empty_when_nothing_cached(self):
        """Test the helper omits `parent` entirely when nothing is cached."""
        client = EeroClient()

        assert client._network_parent_kwargs("network_123") == {}

    def test_network_parent_kwargs_returns_cached_envelope(self):
        """Test the helper surfaces the fresh cached network envelope."""
        client = EeroClient()
        envelope = {"meta": {"code": 200}, "data": {"id": "network_123"}}
        client._update_cache("network", "network_123", envelope)

        assert client._network_parent_kwargs("network_123") == {"parent": envelope}

    def test_network_parent_kwargs_ignores_expired_cache(self):
        """Test a stale cached envelope is not surfaced as parent."""
        client = EeroClient(cache_timeout=1)
        envelope = {"meta": {"code": 200}, "data": {"id": "network_123"}}
        client._cache["network"]["network_123"] = {
            "data": envelope,
            "timestamp": time.monotonic() - 120,
        }

        assert client._network_parent_kwargs("network_123") == {}

    def test_network_parent_kwargs_scoped_to_the_right_network(self):
        """Test caching one network's envelope does not leak into another's lookup."""
        client = EeroClient()
        client._update_cache("network", "network_123", {"data": {"id": "network_123"}})

        assert client._network_parent_kwargs("network_456") == {}

    def test_eero_parent_kwargs_empty_when_nothing_cached(self):
        """Test the eero helper omits `parent` when the eeros list is not cached."""
        client = EeroClient()

        assert client._eero_parent_kwargs("network_123", "eero_1") == {}

    def test_eero_parent_kwargs_matches_by_id(self):
        """Test the eero helper finds an entry by its `id` field."""
        client = EeroClient()
        eero_entry = {"id": "eero_1", "url": "/2.2/networks/network_123/eeros/eero_1"}
        response = {"meta": {"code": 200}, "data": [eero_entry]}
        client._update_cache("eeros", "network_123_eeros", response)

        assert client._eero_parent_kwargs("network_123", "eero_1") == {"parent": eero_entry}

    def test_eero_parent_kwargs_matches_by_trailing_url_segment(self):
        """Test the eero helper falls back to matching the trailing URL segment."""
        client = EeroClient()
        eero_entry = {"url": "/2.2/networks/network_123/eeros/eero_1"}
        response = {"meta": {"code": 200}, "data": [eero_entry]}
        client._update_cache("eeros", "network_123_eeros", response)

        assert client._eero_parent_kwargs("network_123", "eero_1") == {"parent": eero_entry}

    def test_eero_parent_kwargs_no_match_returns_empty(self):
        """Test an eero ID absent from the cached list yields no parent."""
        client = EeroClient()
        response = {"meta": {"code": 200}, "data": [{"id": "eero_other"}]}
        client._update_cache("eeros", "network_123_eeros", response)

        assert client._eero_parent_kwargs("network_123", "eero_1") == {}

    def test_device_parent_kwargs_returns_cached_device_envelope(self):
        """Test the device helper surfaces a fresh single-device cache entry."""
        client = EeroClient()
        envelope = {"meta": {"code": 200}, "data": {"mac": "dev_1"}}
        client._update_cache("devices", "network_123_dev_1", envelope)

        assert client._device_parent_kwargs("network_123", "dev_1") == {"parent": envelope}

    def test_device_parent_kwargs_empty_when_nothing_cached(self):
        """Test the device helper omits `parent` when nothing is cached."""
        client = EeroClient()

        assert client._device_parent_kwargs("network_123", "dev_1") == {}

    @pytest.mark.asyncio
    async def test_get_eeros_forwards_parent_when_network_cached(self, mock_session):
        """Test get_eeros passes the cached network envelope as parent."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = "network_123"
        network_envelope = {"meta": {"code": 200}, "data": {"id": "network_123"}}
        client._update_cache("network", "network_123", network_envelope)
        client._api.eeros.get_eeros = AsyncMock(return_value={"meta": {"code": 200}, "data": []})

        await client.get_eeros()

        client._api.eeros.get_eeros.assert_awaited_once_with("network_123", parent=network_envelope)

    @pytest.mark.asyncio
    async def test_get_eeros_omits_parent_when_network_not_cached(self, mock_session):
        """Test get_eeros omits `parent` entirely with a cold network cache."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = "network_123"
        client._api.eeros.get_eeros = AsyncMock(return_value={"meta": {"code": 200}, "data": []})

        await client.get_eeros()

        client._api.eeros.get_eeros.assert_awaited_once_with("network_123")

    @pytest.mark.asyncio
    async def test_reboot_eero_forwards_matching_cached_eero_as_parent(self, mock_session):
        """Test reboot_eero resolves parent from the cached eeros list."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = "network_123"
        eero_entry = {"id": "eero_1", "url": "/2.2/networks/network_123/eeros/eero_1"}
        client._update_cache(
            "eeros", "network_123_eeros", {"meta": {"code": 200}, "data": [eero_entry]}
        )
        client._api.eeros.reboot_eero = AsyncMock(return_value={"meta": {"code": 200}, "data": {}})

        await client.reboot_eero("eero_1")

        client._api.eeros.reboot_eero.assert_awaited_once_with(
            "network_123", "eero_1", parent=eero_entry
        )


# ========================== Cache isolation (item 4) ==========================


class TestCacheIsolation:
    """The cache and the object returned to a caller are independent copies.

    See the ``EeroClient`` class docstring for the full contract: every
    cache write stores a deep copy, and every cache read (including the
    internal ``parent=`` lookups) returns a deep copy.
    """

    def test_update_cache_stores_independent_copy(self):
        """Mutating the source object after `_update_cache` must not affect the cache."""
        client = EeroClient()
        source = {"meta": {"code": 200}, "data": {"id": "network_123", "name": "original"}}

        client._update_cache("network", "network_123", source)
        source["data"]["name"] = "mutated-after-cache-write"
        source["data"]["new_key"] = "leaked"

        cached = client._cache["network"]["network_123"]["data"]
        assert cached["data"]["name"] == "original"
        assert "new_key" not in cached["data"]

    def test_get_from_cache_returns_independent_copy(self):
        """Mutating a value returned by `_get_from_cache` must not affect the cache."""
        client = EeroClient()
        envelope = {"meta": {"code": 200}, "data": {"id": "network_123", "name": "original"}}
        client._update_cache("network", "network_123", envelope)

        first_read = client._get_from_cache("network", "network_123")
        first_read["data"]["name"] = "mutated-by-caller"
        first_read["data"]["new_key"] = "leaked"

        second_read = client._get_from_cache("network", "network_123")
        assert second_read["data"]["name"] == "original"
        assert "new_key" not in second_read["data"]

    @pytest.mark.asyncio
    async def test_mutating_returned_envelope_does_not_poison_next_cached_read(self, mock_session):
        """Mutating a response returned from a public method leaves the cache untouched."""
        client = EeroClient(session=mock_session)
        network_id = "network_123"
        client._api.networks.get_network = AsyncMock(
            return_value={"meta": {"code": 200}, "data": {"id": network_id, "name": "original"}}
        )

        response = await client.get_network(network_id)
        response["data"]["name"] = "mutated-by-caller"
        response["data"]["new_key"] = "leaked"

        cached_again = await client.get_network(network_id)
        assert cached_again["data"]["name"] == "original"
        assert "new_key" not in cached_again["data"]
        # The mutation on the first call's own return value is real and
        # independent -- it simply never reached the cache.
        assert response["data"]["name"] == "mutated-by-caller"

    @pytest.mark.asyncio
    async def test_mutating_returned_envelope_does_not_poison_parent_kwargs(self, mock_session):
        """Mutating a returned network envelope leaves later `parent=` kwargs unaffected."""
        client = EeroClient(session=mock_session)
        network_id = "network_123"
        client._api.networks.get_network = AsyncMock(
            return_value={"meta": {"code": 200}, "data": {"id": network_id, "name": "original"}}
        )
        client._api.eeros.get_eeros = AsyncMock(return_value={"meta": {"code": 200}, "data": []})

        response = await client.get_network(network_id)
        response["data"]["name"] = "mutated-by-caller"
        response["data"]["new_key"] = "leaked"

        await client.get_eeros(network_id)

        _, kwargs = client._api.eeros.get_eeros.call_args
        parent = kwargs["parent"]
        assert parent["data"]["name"] == "original"
        assert "new_key" not in parent["data"]

    def test_eero_parent_kwargs_match_is_independent_of_cache(self):
        """The eero entry returned via `_eero_parent_kwargs` is a copy, not a cache alias."""
        client = EeroClient()
        eero_entry = {"id": "eero_1", "url": "/2.2/networks/network_123/eeros/eero_1"}
        client._update_cache(
            "eeros", "network_123_eeros", {"meta": {"code": 200}, "data": [eero_entry]}
        )

        result = client._eero_parent_kwargs("network_123", "eero_1")
        result["parent"]["id"] = "mutated"

        second_result = client._eero_parent_kwargs("network_123", "eero_1")
        assert second_result["parent"]["id"] == "eero_1"


# ========================== Cache invalidation for new write wrappers ==========================


class TestNewWriteWrapperCacheInvalidation:
    """Every new write wrapper evicts the cache bucket its resource lives in."""

    @pytest.fixture
    def client(self, mock_session):
        """A client with a preferred network and every relevant domain call stubbed."""
        client = EeroClient(session=mock_session)
        client._preferred_network_id = "network_123"
        ok = {"meta": {"code": 200}, "data": {}}
        for path in (
            "eeros.set_location",
            "eeros.get_connections",
            "networks.set_network_password",
            "networks.clear_network_password",
            "networks.set_guest_password",
            "networks.clear_guest_password",
            "sqm.set_sqm",
            "backup.set_backup_internet",
            "diagnostics.run_diagnostics",
            "updates.apply_update",
            "thread.set_thread_enabled",
            "thread.update_thread",
            "thread.regenerate_thread_credentials",
            "devices.update_device_via_link",
            "devices.set_device_type",
            "devices.set_device_labels",
            "profiles.create_profile",
        ):
            attr_path, method_name = path.rsplit(".", 1)
            setattr(getattr(client._api, attr_path), method_name, AsyncMock(return_value=ok))
        return client

    def _seed_network_cache(self, client):
        client._cache["network"]["network_123"] = {"data": {}, "timestamp": time.monotonic()}

    def _seed_eeros_cache(self, client):
        client._cache["eeros"]["network_123_eeros"] = {"data": [], "timestamp": time.monotonic()}

    def _seed_profiles_cache(self, client):
        client._cache["profiles"]["network_123_profiles"] = {
            "data": [],
            "timestamp": time.monotonic(),
        }

    def _seed_devices_cache(self, client, device_id="dev_1"):
        client._cache["devices"][f"network_123_{device_id}"] = {
            "data": {},
            "timestamp": time.monotonic(),
        }

    @pytest.mark.asyncio
    async def test_set_location_invalidates_eeros_cache(self, client):
        """Test set_location evicts the eeros bucket."""
        self._seed_eeros_cache(client)

        await client.set_location("eero_1", "Kitchen")

        assert "network_123_eeros" not in client._cache["eeros"]

    @pytest.mark.asyncio
    async def test_set_network_password_invalidates_network_cache(self, client):
        """Test set_network_password evicts the network bucket."""
        self._seed_network_cache(client)

        await client.set_network_password("hunter2")

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_clear_network_password_invalidates_network_cache(self, client):
        """Test clear_network_password evicts the network bucket."""
        self._seed_network_cache(client)

        await client.clear_network_password()

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_set_guest_password_invalidates_network_cache(self, client):
        """Test set_guest_password evicts the network bucket."""
        self._seed_network_cache(client)

        await client.set_guest_password("guestpw")

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_clear_guest_password_invalidates_network_cache(self, client):
        """Test clear_guest_password evicts the network bucket."""
        self._seed_network_cache(client)

        await client.clear_guest_password()

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_set_sqm_invalidates_network_cache(self, client):
        """Test set_sqm evicts the network bucket."""
        self._seed_network_cache(client)

        await client.set_sqm(True)

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_set_backup_internet_invalidates_network_cache(self, client):
        """Test set_backup_internet evicts the network bucket."""
        self._seed_network_cache(client)

        await client.set_backup_internet(True)

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_apply_update_invalidates_network_cache(self, client):
        """Test apply_update evicts the network bucket."""
        self._seed_network_cache(client)

        await client.apply_update()

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_set_thread_enabled_invalidates_network_cache(self, client):
        """Test set_thread_enabled evicts the network bucket."""
        self._seed_network_cache(client)

        await client.set_thread_enabled(True)

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_update_thread_invalidates_network_cache(self, client):
        """Test update_thread evicts the network bucket."""
        self._seed_network_cache(client)

        await client.update_thread(thread_enable=True)

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_regenerate_thread_credentials_invalidates_network_cache(self, client):
        """Test regenerate_thread_credentials evicts the network bucket."""
        self._seed_network_cache(client)

        await client.regenerate_thread_credentials()

        assert "network_123" not in client._cache["network"]

    @pytest.mark.asyncio
    async def test_update_device_via_link_invalidates_device_cache(self, client):
        """Test update_device_via_link evicts both the single and list device cache."""
        self._seed_devices_cache(client)
        client._cache["devices"]["network_123_devices"] = {
            "data": [],
            "timestamp": time.monotonic(),
        }

        await client.update_device_via_link("dev_1", nickname="New Name")

        assert "network_123_dev_1" not in client._cache["devices"]
        assert "network_123_devices" not in client._cache["devices"]

    @pytest.mark.asyncio
    async def test_update_device_via_link_with_profile_invalidates_profile_cache(self, client):
        """A device's profile reassignment also evicts the profile cache.

        Mirrors set_profile_devices: reassigning a device to a different
        profile changes the membership both the single cached profile and
        the cached profiles list would otherwise still report.
        """
        self._seed_devices_cache(client)
        self._seed_profiles_cache(client)
        client._cache["profiles"]["network_123_profile_1"] = {
            "data": {},
            "timestamp": time.monotonic(),
        }

        await client.update_device_via_link(
            "dev_1",
            profile="/2.2/networks/network_123/profiles/profile_1",
        )

        assert "network_123_profile_1" not in client._cache["profiles"]
        assert "network_123_profiles" not in client._cache["profiles"]

    @pytest.mark.asyncio
    async def test_update_device_via_link_without_profile_leaves_profile_cache(self, client):
        """No profile kwarg means no profile-cache side effect."""
        self._seed_devices_cache(client)
        self._seed_profiles_cache(client)

        await client.update_device_via_link("dev_1", nickname="New Name")

        assert "network_123_profiles" in client._cache["profiles"]

    @pytest.mark.asyncio
    async def test_set_device_type_invalidates_device_cache(self, client):
        """Test set_device_type evicts the device cache."""
        self._seed_devices_cache(client)

        await client.set_device_type("dev_1", "computer")

        assert "network_123_dev_1" not in client._cache["devices"]

    @pytest.mark.asyncio
    async def test_set_device_labels_invalidates_device_cache(self, client):
        """Test set_device_labels evicts the device cache."""
        self._seed_devices_cache(client)

        await client.set_device_labels("dev_1", make_label="Acme")

        assert "network_123_dev_1" not in client._cache["devices"]

    @pytest.mark.asyncio
    async def test_create_profile_invalidates_profiles_list_cache(self, client):
        """Test create_profile evicts the profiles list cache."""
        self._seed_profiles_cache(client)

        await client.create_profile("New Profile")

        assert "network_123_profiles" not in client._cache["profiles"]


# ========================== Phase 4 wrapper bindings ==========================

#: (dotted attribute path under EeroAPI, positional args, keyword args) for the
#: wrappers added with the new domain modules; the same binding check as above.
PHASE4_DOMAIN_CALL_SHAPES = [
    ("entitlements.get_features", ("net",), {}),
    ("entitlements.get_upsell_features", ("net",), {}),
    ("entitlements.get_model_capabilities", ("net",), {}),
    ("entitlements.get_premium_customer", (), {}),
    (
        "events.get_app_events",
        ("net",),
        {"page_size": 1, "timestamp": "t", "parent": _PLACEHOLDER_PARENT},
    ),
    ("events.get_network_scan", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    (
        "events.get_channel_utilization",
        ("net",),
        {
            "start": "s",
            "end": "e",
            "busy_threshold": 1,
            "eero_id": 1,
            "band": "b",
            "granularity": 5,
            "gap_data_placeholder": -1,
            "parent": _PLACEHOLDER_PARENT,
        },
    ),
    ("permissions.get_permissions", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("notifications.get_settings", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("notifications.set_settings", ("net", {}), {"parent": _PLACEHOLDER_PARENT}),
    ("notifications.has_unread", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("notifications.mark_read", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("notifications.get_history", ("net",), {"timestamp": "t", "parent": _PLACEHOLDER_PARENT}),
    ("notifications.set_push_settings", ({},), {}),
    ("dns_policies.get_advanced_content_filter", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    (
        "dns_policies.allow_domain",
        ("net", "example.test"),
        {
            "add_cname": True,
            "reason_to_allow": 1,
            "is_delete": False,
            "keep_profiles": [],
            "parent": _PLACEHOLDER_PARENT,
        },
    ),
    ("dns_policies.allow_cnames", ("net", []), {"parent": _PLACEHOLDER_PARENT}),
    (
        "dns_policies.block_domain",
        ("net", "example.test"),
        {"is_delete": False, "keep_profiles": [], "parent": _PLACEHOLDER_PARENT},
    ),
    (
        "dns_policies.allow_domain_for_profiles",
        ("net", "example.test"),
        {
            "profiles": [],
            "override": True,
            "add_cname": True,
            "reason_to_allow": 1,
            "is_delete": False,
            "parent": _PLACEHOLDER_PARENT,
        },
    ),
    (
        "dns_policies.allow_cnames_for_profiles",
        ("net", []),
        {"profiles": [], "parent": _PLACEHOLDER_PARENT},
    ),
    (
        "dns_policies.block_domain_for_profiles",
        ("net", "example.test"),
        {"profiles": [], "is_delete": False, "override": True, "parent": _PLACEHOLDER_PARENT},
    ),
    ("dns_policies.get_profile_applications", ("net", "profile"), {}),
    ("dns_policies.set_profile_blocked_applications", ("net", "profile", []), {}),
    ("members.get_members", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("members.get_invites", ("net",), {}),
    ("members.create_invite", ("net",), {"role": "admin"}),
    ("members.update_invite", ("net", "invite"), {"invite_nickname": "n"}),
    ("members.delete_invite", ("net", "invite"), {}),
    ("members.respond_to_invite", ("net",), {"accept": True, "invite_id": "i", "invite_code": "c"}),
    ("members.cancel_pending_admin", ("net",), {}),
    ("members.promote_member", ("net", "member"), {}),
    ("members.remove_admin", ("net", "user"), {}),
    ("members.query_invite", ("code",), {}),
    ("account.set_name", ("name",), {}),
    ("account.set_email", ("mail",), {}),
    ("account.verify_email", ("code",), {}),
    ("account.set_phone", ("phone",), {}),
    ("account.verify_phone", ("code",), {}),
    ("account.set_consents", (), {"marketing_emails": True}),
    ("account.get_sms_countries", (), {}),
    (
        "dhcp.set_dhcp",
        ("net",),
        {"mode": "m", "custom": {}, "custom_v2": {}, "parent": _PLACEHOLDER_PARENT},
    ),
    ("dhcp.set_connection_mode", ("net", "mode"), {"parent": _PLACEHOLDER_PARENT}),
    ("dhcp.set_nat_port_randomization", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    ("dhcp.set_pppoe", ("serial",), {"username": "u", "password": "p"}),
    ("wpa3.get_wpa3_per_band", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    (
        "wpa3.set_wpa3_per_band",
        ("net",),
        {"band_2_4_ghz": "WPA3", "band_5_ghz": "WPA3", "parent": _PLACEHOLDER_PARENT},
    ),
    ("security.set_mlo_mode", ("net", "multi"), {"parent": _PLACEHOLDER_PARENT}),
    ("security.get_fast_transition", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("security.set_fast_transition", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    ("security.set_passpoint_enabled", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    ("security.set_proxied_nodes", ("net", True), {"parent": _PLACEHOLDER_PARENT}),
    (
        "power_saving.set_power_saving",
        ("net",),
        {"enable": True, "power_saving_schedule_enabled": True, "parent": _PLACEHOLDER_PARENT},
    ),
    ("power_saving.get_schedules", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    (
        "power_saving.create_schedule",
        ("net",),
        {"name": "n", "days": [], "start_time": "s", "end_time": "e", "enabled": True},
    ),
    (
        "power_saving.update_schedule",
        ("net", "schedule"),
        {"name": "n", "days": [], "start_time": "s", "end_time": "e", "enabled": True},
    ),
    ("power_saving.delete_schedule", ("net", "schedule"), {}),
    ("ddns.enable", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("ddns.disable", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("backup_access_points.list", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("backup_access_points.add", ("net",), {"ssid": "s", "password": "p", "uuid": "u"}),
    (
        "backup_access_points.update",
        ("net", "backup"),
        {
            "ssid": "s",
            "password": "p",
            "enabled": True,
            "uuid": "u",
            "connectivity": {},
            "created": "c",
            "last_updated_at": "l",
        },
    ),
    ("backup_access_points.delete_backup_access_point", ("net", "backup"), {}),
    ("backup_access_points.rearrange", ("net", []), {}),
    ("backup_access_points.discover_ssids", ("net",), {}),
    ("backup_access_points.start_ssid_discovery", ("net",), {}),
    ("backup_access_points.connectivity_check", ("net",), {}),
    ("subnets.get_config", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("subnets.set_config", ("net", {}), {}),
    ("subnets.delete_subnet", ("net", "type"), {}),
    ("subnets.set_content_filters", ("net", {}), {}),
    ("subnets.get_content_filters", ("net", "subnet"), {}),
    ("wan.get_multistaticip", ("net",), {"parent": _PLACEHOLDER_PARENT}),
    ("wan.set_multistaticip", ("net", {}), {}),
    ("wan.set_secondary_wan_config", ("net", {}), {}),
    ("wan.set_device_secondary_wan_access", ("net", "aabbccddeeff"), {"deny": True}),
    ("eeros.node_action", ("eero", "POWER_CYCLE_ALL_PORTS"), {"parent": _PLACEHOLDER_PARENT}),
    ("eeros.port_action", ("eero", "1", "ENABLE_DATA"), {}),
    ("eeros.led_cycle", ("serial",), {"colors": [], "duration": "1", "time_per_color": "1"}),
    ("eeros.nightlight_override", ("eero",), {"brightness_percentage": 50}),
    ("eeros.get_eero_support", ("serial",), {}),
]

#: EeroClient wrapper → the domain call it forwards to (dotted path).
PHASE4_WRAPPERS = {
    "get_entitlement_features": "entitlements.get_features",
    "get_upsell_features": "entitlements.get_upsell_features",
    "get_model_capabilities": "entitlements.get_model_capabilities",
    "get_premium_customer": "entitlements.get_premium_customer",
    "get_app_events": "events.get_app_events",
    "get_network_scan": "events.get_network_scan",
    "get_channel_utilization": "events.get_channel_utilization",
    "get_permissions": "permissions.get_permissions",
    "get_notification_settings": "notifications.get_settings",
    "set_notification_settings": "notifications.set_settings",
    "has_unread_notifications": "notifications.has_unread",
    "mark_notifications_read": "notifications.mark_read",
    "get_notification_history": "notifications.get_history",
    "set_push_settings": "notifications.set_push_settings",
    "get_advanced_content_filter": "dns_policies.get_advanced_content_filter",
    "allow_domain": "dns_policies.allow_domain",
    "allow_cnames": "dns_policies.allow_cnames",
    "block_domain": "dns_policies.block_domain",
    "allow_domain_for_profiles": "dns_policies.allow_domain_for_profiles",
    "allow_cnames_for_profiles": "dns_policies.allow_cnames_for_profiles",
    "block_domain_for_profiles": "dns_policies.block_domain_for_profiles",
    "get_dns_policy_applications": "dns_policies.get_profile_applications",
    "set_profile_blocked_applications": "dns_policies.set_profile_blocked_applications",
    "get_members": "members.get_members",
    "get_invites": "members.get_invites",
    "create_invite": "members.create_invite",
    "update_invite": "members.update_invite",
    "delete_invite": "members.delete_invite",
    "respond_to_invite": "members.respond_to_invite",
    "cancel_pending_admin": "members.cancel_pending_admin",
    "promote_member": "members.promote_member",
    "remove_admin": "members.remove_admin",
    "query_invite": "members.query_invite",
    "set_account_name": "account.set_name",
    "set_account_email": "account.set_email",
    "verify_account_email": "account.verify_email",
    "set_account_phone": "account.set_phone",
    "verify_account_phone": "account.verify_phone",
    "set_account_consents": "account.set_consents",
    "get_sms_countries": "account.get_sms_countries",
    "set_dhcp": "dhcp.set_dhcp",
    "set_connection_mode": "dhcp.set_connection_mode",
    "set_nat_port_randomization": "dhcp.set_nat_port_randomization",
    "set_pppoe": "dhcp.set_pppoe",
    "get_wpa3_per_band": "wpa3.get_wpa3_per_band",
    "set_wpa3_per_band": "wpa3.set_wpa3_per_band",
    "set_mlo_mode": "security.set_mlo_mode",
    "get_fast_transition": "security.get_fast_transition",
    "set_fast_transition": "security.set_fast_transition",
    "set_passpoint_enabled": "security.set_passpoint_enabled",
    "set_proxied_nodes": "security.set_proxied_nodes",
    "set_power_saving": "power_saving.set_power_saving",
    "get_power_saving_schedules": "power_saving.get_schedules",
    "create_power_saving_schedule": "power_saving.create_schedule",
    "update_power_saving_schedule": "power_saving.update_schedule",
    "delete_power_saving_schedule": "power_saving.delete_schedule",
    "enable_ddns": "ddns.enable",
    "disable_ddns": "ddns.disable",
    "list_backup_access_points": "backup_access_points.list",
    "add_backup_access_point": "backup_access_points.add",
    "update_backup_access_point": "backup_access_points.update",
    "delete_backup_access_point": "backup_access_points.delete_backup_access_point",
    "rearrange_backup_access_points": "backup_access_points.rearrange",
    "discover_backup_ssids": "backup_access_points.discover_ssids",
    "start_backup_ssid_discovery": "backup_access_points.start_ssid_discovery",
    "backup_connectivity_check": "backup_access_points.connectivity_check",
    "get_subnets_config": "subnets.get_config",
    "set_subnets_config": "subnets.set_config",
    "delete_subnet": "subnets.delete_subnet",
    "set_subnet_content_filters": "subnets.set_content_filters",
    "get_subnet_content_filters": "subnets.get_content_filters",
    "get_multistaticip": "wan.get_multistaticip",
    "set_multistaticip": "wan.set_multistaticip",
    "set_secondary_wan_config": "wan.set_secondary_wan_config",
    "set_device_secondary_wan_access": "wan.set_device_secondary_wan_access",
    "node_action": "eeros.node_action",
    "port_action": "eeros.port_action",
    "led_cycle": "eeros.led_cycle",
    "nightlight_override": "eeros.nightlight_override",
    "get_eero_support": "eeros.get_eero_support",
}


class TestPhase4WrapperBindings:
    """Every Phase 4 wrapper forwards to a real domain method with a valid call shape."""

    @pytest.fixture
    def api(self):
        """A real EeroAPI so the bound methods are the real signatures."""
        from eero.api import EeroAPI

        return EeroAPI(use_keyring=False)

    @pytest.mark.parametrize(
        "shape", PHASE4_DOMAIN_CALL_SHAPES, ids=[s[0] for s in PHASE4_DOMAIN_CALL_SHAPES]
    )
    def test_call_shape_binds_to_the_real_domain_signature(self, api, shape):
        """The forwarded call binds against the real domain method (no missing or renamed method)."""
        path, args, kwargs = shape
        *attrs, method_name = path.split(".")
        target = api
        for attr in attrs:
            target = getattr(target, attr)
        method = getattr(target, method_name)

        inspect.signature(method).bind(*args, **kwargs)

    def test_every_wrapper_exists_and_its_target_is_in_the_shape_table(self):
        """Each listed wrapper exists on EeroClient and its target has a binding entry."""
        client = EeroClient()
        shapes = {shape[0] for shape in PHASE4_DOMAIN_CALL_SHAPES}

        for wrapper, target in PHASE4_WRAPPERS.items():
            assert callable(getattr(client, wrapper)), wrapper
            assert target in shapes, target

    @pytest.mark.parametrize(
        ("wrapper", "args", "kwargs", "bucket"),
        [
            ("set_notification_settings", ({},), {}, "network"),
            ("allow_domain", ("example.test",), {}, "network"),
            ("set_dhcp", (), {"mode": "automatic"}, "network"),
            ("set_mlo_mode", ("multi",), {}, "network"),
            ("set_power_saving", (), {"enable": True}, "network"),
            ("enable_ddns", (), {}, "network"),
            ("set_subnets_config", ({},), {}, "network"),
            ("set_multistaticip", ({},), {}, "network"),
            ("node_action", ("eero_1", "POWER_CYCLE_ALL_PORTS"), {}, "eeros"),
        ],
    )
    @pytest.mark.asyncio
    async def test_write_wrappers_invalidate_their_cache_bucket(
        self, wrapper, args, kwargs, bucket
    ):
        """A write wrapper drops the cached entry for the bucket it changes."""
        client = EeroClient()
        client._api = MagicMock()
        target = PHASE4_WRAPPERS[wrapper]
        domain, method = target.split(".")
        setattr(getattr(client._api, domain), method, AsyncMock(return_value={"meta": {}}))
        subkey = "network_123_eeros" if bucket == "eeros" else "network_123"
        client._update_cache(bucket, subkey, {"meta": {"code": 200}, "data": {}})

        await getattr(client, wrapper)(*args, **kwargs, network_id="network_123")

        assert client._get_from_cache(bucket, subkey) is None

    @pytest.mark.asyncio
    async def test_parent_is_passed_when_the_network_is_cached(self):
        """A network-scoped wrapper passes the cached envelope as parent."""
        client = EeroClient()
        client._api = MagicMock()
        client._api.permissions.get_permissions = AsyncMock(return_value={"meta": {}})
        envelope = {"meta": {"code": 200}, "data": {"url": "/2.2/networks/network_123"}}
        client._update_cache("network", "network_123", envelope)

        await client.get_permissions(network_id="network_123")

        client._api.permissions.get_permissions.assert_awaited_once_with(
            "network_123", parent=envelope
        )
