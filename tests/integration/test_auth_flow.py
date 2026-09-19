"""Integration tests for authentication workflow.

Tests cover:
- Authentication state management
- Session data persistence patterns
- Error handling across auth operations
- The full login -> verify -> authenticated call -> server-driven refresh ->
  replay -> logout lifecycle against a mocked transport
- A regression guard proving the session token is never written into the
  shared aiohttp cookie jar

NOTE: All tests must use use_keyring=False to avoid polluting the real OS keychain.
"""

from unittest.mock import MagicMock, patch

import aiohttp
import pytest
import yarl

from eero.api.auth import AuthAPI
from eero.api.base import AuthenticatedAPI
from eero.client import EeroClient
from eero.const import (
    ACCOUNT_ENDPOINT,
    API_ENDPOINT,
    LOGIN_ENDPOINT,
    LOGIN_REFRESH_ENDPOINT,
    LOGIN_VERIFY_ENDPOINT,
    LOGOUT_ENDPOINT,
)
from eero.exceptions import EeroAuthenticationException

from ..api.conftest import (  # noqa: F401 -- mock_session/mock_cookie_jar are fixtures
    api_error_response,
    api_success_response,
    create_mock_response,
    mock_cookie_jar,
    mock_session,
)

# ========================== Auth State Integration Tests ==========================


class TestAuthStateManagement:
    """Integration tests for authentication state management."""

    def test_auth_api_initialization(self):
        """Test AuthAPI initializes correctly."""
        auth_api = AuthAPI(use_keyring=False)

        assert auth_api.is_authenticated is False

    def test_auth_api_with_custom_session(self):
        """Test AuthAPI with a custom session."""
        custom_session = MagicMock()
        auth_api = AuthAPI(session=custom_session, use_keyring=False)

        assert auth_api._session == custom_session

    def test_auth_api_session_data_management(self):
        """Test AuthAPI session data management."""
        auth_api = AuthAPI(use_keyring=False)

        # Initially not authenticated
        assert auth_api.is_authenticated is False

        # After setting a session token, the client is authenticated -- there
        # is no client-side expiry; the server is the sole authority on
        # session validity, signalled via 401 responses.
        auth_api._credentials.session_id = "session_123"

        assert auth_api.is_authenticated is True


# ========================== EeroClient Auth Integration Tests ==========================


class TestEeroClientAuthState:
    """Integration tests for EeroClient authentication state."""

    def test_client_initialization(self):
        """Test EeroClient initializes correctly."""
        client = EeroClient(use_keyring=False)

        # Client should have API components
        assert hasattr(client, "_api")

    def test_client_is_authenticated_property(self):
        """Test client is_authenticated property."""
        client = EeroClient(use_keyring=False)

        # Initially not authenticated
        assert client.is_authenticated is False


# ========================== Authentication Flow Patterns ==========================


