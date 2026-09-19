"""Tests for AuthAPI authentication module.

Tests cover:
- Login flow (request verification code)
- Verification flow (submit code)
- Resend verification code
- Logout
- Session refresh, including the single-flight guard for concurrent callers
- Authentication state (`is_authenticated` / `ensure_authenticated`)
- Credential storage (keyring, file, in-memory, chained) and record migration
- set_session_token / clear_session_token helpers

Note: _mask_sensitive tests moved to tests/test_logging.py as part of SecureLogger
"""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from eero.api.auth import AuthAPI
from eero.api.auth_storage import AuthCredentials
from eero.const import CREDENTIAL_SCHEMA_VERSION, DEFAULT_ACCEPT_LANGUAGE
from eero.exceptions import (
    EeroAuthenticationException,
    EeroNetworkException,
    EeroValidationException,
)

from .conftest import api_error_response, api_success_response, create_mock_response

# ========================== Shared AuthAPI Fixtures ==========================


@pytest.fixture
def api_with_session(mock_session):
    """Create an unauthenticated AuthAPI backed by a mock aiohttp session."""
    api = AuthAPI(session=mock_session, use_keyring=False)
    api._session = mock_session
    return api


@pytest.fixture
def api_pending_verification(api_with_session):
    """An AuthAPI with a session_id pending verification (post-login, pre-verify)."""
    api_with_session._credentials.session_id = "ut_pending_verification"
    return api_with_session


@pytest.fixture
def authenticated_api(api_with_session):
    """An AuthAPI with a verified, active session."""
    api_with_session._credentials.session_id = "active_session"
    return api_with_session


# ========================== AuthCredentials Tests ==========================


class TestAuthCredentials:
    """Tests for the AuthCredentials dataclass."""

    def test_to_dict_and_from_dict_round_trip(self):
        """Test that to_dict/from_dict round-trips the session token."""
        original = AuthCredentials(session_id="s_456")
        data = original.to_dict()

        assert data == {"session_id": "s_456", "schema_version": CREDENTIAL_SCHEMA_VERSION}
        assert AuthCredentials.from_dict(data).session_id == "s_456"

    def test_to_dict_includes_schema_version(self):
        """Test that every serialized record carries the schema_version marker."""
        assert AuthCredentials().to_dict()["schema_version"] == CREDENTIAL_SCHEMA_VERSION

    def test_clear_all(self):
        """Test clear_all clears the session token."""
        creds = AuthCredentials(session_id="s_456")
        creds.clear_all()

        assert creds.session_id is None


# ========================== AuthAPI Init Tests ==========================


class TestAuthAPIInit:
    """Tests for AuthAPI initialization."""

    def test_default_init(self):
        """Test default initialization."""
        api = AuthAPI()

        assert api._session is None
        assert api._cookie_file is None
        assert api._credentials.session_id is None
        assert api.is_authenticated is False

    def test_init_with_cookie_file(self):
        """Test initialization with cookie file."""
        api = AuthAPI(cookie_file="/path/to/cookies.json", use_keyring=False)

        assert api._cookie_file == "/path/to/cookies.json"

    def test_is_authenticated_false_without_session(self):
        """Test is_authenticated returns False without a session token."""
        api = AuthAPI()

        assert api.is_authenticated is False

    def test_is_authenticated_true_with_session_token(self):
        """Test is_authenticated returns True whenever a session token is present."""
        api = AuthAPI()
        api._credentials.session_id = "valid_session"

        assert api.is_authenticated is True

    def test_init_forwards_transport_options_to_base_api(self):
        """Test that keyword-only transport options are forwarded to BaseAPI."""
        api = AuthAPI(
            use_keyring=False,
            send_legacy_cookie=False,
            accept_language="pt-BR",
            get_retries=3,
        )

        assert api._send_legacy_cookie is False
        assert api._accept_language == "pt-BR"
        assert api._get_retries == 3

    def test_init_defaults_for_transport_options(self):
        """Test the default values of the keyword-only transport options."""
        api = AuthAPI(use_keyring=False)

        assert api._send_legacy_cookie is True
        assert api._accept_language == DEFAULT_ACCEPT_LANGUAGE
        assert api._get_retries == 0


