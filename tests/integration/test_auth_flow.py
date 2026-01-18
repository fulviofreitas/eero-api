"""Integration tests for authentication workflow.

Tests cover:
- Authentication state management
- Session data persistence patterns
- Error handling across auth operations
"""

from unittest.mock import MagicMock

import pytest

from eero.api.auth import AuthAPI
from eero.client import EeroClient
from eero.exceptions import EeroAuthenticationException

# ========================== Auth State Integration Tests ==========================


class TestAuthStateManagement:
    """Integration tests for authentication state management."""

    def test_auth_api_initialization(self):
        """Test AuthAPI initializes correctly."""
        auth_api = AuthAPI()

        assert auth_api.is_authenticated is False
        assert auth_api.preferred_network_id is None

    def test_auth_api_with_custom_session(self):
        """Test AuthAPI with a custom session."""
        mock_session = MagicMock()
        auth_api = AuthAPI(session=mock_session)

        assert auth_api._session == mock_session

    def test_auth_api_session_data_management(self):
        """Test AuthAPI session data management."""
        auth_api = AuthAPI()

        # Initially not authenticated
        assert auth_api.is_authenticated is False

        # After setting session data, should be authenticated
        # (Simulating what happens after successful login/verify)
        auth_api._user_token = "test_token"
        auth_api._session_id = "session_123"

        # Without expiry, still not authenticated
        assert auth_api.is_authenticated is False

    def test_preferred_network_setter(self):
        """Test setting preferred network."""
        auth_api = AuthAPI()

        auth_api.preferred_network_id = "network_123"
        assert auth_api.preferred_network_id == "network_123"


# ========================== EeroClient Auth Integration Tests ==========================


class TestEeroClientAuthState:
    """Integration tests for EeroClient authentication state."""

    def test_client_initialization(self):
        """Test EeroClient initializes correctly."""
        client = EeroClient()

        # Client should have API components
        assert hasattr(client, "_api")

    def test_client_is_authenticated_property(self):
        """Test client is_authenticated property."""
        client = EeroClient()

        # Initially not authenticated
        assert client.is_authenticated is False


# ========================== Authentication Flow Patterns ==========================


class TestAuthFlowPatterns:
    """Integration tests for authentication flow patterns."""

    @pytest.mark.asyncio
    async def test_unauthenticated_client_raises_for_protected_calls(self):
        """Test that unauthenticated client raises for protected calls."""
        async with EeroClient() as client:
            # Not authenticated, should raise
            with pytest.raises(EeroAuthenticationException):
                await client.get_networks()

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client works as async context manager."""
        async with EeroClient() as client:
            assert client is not None
            assert hasattr(client, "_api")


# ========================== Auth Error Handling Tests ==========================


class TestAuthErrorHandling:
    """Integration tests for authentication error handling."""

    @pytest.mark.asyncio
    async def test_auth_exception_contains_message(self):
        """Test that auth exceptions contain helpful messages."""
        try:
            raise EeroAuthenticationException("Test auth error")
        except EeroAuthenticationException as e:
            assert "Test auth error" in str(e)


# ========================== Cache Integration with Auth Tests ==========================


class TestCacheIntegrationWithAuth:
    """Integration tests for cache behavior with authentication."""

    def test_cache_initialization(self):
        """Test cache is properly initialized."""
        client = EeroClient()

        # Cache should exist
        assert hasattr(client, "_cache")
        assert isinstance(client._cache, dict)

    def test_cache_validity_check(self):
        """Test cache validity checking."""
        client = EeroClient()

        # Empty cache should not be valid
        assert client._is_cache_valid("nonexistent_key") is False
