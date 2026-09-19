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
import gc
import json
import logging
import os
import stat
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from eero.api.auth import AuthAPI
from eero.api.auth_storage import AuthCredentials, ChainedStorage, FileStorage
from eero.const import CREDENTIAL_SCHEMA_VERSION, DEFAULT_ACCEPT_LANGUAGE
from eero.exceptions import (
    EeroAuthenticationException,
    EeroNetworkException,
    EeroNotFoundException,
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


# ================ Credential Destruction Propagation Tests (item 1) ================


class TestCredentialDestructionPropagatesToEveryBackend:
    """Every credential-destroying path must destroy the record in EVERY backend.

    Uses a real ``ChainedStorage`` (mocked keyring + a real file on disk) so
    a stale token left behind in the non-primary backend after logout /
    clear_session_token / a terminal-refresh clear would be caught here.
    """

    @pytest.fixture
    def chained_api(self, mock_session, mock_keyring, tmp_path):
        """An authenticated AuthAPI backed by chained keyring+file storage, seeded on both sides."""
        cookie_file = tmp_path / "cookies.json"
        token = "chained_live_token"
        record = json.dumps({"session_id": token, "schema_version": CREDENTIAL_SCHEMA_VERSION})
        mock_keyring.get_password.return_value = record
        cookie_file.write_text(record)

        api = AuthAPI(session=mock_session, cookie_file=str(cookie_file), use_keyring=True)
        api._session = mock_session
        api._credentials.session_id = token
        return api, cookie_file

    @pytest.mark.asyncio
    async def test_logout_destroys_token_in_every_backend(
        self, chained_api, mock_session, mock_keyring
    ):
        """After logout, the keyring entry is deleted and the credential file is removed."""
        api, cookie_file = chained_api
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        result = await api.logout()

        assert result is True
        assert api.is_authenticated is False
        mock_keyring.delete_password.assert_called_once_with("eero-api", "auth-tokens")
        assert not cookie_file.exists()

    @pytest.mark.asyncio
    async def test_clear_session_token_destroys_token_in_every_backend(
        self, chained_api, mock_keyring
    ):
        """After clear_session_token, the keyring entry is deleted and the credential file is removed."""
        api, cookie_file = chained_api

        await api.clear_session_token()

        assert api.is_authenticated is False
        mock_keyring.delete_password.assert_called_once_with("eero-api", "auth-tokens")
        assert not cookie_file.exists()

    @pytest.mark.asyncio
    async def test_terminal_refresh_clear_destroys_token_in_every_backend(
        self, chained_api, mock_keyring
    ):
        """After a terminal-refresh clear, the keyring entry is deleted and the file is removed."""
        api, cookie_file = chained_api
        err = EeroAuthenticationException("session gone", error_code="error.session.expired")

        with patch.object(api, "post", new=AsyncMock(side_effect=err)):
            result = await api.refresh_session()

        assert result is False
        assert api.is_authenticated is False
        mock_keyring.delete_password.assert_called_once_with("eero-api", "auth-tokens")
        assert not cookie_file.exists()


# ================ ChainedStorage Single-Writer Invariant Tests (item 2) ================


class TestChainedStorageSingleWriterInvariant:
    """Promoting a fallback record into the primary must clear the fallback."""

    @pytest.mark.asyncio
    async def test_load_clears_fallback_after_promoting_into_primary(self):
        """A record found only in the fallback is promoted, then removed from the fallback."""
        primary = AsyncMock()
        # First load: primary empty; second load: the read-back after promotion.
        primary.load = AsyncMock(
            side_effect=[
                AuthCredentials(session_id=None),
                AuthCredentials(session_id="fallback_token"),
            ]
        )
        primary.save = AsyncMock()

        fallback = AsyncMock()
        fallback.load = AsyncMock(return_value=AuthCredentials(session_id="fallback_token"))
        fallback.clear = AsyncMock()

        storage = ChainedStorage(primary=primary, fallback=fallback)

        result = await storage.load()

        assert result.session_id == "fallback_token"
        primary.save.assert_awaited_once_with(AuthCredentials(session_id="fallback_token"))
        fallback.clear.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_load_keeps_fallback_when_primary_did_not_retain_the_record(self):
        """If the primary write silently failed, the fallback copy is not destroyed."""
        primary = AsyncMock()
        primary.load = AsyncMock(return_value=AuthCredentials(session_id=None))
        primary.save = AsyncMock()

        fallback = AsyncMock()
        fallback.load = AsyncMock(return_value=AuthCredentials(session_id="fallback_token"))
        fallback.clear = AsyncMock()

        storage = ChainedStorage(primary=primary, fallback=fallback)

        result = await storage.load()

        assert result.session_id == "fallback_token"
        primary.save.assert_awaited_once()
        fallback.clear.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_load_does_not_touch_fallback_when_primary_already_has_a_token(self):
        """When the primary already has a token, the fallback is never consulted or cleared."""
        primary = AsyncMock()
        primary.load = AsyncMock(return_value=AuthCredentials(session_id="primary_token"))

        fallback = AsyncMock()
        fallback.load = AsyncMock()
        fallback.clear = AsyncMock()

        storage = ChainedStorage(primary=primary, fallback=fallback)

        result = await storage.load()

        assert result.session_id == "primary_token"
        fallback.load.assert_not_awaited()
        fallback.clear.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_load_does_not_clear_fallback_when_neither_side_has_a_token(self):
        """When both sides are empty, there is nothing to promote and nothing to clear."""
        primary = AsyncMock()
        primary.load = AsyncMock(return_value=AuthCredentials(session_id=None))
        primary.save = AsyncMock()

        fallback = AsyncMock()
        fallback.load = AsyncMock(return_value=AuthCredentials(session_id=None))
        fallback.clear = AsyncMock()

        storage = ChainedStorage(primary=primary, fallback=fallback)

        result = await storage.load()

        assert result.session_id is None
        primary.save.assert_not_awaited()
        fallback.clear.assert_not_awaited()


# ================ FileStorage Atomic Secure-Permissions Tests (item 3) ================


class TestFileStorageAtomicSecurePermissions:
    """FileStorage.save() creates the file at 0600 atomically and refuses a symlinked path."""

    @pytest.mark.asyncio
    async def test_save_creates_file_with_0600_mode(self, tmp_path):
        """Test the file is created with mode 0600."""
        cookie_file = tmp_path / "cookies.json"
        storage = FileStorage(str(cookie_file))

        await storage.save(AuthCredentials(session_id="s"))

        mode = stat.S_IMODE(os.stat(cookie_file).st_mode)
        assert mode == 0o600

    @pytest.mark.asyncio
    async def test_save_refuses_symlinked_path(self, tmp_path):
        """Test that O_NOFOLLOW refuses to write through a symlink at the configured path."""
        real_target = tmp_path / "real_target.json"
        real_target.write_text("untouched")
        symlink_path = tmp_path / "cookies.json"
        symlink_path.symlink_to(real_target)

        storage = FileStorage(str(symlink_path))

        await storage.save(AuthCredentials(session_id="s"))

        # The write is refused -- the symlink target is left untouched, and
        # the path is still a symlink rather than having been replaced.
        assert real_target.read_text() == "untouched"
        assert symlink_path.is_symlink()


# ================ Identifier Redaction in Error Logging Tests (item 4) ================


class TestLoginFailureNeverLogsSubmittedIdentifier:
    """A login failure must never emit the submitted identifier into log records."""

    @pytest.mark.asyncio
    async def test_login_failure_identifier_not_in_logs(
        self, api_with_session, mock_session, caplog
    ):
        """Test that an identifier echoed back by the server is redacted out of the logs."""
        identifier = "someone-searchable@example.test"
        # Simulate a server that echoes the submitted identifier back as
        # structured fields in the error envelope.
        error_body = {
            "meta": {"code": 400, "error": "error.validation.invalid"},
            "data": {"login": identifier, "email": identifier},
        }
        mock_session.request.return_value = create_mock_response(400, error_body)

        with caplog.at_level(logging.DEBUG):
            with pytest.raises(EeroAuthenticationException):
                await api_with_session.login(identifier)

        assert identifier not in caplog.text


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
            # Retained: the explicit allowlist -- VERIFICATION and
            # SESSION_REFRESH are the only two groups that do not clear.
            ("error.verification.required", False),
            ("error.verification.invalid", False),
            ("error.login.unknown", False),
            ("error.session.refresh", False),
            # Cleared: the terminal Session group.
            ("error.session.expired", True),
            ("error.session.invalid", True),
            ("error.session.revoked", True),
            # Cleared: every other recognised group -- none of these should
            # legitimately come back from the refresh endpoint, but if one
            # did, a stale token must not be retained on its account.
            ("error.premium.user_not_subscribed", True),
            ("error.eero.offline", True),
            ("error.rate.limit", True),
            ("error.app.version.blocked", True),
            ("error.reservation.failed", True),
            ("error.form.errors", True),
            ("error.network.not.found", True),
            ("error.access.denied", True),
            # Cleared: unrecognised or absent.
            ("error.something_unrecognised", True),
            (None, True),
        ],
    )
    @pytest.mark.asyncio
    async def test_refresh_session_credential_clearing_matrix(
        self, api_with_session, error_code, should_clear
    ):
        """Credentials are retained only for an explicit allowlist of two groups.

        VERIFICATION (the account is mid-verification) and SESSION_REFRESH
        (the session is merely due for a refresh) are the only two outcomes
        that leave stored credentials untouched. Every other recognised
        group, and an unrecognised or absent error_code, clears them.
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

    @pytest.mark.parametrize(
        "escaping_exception",
        [
            EeroNotFoundException("network", "unknown_id"),
            EeroValidationException("field", "invalid"),
        ],
    )
    @pytest.mark.asyncio
    async def test_refresh_session_non_auth_exception_returns_false_without_escaping(
        self, api_with_session, escaping_exception
    ):
        """No exception class may escape the credential decision in _do_refresh.

        A 404 (EeroNotFoundException, now an EeroAPIException subclass) and a
        validation error (EeroValidationException, still a direct
        EeroException subclass) both come back from the broadened
        ``except EeroException`` fallback as a plain ``False`` -- neither
        propagates out of refresh_session(), and neither touches stored
        credentials (they were never proven invalid).
        """
        api_with_session._credentials.session_id = "sess_token"

        with patch.object(api_with_session, "post", new=AsyncMock(side_effect=escaping_exception)):
            result = await api_with_session.refresh_session()

        assert result is False
        assert api_with_session._credentials.session_id == "sess_token"

    @pytest.mark.asyncio
    async def test_refresh_session_network_error_still_propagates_after_broadening(
        self, api_with_session
    ):
        """The broadened EeroException fallback must not swallow transport failures.

        EeroNetworkException/EeroTimeoutException are EeroException
        subclasses too, but they represent "no verdict on the session was
        possible" rather than an API-level outcome, so they must still
        propagate to the caller of refresh_session() unchanged.
        """
        api_with_session._credentials.session_id = "sess_token"
        err = EeroNetworkException("connection reset")

        with patch.object(api_with_session, "post", new=AsyncMock(side_effect=err)):
            with pytest.raises(EeroNetworkException):
                await api_with_session.refresh_session()

        assert api_with_session._credentials.session_id == "sess_token"

    @pytest.mark.asyncio
    async def test_ordinary_endpoint_401_does_not_clear_credentials(
        self, authenticated_api, mock_session
    ):
        """A 401 from an ordinary (non-refresh) endpoint never clears stored credentials.

        Credential-clearing is exclusively _do_refresh's decision, reached
        only via an explicit call to refresh_session(). A transport-level
        401 from any other call -- here a plain BaseAPI.get() with no
        refresh signal, which never even triggers the refresh hook -- must
        leave the stored record completely untouched.
        """
        mock_response = create_mock_response(401, {"meta": {"code": 401}})
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAuthenticationException):
            await authenticated_api.get("/2.2/networks/some_network")

        assert authenticated_api._credentials.session_id == "active_session"
        assert authenticated_api.is_authenticated is True

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

    @pytest.mark.asyncio
    async def test_refresh_session_discards_future_from_a_different_loop(self, api_with_session):
        """A future left over from a different (e.g. closed) event loop is never awaited.

        Regression test for item 10: reusing an AuthAPI instance whose
        ``_refresh_future`` still references a future bound to a now-closed
        loop must not raise -- the stale future/loop pair is discarded and a
        fresh refresh proceeds normally on the current loop.
        """
        api_with_session._credentials.session_id = "sess_token"

        stale_loop = asyncio.new_event_loop()
        stale_future = stale_loop.create_future()
        stale_loop.close()

        api_with_session._refresh_future = stale_future
        api_with_session._refresh_future_loop = stale_loop

        with patch.object(
            api_with_session, "post", new=AsyncMock(return_value=api_success_response({}))
        ) as mock_post:
            result = await api_with_session.refresh_session()

        assert result is True
        mock_post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_refresh_session_leader_exception_with_no_waiter_is_marked_retrieved(
        self, api_with_session, caplog
    ):
        """A solo leader's failure must not leave the future's exception unretrieved.

        Without retrieving the exception on the future itself, asyncio logs
        "exception was never retrieved" (via the "asyncio" logger, at ERROR)
        when the future is garbage collected and nothing ever called
        ``.result()``/``.exception()`` on it -- which is exactly what
        happens when a refresh leader has zero concurrent waiters.
        """
        api_with_session._credentials.session_id = "sess_token"

        with patch.object(
            api_with_session,
            "post",
            new=AsyncMock(side_effect=EeroNetworkException("boom")),
        ):
            with caplog.at_level(logging.ERROR, logger="asyncio"):
                with pytest.raises(EeroNetworkException):
                    await api_with_session.refresh_session()

                gc.collect()

        assert "never retrieved" not in caplog.text


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
    async def test_set_session_token_rejects_crlf(self, api_with_session):
        """Test that a token containing CR/LF is rejected (reuses the transport's header validator)."""
        with pytest.raises(EeroValidationException):
            await api_with_session.set_session_token("abc\r\ndef")

    @pytest.mark.asyncio
    async def test_set_session_token_rejects_non_printable_ascii(self, api_with_session):
        """Test that a token containing non-printable-ASCII characters is rejected."""
        with pytest.raises(EeroValidationException):
            await api_with_session.set_session_token("token\x00withnull")

    @pytest.mark.asyncio
    async def test_set_session_token_rejected_token_is_not_persisted(self, api_with_session):
        """Test that a rejected token is never written to storage."""
        with patch.object(api_with_session, "_save_credentials", new=AsyncMock()) as mock_save:
            with pytest.raises(EeroValidationException):
                await api_with_session.set_session_token("abc\r\ndef")

        mock_save.assert_not_awaited()
        assert api_with_session._credentials.session_id is None

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
        """Test that clear_session_token destroys the record via storage.clear()."""
        with patch.object(authenticated_api._storage, "clear", new=AsyncMock()) as mock_clear:
            await authenticated_api.clear_session_token()

        mock_clear.assert_awaited_once()


# ========================== Keyring Storage Tests ==========================


class TestAuthStorageUsesSecureLogger:
    """Item 5: auth_storage.py must use the redacting SecureLoggerAdapter, not plain logging."""

    def test_module_logger_is_a_secure_logger_adapter(self):
        """Test the module-level logger is wired through get_secure_logger."""
        from eero.api import auth_storage
        from eero.logging import SecureLoggerAdapter

        assert isinstance(auth_storage._LOGGER, SecureLoggerAdapter)


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
        record. The record is migrated (session_id retained, legacy fields
        dropped) and promoted into the keyring; per the single-writer
        invariant, ChainedStorage then clears the fallback file so the
        primary is the sole remaining owner of the live record.
        """
        # A working keyring: what is set can be read back (the promotion is
        # only trusted, and the fallback only cleared, after that read-back).
        stored: dict[str, str] = {}
        mock_keyring.set_password.side_effect = lambda service, account, value: stored.__setitem__(
            "record", value
        )
        mock_keyring.get_password.side_effect = lambda service, account: stored.get("record")
        cookie_file = tmp_path / "cookies.json"
        cookie_file.write_text(json.dumps(legacy_session_data))

        api = AuthAPI(session=mock_session, cookie_file=str(cookie_file), use_keyring=True)
        api._session = mock_session

        await api._load_credentials()

        assert api._credentials.session_id == legacy_session_data["session_id"]
        assert mock_keyring.set_password.called
        saved = json.loads(mock_keyring.set_password.call_args[0][2])
        assert saved == {
            "session_id": legacy_session_data["session_id"],
            "schema_version": CREDENTIAL_SCHEMA_VERSION,
        }
        # Single-writer invariant: the fallback file no longer exists.
        assert not cookie_file.exists()


# ========================== Context Manager Tests ==========================


class TestAuthAPIContextManager:
    """Tests for AuthAPI async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_loads_auth_data(self, mock_session, mock_keyring):
        """Test that entering context loads authentication data."""
        api = AuthAPI(session=mock_session, use_keyring=True)

        await api.__aenter__()

        mock_keyring.get_password.assert_called()