# ========================== Login Tests ==========================


class TestAuthAPILogin:
    """Tests for AuthAPI login flow."""

    @pytest.mark.asyncio
    async def test_login_success(self, api_with_session, mock_session, sample_login_response):
        """Test successful login request."""
        mock_session.request.return_value = create_mock_response(200, sample_login_response)

        result = await api_with_session.login("user@example.test")

        assert result is True
        assert api_with_session._credentials.session_id == "ut_login_token_12345"

    @pytest.mark.asyncio
    async def test_login_clears_previous_tokens(self, api_with_session, mock_session):
        """Test that login clears previous authentication data."""
        api_with_session._credentials.session_id = "old_session"

        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"user_token": "new_token"})
        )

        await api_with_session.login("user@example.test")

        assert api_with_session._credentials.session_id == "new_token"

    @pytest.mark.asyncio
    async def test_login_failure_raises_exception(self, api_with_session, mock_session):
        """Test that a 401 login failure raises EeroAuthenticationException."""
        mock_session.request.return_value = create_mock_response(
            401, api_error_response(401, "invalid_credentials")
        )

        with pytest.raises(EeroAuthenticationException):
            await api_with_session.login("invalid@example.test")

    @pytest.mark.asyncio
    async def test_login_api_error_wrapped_as_authentication_exception(
        self, api_with_session, mock_session
    ):
        """Test that a non-401 API error is wrapped, preserving envelope and error_code."""
        mock_session.request.return_value = create_mock_response(
            400, api_error_response(400, "invalid.identifier")
        )

        with pytest.raises(EeroAuthenticationException) as exc_info:
            await api_with_session.login("bad-identifier")

        assert exc_info.value.error_code == "invalid.identifier"
        assert exc_info.value.envelope is not None

    @pytest.mark.asyncio
    async def test_login_no_token_returns_false(self, api_with_session, mock_session):
        """Test that login returns False when no token is received."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        result = await api_with_session.login("user@example.test")

        assert result is False

    @pytest.mark.asyncio
    async def test_login_network_error_raises(self, api_with_session, mock_session):
        """Test that a network error during login raises EeroNetworkException."""
        mock_session.request.side_effect = aiohttp.ClientConnectionError("boom")

        with pytest.raises(EeroNetworkException):
            await api_with_session.login("user@example.test")


# ========================== Verify Tests ==========================


class TestAuthAPIVerify:
    """Tests for AuthAPI verification flow."""

    @pytest.mark.asyncio
    async def test_verify_success(
        self, api_pending_verification, mock_session, sample_verify_response
    ):
        """Test successful verification."""
        mock_session.request.return_value = create_mock_response(200, sample_verify_response)

        result = await api_pending_verification.verify("123456")

        assert result is True
        assert api_pending_verification._credentials.session_id == "ut_pending_verification"
        assert api_pending_verification.is_authenticated is True

    @pytest.mark.asyncio
    async def test_verify_without_session_token_raises(self, api_with_session):
        """Test that verify raises without a session token."""
        with pytest.raises(EeroAuthenticationException, match="No session token available"):
            await api_with_session.verify("123456")

    @pytest.mark.asyncio
    async def test_verify_invalid_code_raises_with_envelope(
        self, api_pending_verification, mock_session
    ):
        """Test that an invalid verification code surfaces error_code and envelope.

        Regression test for the previously-unreachable status_code==401 branch:
        the transport raises EeroAuthenticationException directly for a 401, so
        verify() must not rely on catching EeroAPIException for this case.
        """
        mock_session.request.return_value = create_mock_response(
            401, api_error_response(401, "verification.invalid")
        )

        with pytest.raises(EeroAuthenticationException) as exc_info:
            await api_pending_verification.verify("000000")

        assert exc_info.value.error_code == "verification.invalid"
        assert exc_info.value.envelope is not None

    @pytest.mark.asyncio
    async def test_verify_network_error_raises(self, api_pending_verification, mock_session):
        """Test that a network error during verify raises EeroNetworkException."""
        mock_session.request.side_effect = aiohttp.ClientConnectionError("boom")

        with pytest.raises(EeroNetworkException):
            await api_pending_verification.verify("123456")


# ========================== Resend Verification Tests ==========================


class TestAuthAPIResendVerification:
    """Tests for resending the verification code."""

    @pytest.mark.asyncio
    async def test_resend_success(self, api_pending_verification, mock_session):
        """Test successful resend."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        result = await api_pending_verification.resend_verification_code()

        assert result is True

    @pytest.mark.asyncio
    async def test_resend_without_session_token_raises(self, api_with_session):
        """Test resend without a session token raises."""
        with pytest.raises(EeroAuthenticationException, match="No session token available"):
            await api_with_session.resend_verification_code()

    @pytest.mark.asyncio
    async def test_resend_api_error_returns_false(self, api_pending_verification, mock_session):
        """Test that an API-level failure returns False rather than raising."""
        mock_session.request.return_value = create_mock_response(
            400, api_error_response(400, "rate.limited")
        )

        result = await api_pending_verification.resend_verification_code()

        assert result is False

    @pytest.mark.asyncio
    async def test_resend_network_error_raises(self, api_pending_verification, mock_session):
        """Test that a network error during resend raises EeroNetworkException."""
        mock_session.request.side_effect = aiohttp.ClientConnectionError("boom")

        with pytest.raises(EeroNetworkException):
            await api_pending_verification.resend_verification_code()


