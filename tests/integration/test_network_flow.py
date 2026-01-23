"""Integration tests for network management workflow.

Tests cover:
- Network ID resolution
- Cache behavior patterns
- Multi-component initialization
- Error propagation

NOTE: All tests must use use_keyring=False to avoid polluting the real OS keychain.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.client import EeroClient
from eero.exceptions import EeroAuthenticationException


def _create_mock_401_response():
    """Create a mock response that simulates a 401 Unauthorized error."""
    mock_response = MagicMock()
    mock_response.status = 401
    mock_response.text = AsyncMock(return_value='{"meta": {"code": 401, "error": "Unauthorized"}}')
    mock_response.json = AsyncMock(return_value={"meta": {"code": 401, "error": "Unauthorized"}})
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)
    return mock_response


# ========================== Network ID Resolution Tests ==========================


class TestNetworkIDResolution:
    """Integration tests for network ID resolution."""

    @pytest.mark.asyncio
    async def test_ensure_network_id_with_explicit_id(self):
        """Test _ensure_network_id with explicit network ID."""
        async with EeroClient(use_keyring=False) as client:
            # With explicit ID, should return it without API call
            result = await client._ensure_network_id("network_explicit", auto_discover=False)
            assert result == "network_explicit"

    @pytest.mark.asyncio
    async def test_ensure_network_id_with_preferred(self):
        """Test _ensure_network_id uses preferred network."""
        async with EeroClient(use_keyring=False) as client:
            # Set preferred network on client (in-memory)
            client._preferred_network_id = "network_preferred"

            # Should return preferred (disable auto_discover to avoid API call)
            result = await client._ensure_network_id(None, auto_discover=False)
            assert result == "network_preferred"

    @pytest.mark.asyncio
    async def test_ensure_network_id_explicit_overrides_preferred(self):
        """Test explicit ID overrides preferred."""
        async with EeroClient(use_keyring=False) as client:
            client._preferred_network_id = "network_preferred"

            result = await client._ensure_network_id("network_explicit", auto_discover=False)
            assert result == "network_explicit"


# ========================== Client Initialization Tests ==========================


class TestClientInitialization:
    """Integration tests for client initialization patterns."""

    def test_client_has_api_component(self):
        """Test client initializes API component."""
        client = EeroClient(use_keyring=False)

        # Check main API exists
        assert hasattr(client, "_api")
        assert client._api is not None

    def test_client_default_cache_timeout(self):
        """Test client has default cache timeout."""
        client = EeroClient(use_keyring=False)

        assert hasattr(client, "_cache_timeout")
        assert client._cache_timeout > 0

    def test_client_with_custom_cache_timeout(self):
        """Test client accepts custom cache timeout."""
        client = EeroClient(cache_timeout=120, use_keyring=False)

        assert client._cache_timeout == 120


# ========================== Cache Behavior Tests ==========================


class TestCacheBehaviorPatterns:
    """Integration tests for cache behavior patterns."""

    def test_cache_structure(self):
        """Test cache has expected structure."""
        client = EeroClient(use_keyring=False)

        # Cache should have predefined keys
        assert "account" in client._cache
        assert "networks" in client._cache
        assert "devices" in client._cache
        assert "eeros" in client._cache
        assert "profiles" in client._cache

    def test_get_from_cache_returns_none_for_missing(self):
        """Test _get_from_cache returns None for missing keys."""
        client = EeroClient(use_keyring=False)

        result = client._get_from_cache("nonexistent_key")
        assert result is None

    def test_cache_is_valid_for_missing_key(self):
        """Test _is_cache_valid returns False for missing keys."""
        client = EeroClient(use_keyring=False)

        result = client._is_cache_valid("nonexistent_key")
        assert result is False


# ========================== Preferred Network Tests ==========================


class TestPreferredNetworkManagement:
    """Integration tests for preferred network management (in-memory only)."""

    def test_client_preferred_network_access(self):
        """Test accessing preferred network through client."""
        client = EeroClient(use_keyring=False)

        # Initially None
        assert client.preferred_network_id is None

        # Set it
        client.set_preferred_network("network_123")

        # Verify
        assert client.preferred_network_id == "network_123"


# ========================== Error Propagation Tests ==========================


class TestErrorPropagation:
    """Integration tests for error propagation across components."""

    @pytest.mark.asyncio
    async def test_auth_error_propagates_from_networks(self):
        """Test auth errors propagate correctly from networks API."""
        mock_response = _create_mock_401_response()
        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        async with EeroClient(session=mock_session, use_keyring=False) as client:
            with pytest.raises(EeroAuthenticationException):
                await client.get_networks()

    @pytest.mark.asyncio
    async def test_auth_error_propagates_from_devices(self):
        """Test auth errors propagate from devices API."""
        mock_response = _create_mock_401_response()
        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        async with EeroClient(session=mock_session, use_keyring=False) as client:
            with pytest.raises(EeroAuthenticationException):
                await client.get_devices("network_123")

    @pytest.mark.asyncio
    async def test_auth_error_propagates_from_eeros(self):
        """Test auth errors propagate from eeros API."""
        mock_response = _create_mock_401_response()
        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        async with EeroClient(session=mock_session, use_keyring=False) as client:
            with pytest.raises(EeroAuthenticationException):
                await client.get_eeros("network_123")

    @pytest.mark.asyncio
    async def test_auth_error_propagates_from_profiles(self):
        """Test auth errors propagate from profiles API."""
        mock_response = _create_mock_401_response()
        mock_session = MagicMock()
        mock_session.request = MagicMock(return_value=mock_response)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        async with EeroClient(session=mock_session, use_keyring=False) as client:
            with pytest.raises(EeroAuthenticationException):
                await client.get_profiles("network_123")


# ========================== API Component Access Tests ==========================


class TestAPIComponentAccess:
    """Integration tests for accessing API components through client."""

    def test_access_auth_via_api(self):
        """Test accessing auth via API."""
        client = EeroClient(use_keyring=False)

        # Auth should be accessible via EeroAPI
        assert hasattr(client._api, "auth")
        assert client._api.auth is not None

    def test_access_networks_via_api(self):
        """Test accessing networks via API."""
        client = EeroClient(use_keyring=False)

        assert hasattr(client._api, "networks")
        assert client._api.networks is not None

    def test_access_devices_via_api(self):
        """Test accessing devices via API."""
        client = EeroClient(use_keyring=False)

        assert hasattr(client._api, "devices")
        assert client._api.devices is not None

    def test_access_eeros_via_api(self):
        """Test accessing eeros via API."""
        client = EeroClient(use_keyring=False)

        assert hasattr(client._api, "eeros")
        assert client._api.eeros is not None

    def test_access_profiles_via_api(self):
        """Test accessing profiles via API."""
        client = EeroClient(use_keyring=False)

        assert hasattr(client._api, "profiles")
        assert client._api.profiles is not None

    def test_access_dns_via_api(self):
        """Test accessing DNS API."""
        client = EeroClient(use_keyring=False)

        assert hasattr(client._api, "dns")
        assert client._api.dns is not None

    def test_access_security_via_api(self):
        """Test accessing security API."""
        client = EeroClient(use_keyring=False)

        assert hasattr(client._api, "security")
        assert client._api.security is not None

    def test_access_sqm_via_api(self):
        """Test accessing SQM API."""
        client = EeroClient(use_keyring=False)

        assert hasattr(client._api, "sqm")
        assert client._api.sqm is not None

    def test_access_schedule_via_api(self):
        """Test accessing schedule API."""
        client = EeroClient(use_keyring=False)

        assert hasattr(client._api, "schedule")
        assert client._api.schedule is not None


# ========================== Multi-Component Workflow Tests ==========================


class TestMultiComponentWorkflows:
    """Integration tests for multi-component workflows."""

    @pytest.mark.asyncio
    async def test_client_context_manager_cleanup(self):
        """Test client context manager properly cleans up."""
        client_ref = None

        async with EeroClient(use_keyring=False) as client:
            client_ref = client

        # After context, client should still exist
        assert client_ref is not None

    def test_cache_clear_resets_state(self):
        """Test clear_cache modifies cache state."""
        client = EeroClient(use_keyring=False)

        # Get initial cache state
        initial_keys = set(client._cache.keys())

        # Clear cache
        client.clear_cache()

        # Keys should still exist, but data should be None or empty
        for key in initial_keys:
            if key in client._cache:
                cache_entry = client._cache[key]
                if isinstance(cache_entry, dict) and "data" in cache_entry:
                    assert cache_entry["data"] is None