class TestAuthFlowPatterns:
    """Integration tests for authentication flow patterns."""

    @pytest.mark.asyncio
    async def test_unauthenticated_client_raises_for_protected_calls(self):
        """Test that unauthenticated client raises for protected calls."""
        async with EeroClient(use_keyring=False) as client:
            # Not authenticated, should raise
            with pytest.raises(EeroAuthenticationException):
                await client.get_networks()

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client works as async context manager."""
        async with EeroClient(use_keyring=False) as client:
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
        client = EeroClient(use_keyring=False)

        # Cache should exist
        assert hasattr(client, "_cache")
        assert isinstance(client._cache, dict)

    def test_cache_validity_check(self):
        """Test cache validity checking."""
        client = EeroClient(use_keyring=False)

        # Empty cache should not be valid
        assert client._is_cache_valid("nonexistent_key") is False


# ========================== Full Lifecycle Integration Test ==========================


class TestAuthFullLifecycleMocked:
    """End-to-end auth lifecycle against a mocked transport.

    Exercises login -> verify -> an authenticated call that receives a
    server-driven ``error.session.refresh`` signal -> transparent refresh ->
    single replay of the original call -> logout, all against envelopes
    shaped exactly as the API returns them. Only ``session.
    request`` is mocked (the network boundary); everything above it is the
    real SDK.
    """

    @pytest.mark.asyncio
    async def test_login_verify_call_refresh_replay_logout(self, mock_session):  # noqa: F811
        login_body = api_success_response({"user_token": "ut_e2e_login_token"})
        verify_body = api_success_response({"user": {"id": "user_e2e_test"}})
        refresh_body = api_success_response({"user_token": "server_issued_ignored"})
        refresh_signal_body = api_error_response(401, "error.session.refresh")
        account_body = api_success_response({"id": "account_e2e_test"})
        logout_body = api_success_response({})

        call_log: list[str] = []
        account_call_count = 0

        def dispatch(method, url, **kwargs):
            nonlocal account_call_count
            call_log.append(url)

            if url == LOGIN_ENDPOINT:
                return create_mock_response(200, login_body)
            if url == LOGIN_VERIFY_ENDPOINT:
                return create_mock_response(200, verify_body)
            if url == LOGIN_REFRESH_ENDPOINT:
                return create_mock_response(200, refresh_body)
            if url == LOGOUT_ENDPOINT:
                return create_mock_response(200, logout_body)
            if url == ACCOUNT_ENDPOINT:
                account_call_count += 1
                if account_call_count == 1:
                    return create_mock_response(401, refresh_signal_body)
                return create_mock_response(200, account_body)

            raise AssertionError(f"Unexpected URL requested: {url}")

        mock_session.request = MagicMock(side_effect=dispatch)

        auth = AuthAPI(session=mock_session, use_keyring=False)
        authed = AuthenticatedAPI(auth, base_url=API_ENDPOINT)

        assert await auth.login("user@example.test") is True
        assert await auth.verify("123456") is True
        assert auth.is_authenticated is True

        token = await auth.get_auth_token()
        account = await authed.get("/account", auth_token=token)

        assert account == account_body
        # First attempt (401 + refresh signal) plus the single replay.
        assert account_call_count == 2
        assert LOGIN_REFRESH_ENDPOINT in call_log

        assert await auth.logout() is True
        assert auth.is_authenticated is False


# ========================== Cookie Jar Non-Leakage Regression Test ==========================


class TestAuthCredentialNeverEntersSharedCookieJar:
    """Regression guard: the session token must never reach the shared cookie jar.

    Uses a REAL aiohttp.ClientSession carrying a REAL aiohttp.CookieJar (not
    a mock), so that any auth-layer code path which still wrote the session
    token into the jar -- rather than letting the transport attach it
    per-request -- would be caught here. Only the session's ``request``
    method is patched, at the network boundary; no live requests are made.
    """

    @pytest.mark.asyncio
    async def test_no_session_cookie_leaks_into_jar_for_any_host(self):
        login_body = api_success_response({"user_token": "ut_jar_regression_login"})
        verify_body = api_success_response({"user": {"id": "user_jar_regression"}})

        def dispatch(method, url, **kwargs):
            if url == LOGIN_ENDPOINT:
                return create_mock_response(200, login_body)
            if url == LOGIN_VERIFY_ENDPOINT:
                return create_mock_response(200, verify_body)
            raise AssertionError(f"Unexpected URL requested: {url}")

        async with aiohttp.ClientSession() as session:
            with patch.object(session, "request", side_effect=dispatch):
                auth = AuthAPI(session=session, use_keyring=False)

                # Both entry points that historically wrote to the jar:
                # the externally-seeded token, and the login/verify flow.
                await auth.set_session_token("pre_existing_seed_token")
                assert await auth.login("user@example.test") is True
                assert await auth.verify("123456") is True
                assert auth.is_authenticated is True

            api_host_url = yarl.URL(API_ENDPOINT)
            foreign_url = yarl.URL("https://foreign.example.test/")

            api_host_cookies = session.cookie_jar.filter_cookies(api_host_url)
            foreign_cookies = session.cookie_jar.filter_cookies(foreign_url)

            assert "s" not in api_host_cookies
            assert "s" not in foreign_cookies
            # The jar must be empty of credentials at all times -- the
            # transport attaches the credential per request instead.
            assert len(session.cookie_jar) == 0