# ========================== Logout Tests ==========================


class TestAuthAPILogout:
    """Tests for AuthAPI logout flow."""

    @pytest.mark.asyncio
    async def test_logout_success(self, authenticated_api, mock_session):
        """Test successful logout."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        result = await authenticated_api.logout()

        assert result is True
        assert authenticated_api._credentials.session_id is None
        assert authenticated_api.is_authenticated is False

    @pytest.mark.asyncio
    async def test_logout_does_not_touch_cookie_jar(
        self, authenticated_api, mock_session, mock_cookie_jar
    ):
        """Test that logout never touches the shared cookie jar."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await authenticated_api.logout()

        mock_cookie_jar.clear.assert_not_called()
        mock_cookie_jar.update_cookies.assert_not_called()

    @pytest.mark.asyncio
    async def test_logout_when_not_authenticated(self, api_with_session):
        """Test logout when not authenticated returns False without a request."""
        result = await api_with_session.logout()

        assert result is False

    @pytest.mark.asyncio
    async def test_logout_clears_credentials_even_on_api_error(
        self, authenticated_api, mock_session
    ):
        """Test that local credentials are cleared even when the server call fails."""
        mock_session.request.return_value = create_mock_response(
            500, api_error_response(500, "server.error")
        )

        result = await authenticated_api.logout()

        assert result is True
        assert authenticated_api._credentials.session_id is None

    @pytest.mark.asyncio
    async def test_logout_clears_credentials_on_network_error(
        self, authenticated_api, mock_session
    ):
        """Test that local credentials are cleared even when the request fails at the network level."""
        mock_session.request.side_effect = aiohttp.ClientConnectionError("boom")

        result = await authenticated_api.logout()

        assert result is True
        assert authenticated_api._credentials.session_id is None


# ========================== Clear Auth Data Tests ==========================


class TestAuthAPIClearAuthData:
    """Tests for clearing authentication data."""

    @pytest.mark.asyncio
    async def test_clear_auth_data(self, api_with_session, mock_cookie_jar):
        """Test clearing all authentication data."""
        api_with_session._credentials.session_id = "session"

        await api_with_session.clear_auth_data()

        assert api_with_session._credentials.session_id is None

    @pytest.mark.asyncio
    async def test_clear_auth_data_does_not_touch_cookie_jar(
        self, api_with_session, mock_cookie_jar
    ):
        """Test that clear_auth_data never touches the shared cookie jar."""
        api_with_session._credentials.session_id = "session"

        await api_with_session.clear_auth_data()

        mock_cookie_jar.clear.assert_not_called()
        mock_cookie_jar.update_cookies.assert_not_called()


