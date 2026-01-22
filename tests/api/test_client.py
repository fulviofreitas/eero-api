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
from eero.exceptions import EeroException


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
        client._api.auth._credentials.preferred_network_id = "preferred_network"

        result = await client._ensure_network_id(None, auto_discover=False)

        assert result == "preferred_network"

    @pytest.mark.asyncio
    async def test_raises_without_network_id(self, mock_session):
        """Test that exception is raised when no network ID available."""
        client = EeroClient(session=mock_session)
        client._api.auth._credentials.preferred_network_id = None

        with pytest.raises(EeroException, match="No network ID"):
            await client._ensure_network_id(None, auto_discover=False)

    @pytest.mark.asyncio
    async def test_auto_discover_networks(self, mock_session, sample_networks_list):
        """Test auto-discovery when no network ID provided."""
        client = EeroClient(session=mock_session)
        client._api.auth._credentials.preferred_network_id = None

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