# ========================== Request Encoding Tests ==========================


class TestAuthAPIRequestEncoding:
    """Parametrised assertions that each auth operation sends the wire shape the API expects."""

    @pytest.mark.asyncio
    async def test_login_sends_form_encoded_login_field(
        self, api_with_session, mock_session, sample_login_response
    ):
        """Test login POSTs a single form-encoded 'login' field."""
        mock_session.request.return_value = create_mock_response(200, sample_login_response)

        await api_with_session.login("user@example.test")

        _, kwargs = mock_session.request.call_args
        assert kwargs["data"] == {"login": "user@example.test"}
        assert kwargs.get("json") is None

    @pytest.mark.asyncio
    async def test_verify_sends_form_encoded_code_field(
        self, api_pending_verification, mock_session, sample_verify_response
    ):
        """Test verify POSTs a single form-encoded 'code' field."""
        mock_session.request.return_value = create_mock_response(200, sample_verify_response)

        await api_pending_verification.verify("654321")

        _, kwargs = mock_session.request.call_args
        assert kwargs["data"] == {"code": "654321"}
        assert kwargs.get("json") is None

    @pytest.mark.asyncio
    async def test_resend_sends_empty_json_body(self, api_pending_verification, mock_session):
        """Test resend POSTs an empty JSON object."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api_pending_verification.resend_verification_code()

        _, kwargs = mock_session.request.call_args
        assert kwargs["json"] == {}
        assert kwargs.get("data") is None

    @pytest.mark.asyncio
    async def test_logout_sends_form_encoded_cookie_field(self, authenticated_api, mock_session):
        """Test logout POSTs a single form field literally named 'Cookie'."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        token = authenticated_api._credentials.session_id

        await authenticated_api.logout()

        _, kwargs = mock_session.request.call_args
        assert kwargs["data"] == {"Cookie": f"s={token}"}
        assert kwargs.get("json") is None

    @pytest.mark.asyncio
    async def test_refresh_sends_empty_json_string_body(self, api_with_session, mock_session):
        """Test refresh POSTs the literal two-byte '""' body with a JSON content type."""
        api_with_session._credentials.session_id = "sess_token"
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"user_token": "server_issued_ignored"})
        )

        await api_with_session.refresh_session()

        _, kwargs = mock_session.request.call_args
        assert kwargs["data"] == '""'
        assert kwargs["headers"]["Content-Type"] == "application/json"


# ========================== Credential Attachment Tests ==========================


class TestAuthAPICredentialAttachment:
    """Tests that authenticated auth operations attach the credential header, and login does not."""

    @pytest.mark.asyncio
    async def test_login_has_no_credential_header(
        self, api_with_session, mock_session, sample_login_response
    ):
        """Test login (no token yet) sends no X-User-Token header."""
        mock_session.request.return_value = create_mock_response(200, sample_login_response)

        await api_with_session.login("user@example.test")

        _, kwargs = mock_session.request.call_args
        assert "X-User-Token" not in kwargs["headers"]

    @pytest.mark.asyncio
    async def test_verify_has_credential_header(
        self, api_pending_verification, mock_session, sample_verify_response
    ):
        """Test verify sends the session token as X-User-Token."""
        mock_session.request.return_value = create_mock_response(200, sample_verify_response)

        await api_pending_verification.verify("123456")

        _, kwargs = mock_session.request.call_args
        assert kwargs["headers"]["X-User-Token"] == "ut_pending_verification"

    @pytest.mark.asyncio
    async def test_resend_has_credential_header(self, api_pending_verification, mock_session):
        """Test resend sends the session token as X-User-Token."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api_pending_verification.resend_verification_code()

        _, kwargs = mock_session.request.call_args
        assert kwargs["headers"]["X-User-Token"] == "ut_pending_verification"

    @pytest.mark.asyncio
    async def test_logout_has_credential_header(self, authenticated_api, mock_session):
        """Test logout sends the session token as X-User-Token."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await authenticated_api.logout()

        _, kwargs = mock_session.request.call_args
        assert kwargs["headers"]["X-User-Token"] == "active_session"

    @pytest.mark.asyncio
    async def test_refresh_has_credential_header(self, api_with_session, mock_session):
        """Test refresh sends the session token as X-User-Token."""
        api_with_session._credentials.session_id = "sess_token"
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api_with_session.refresh_session()

        _, kwargs = mock_session.request.call_args
        assert kwargs["headers"]["X-User-Token"] == "sess_token"


# ========================== Session Refresh Tests ==========================


class TestAuthAPISessionRefresh:
    """Tests for session refresh functionality."""

    @pytest.mark.asyncio
    async def test_refresh_session_success(self, api_with_session, mock_session):
        """Test a successful refresh returns True."""
        api_with_session._credentials.session_id = "sess_token"
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"user_token": "server_issued"})
        )

        result = await api_with_session.refresh_session()

        assert result is True

    @pytest.mark.asyncio
    async def test_refresh_session_ignores_server_issued_token(
        self, api_with_session, mock_session
    ):
        """Test the server-issued token in the refresh response is ignored (Q22)."""
        api_with_session._credentials.session_id = "sess_token"
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"user_token": "a_completely_different_token"})
        )

        await api_with_session.refresh_session()

        assert api_with_session._credentials.session_id == "sess_token"

    @pytest.mark.asyncio
    async def test_refresh_without_session_token_raises(self, api_with_session):
        """Test refresh without a session token raises."""
        with pytest.raises(EeroAuthenticationException, match="No session token available"):
            await api_with_session.refresh_session()

    @pytest.mark.asyncio
    async def test_refresh_session_network_error_raises(self, api_with_session, mock_session):
        """Test a network error during refresh raises EeroNetworkException."""
        api_with_session._credentials.session_id = "sess_token"
        mock_session.request.side_effect = aiohttp.ClientConnectionError("boom")

        with pytest.raises(EeroNetworkException):
            await api_with_session.refresh_session()

    @pytest.mark.parametrize(
        "error_code,should_clear",
        [
            ("error.verification.required", False),
            ("error.verification.invalid", False),
            ("error.login.unknown", False),
            ("error.session.refresh", False),
            ("error.session.expired", True),
            ("error.session.invalid", True),
            ("error.session.revoked", True),
            ("error.something_unrecognised", True),
            (None, True),
        ],
    )
    @pytest.mark.asyncio
    async def test_refresh_session_credential_clearing_matrix(
        self, api_with_session, error_code, should_clear
    ):
        """Credentials clear only for the catalogue's Session group or an unrecognised/absent code.

        The verification/login-state group and the session-refresh signal
        itself both leave stored credentials untouched -- the session is
        mid-verification or merely due for a refresh, not gone.
        """
        api_with_session._credentials.session_id = "sess_token"
        err = EeroAuthenticationException("unauthorized", error_code=error_code)

        with patch.object(api_with_session, "post", new=AsyncMock(side_effect=err)):
            result = await api_with_session.refresh_session()

        assert result is False
        if should_clear:
            assert api_with_session._credentials.session_id is None
        else:
            assert api_with_session._credentials.session_id == "sess_token"

    @pytest.mark.asyncio
    async def test_refresh_session_single_flight_across_concurrent_callers(self, api_with_session):
        """Test that N concurrent refresh_session() callers share exactly one HTTP call."""
        api_with_session._credentials.session_id = "sess_token"
        call_count = 0

        async def slow_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.02)
            return api_success_response({"user_token": "ignored_token"})

        with patch.object(api_with_session, "post", new=AsyncMock(side_effect=slow_post)):
            results = await asyncio.gather(*(api_with_session.refresh_session() for _ in range(5)))

        assert results == [True] * 5
        assert call_count == 1
        assert api_with_session._credentials.session_id == "sess_token"

    @pytest.mark.asyncio
    async def test_refresh_session_waiter_times_out_with_false(self, api_with_session, monkeypatch):
        """Test a waiter that outlasts the guard timeout gives up and returns False."""
        monkeypatch.setattr("eero.api.auth._SESSION_REFRESH_GUARD_TIMEOUT_SECONDS", 0.01)
        api_with_session._credentials.session_id = "sess_token"

        async def slow_post(*args, **kwargs):
            await asyncio.sleep(0.2)
            return api_success_response({"user_token": "ignored_token"})

        with patch.object(api_with_session, "post", new=AsyncMock(side_effect=slow_post)):
            leader_task = asyncio.create_task(api_with_session.refresh_session())
            # Yield once so the leader claims the in-flight future before we
            # issue the waiter's call.
            await asyncio.sleep(0)

            waiter_result = await api_with_session.refresh_session()
            leader_result = await leader_task

        assert waiter_result is False
        assert leader_result is True


# ========================== Ensure Authenticated Tests ==========================


class TestAuthAPIEnsureAuthenticated:
    """Tests for ensure_authenticated method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_not_authenticated(self, api_with_session):
        """Test returns False when not authenticated."""
        result = await api_with_session.ensure_authenticated()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_authenticated(self, authenticated_api):
        """Test returns True when authenticated."""
        result = await authenticated_api.ensure_authenticated()

        assert result is True

    @pytest.mark.asyncio
    async def test_does_not_trigger_a_request(self, authenticated_api, mock_session):
        """Test ensure_authenticated never makes a network call -- refreshes are server-driven only."""
        await authenticated_api.ensure_authenticated()

        mock_session.request.assert_not_called()


# ========================== SetSessionToken Tests ==========================


class TestSetSessionToken:
    """Tests for AuthAPI.set_session_token helper."""

    @pytest.mark.asyncio
    async def test_set_session_token_stores_credentials(self, api_with_session):
        """Test that set_session_token stores the token in memory."""
        await api_with_session.set_session_token("token-abc")

        assert api_with_session._credentials.session_id == "token-abc"

    @pytest.mark.asyncio
    async def test_set_session_token_does_not_touch_cookie_jar(
        self, api_with_session, mock_cookie_jar
    ):
        """Test that set_session_token never touches the shared cookie jar."""
        await api_with_session.set_session_token("token-abc")

        mock_cookie_jar.update_cookies.assert_not_called()
        mock_cookie_jar.clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_session_token_empty_string_raises(self, api_with_session):
        """Test that set_session_token raises EeroValidationException for an empty string."""
        with pytest.raises(EeroValidationException):
            await api_with_session.set_session_token("")

    @pytest.mark.asyncio
    async def test_set_session_token_non_string_raises(self, api_with_session):
        """Test that set_session_token raises EeroValidationException for a non-string."""
        with pytest.raises(EeroValidationException):
            await api_with_session.set_session_token(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_set_session_token_persists_via_storage(self, api_with_session):
        """Test that set_session_token awaits _save_credentials."""
        with patch.object(api_with_session, "_save_credentials", new=AsyncMock()) as mock_save:
            await api_with_session.set_session_token("token-xyz")

        mock_save.assert_awaited_once()


# ========================== ClearSessionToken Tests ==========================


class TestClearSessionToken:
    """Tests for AuthAPI.clear_session_token helper."""

    @pytest.mark.asyncio
    async def test_clear_session_token_clears_credentials(self, authenticated_api):
        """Test that clear_session_token nulls the session token."""
        await authenticated_api.clear_session_token()

        assert authenticated_api._credentials.session_id is None

    @pytest.mark.asyncio
    async def test_clear_session_token_does_not_touch_cookie_jar(
        self, authenticated_api, mock_cookie_jar
    ):
        """Test that clear_session_token never touches the shared cookie jar."""
        await authenticated_api.clear_session_token()

        mock_cookie_jar.update_cookies.assert_not_called()
        mock_cookie_jar.clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_session_token_persists_via_storage(self, authenticated_api):
        """Test that clear_session_token awaits _save_credentials."""
        with patch.object(authenticated_api, "_save_credentials", new=AsyncMock()) as mock_save:
            await authenticated_api.clear_session_token()

        mock_save.assert_awaited_once()


# ========================== Keyring Storage Tests ==========================


class TestAuthAPIKeyringStorage:
    """Tests for keyring-based token storage."""

    @pytest.mark.asyncio
    async def test_load_from_keyring(self, mock_session, mock_keyring, valid_session_data):
        """Test loading a current-schema record from keyring."""
        mock_keyring.get_password.return_value = json.dumps(valid_session_data)

        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session

        await api._load_credentials()

        assert api._credentials.session_id == valid_session_data["session_id"]

    @pytest.mark.asyncio
    async def test_save_to_keyring(self, mock_session, mock_keyring):
        """Test saving tokens to keyring."""
        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session
        api._credentials.session_id = "session_123"

        await api._save_credentials()

        mock_keyring.set_password.assert_called_once()
        call_args = mock_keyring.set_password.call_args
        assert call_args[0][0] == "eero-api"
        assert call_args[0][1] == "auth-tokens"
        saved = json.loads(call_args[0][2])
        assert saved == {"session_id": "session_123", "schema_version": CREDENTIAL_SCHEMA_VERSION}


# ========================== File Storage Tests ==========================


class TestAuthAPIFileStorage:
    """Tests for file-based token storage."""

    @pytest.mark.asyncio
    async def test_load_from_file(self, mock_session, valid_session_data, tmp_path):
        """Test loading a current-schema record from file."""
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps(valid_session_data))

        api = AuthAPI(session=mock_session, cookie_file=str(cookie_file), use_keyring=False)
        api._session = mock_session

        await api._load_credentials()

        assert api._credentials.session_id == valid_session_data["session_id"]

    @pytest.mark.asyncio
    async def test_save_to_file(self, mock_session, tmp_path):
        """Test saving tokens to file."""
        cookie_file = tmp_path / "cookies.json"

        api = AuthAPI(session=mock_session, cookie_file=str(cookie_file), use_keyring=False)
        api._session = mock_session
        api._credentials.session_id = "session_123"

        await api._save_credentials()

        assert cookie_file.exists()
        saved_data = json.loads(cookie_file.read_text())
        assert saved_data == {
            "session_id": "session_123",
            "schema_version": CREDENTIAL_SCHEMA_VERSION,
        }

    @pytest.mark.asyncio
    async def test_load_handles_missing_file(self, mock_session, tmp_path):
        """Test that loading handles a missing file gracefully."""
        cookie_file = tmp_path / "nonexistent.json"

        api = AuthAPI(session=mock_session, cookie_file=str(cookie_file), use_keyring=False)
        api._session = mock_session

        # Should not raise
        await api._load_credentials()

        assert api._credentials.session_id is None


# ========================== Credential Migration Tests ==========================


class TestCredentialMigration:
    """Tests for migrating pre-schema-version (7.x or earlier) credential records."""

    @pytest.mark.asyncio
    async def test_keyring_migrates_legacy_session_id_record(
        self, mock_session, mock_keyring, legacy_session_data
    ):
        """Test that a legacy session_id-based record is migrated on load."""
        mock_keyring.get_password.return_value = json.dumps(legacy_session_data)

        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session

        await api._load_credentials()

        assert api._credentials.session_id == legacy_session_data["session_id"]
        saved = json.loads(mock_keyring.set_password.call_args[0][2])
        assert saved == {
            "session_id": legacy_session_data["session_id"],
            "schema_version": CREDENTIAL_SCHEMA_VERSION,
        }

    @pytest.mark.asyncio
    async def test_keyring_migrates_legacy_user_token_record(
        self, mock_session, mock_keyring, legacy_user_token_data
    ):
        """Test that an even-older user_token-keyed record is migrated on load."""
        mock_keyring.get_password.return_value = json.dumps(legacy_user_token_data)

        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session

        await api._load_credentials()

        assert api._credentials.session_id == legacy_user_token_data["user_token"]

    @pytest.mark.asyncio
    async def test_keyring_migration_is_idempotent(
        self, mock_session, mock_keyring, legacy_session_data
    ):
        """Test that loading an already-migrated record does not save again."""
        mock_keyring.get_password.return_value = json.dumps(legacy_session_data)

        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session

        await api._load_credentials()
        assert mock_keyring.set_password.call_count == 1

        migrated_record = mock_keyring.set_password.call_args[0][2]
        mock_keyring.get_password.return_value = migrated_record
        mock_keyring.set_password.reset_mock()

        await api._load_credentials()

        mock_keyring.set_password.assert_not_called()

    @pytest.mark.asyncio
    async def test_keyring_migration_logs_no_token_value(
        self, mock_session, mock_keyring, legacy_session_data, caplog
    ):
        """Test that migration is logged at DEBUG without leaking the token value."""
        mock_keyring.get_password.return_value = json.dumps(legacy_session_data)

        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session

        with caplog.at_level(logging.DEBUG, logger="eero.api.auth_storage"):
            await api._load_credentials()

        assert legacy_session_data["session_id"] not in caplog.text

    @pytest.mark.asyncio
    async def test_file_migrates_legacy_record(self, mock_session, legacy_session_data, tmp_path):
        """Test that a legacy file record is migrated in place on load."""
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps(legacy_session_data))

        api = AuthAPI(session=mock_session, cookie_file=str(cookie_file), use_keyring=False)
        api._session = mock_session

        await api._load_credentials()

        assert api._credentials.session_id == legacy_session_data["session_id"]
        saved = json.loads(cookie_file.read_text())
        assert saved == {
            "session_id": legacy_session_data["session_id"],
            "schema_version": CREDENTIAL_SCHEMA_VERSION,
        }

    @pytest.mark.asyncio
    async def test_file_migration_is_idempotent(self, mock_session, legacy_session_data, tmp_path):
        """Test that a second load of an already-migrated file does not rewrite it."""
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps(legacy_session_data))

        api = AuthAPI(session=mock_session, cookie_file=str(cookie_file), use_keyring=False)
        api._session = mock_session

        await api._load_credentials()
        first_mtime = cookie_file.stat().st_mtime_ns

        await api._load_credentials()

        assert cookie_file.stat().st_mtime_ns == first_mtime

    @pytest.mark.asyncio
    async def test_chained_storage_migrates_fallback_only_legacy_record(
        self, mock_session, mock_keyring, legacy_session_data, tmp_path
    ):
        """Test a legacy record held only by the fallback (file) side.

        Keyring (primary) is empty; the file (fallback) holds a legacy
        record. Both the file (via its own migration) and the keyring (via
        ChainedStorage priming the primary from a successful fallback load)
        end up holding the migrated, schema-versioned record.
        """
        mock_keyring.get_password.return_value = None
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps(legacy_session_data))

        api = AuthAPI(session=mock_session, cookie_file=str(cookie_file), use_keyring=True)
        api._session = mock_session

        await api._load_credentials()

        assert api._credentials.session_id == legacy_session_data["session_id"]
        assert json.loads(cookie_file.read_text())["schema_version"] == CREDENTIAL_SCHEMA_VERSION
        assert mock_keyring.set_password.called


# ========================== Context Manager Tests ==========================


class TestAuthAPIContextManager:
    """Tests for AuthAPI async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_loads_auth_data(self, mock_session, mock_keyring):
        """Test that entering context loads authentication data."""
        api = AuthAPI(session=mock_session, use_keyring=True)

        await api.__aenter__()

        mock_keyring.get_password.assert_called()
