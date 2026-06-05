"""Tests for AuthAPI authentication module.

Tests cover:
- Login flow (request verification code)
- Verification flow (submit code)
- Logout
- Session management and expiry
- Token storage (keyring and file)
- Session refresh
- set_session_token / clear_session_token helpers
"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from eero.api.auth import AuthAPI
from eero.api.auth_storage import AuthCredentials
from eero.const import LOGIN_REFRESH_ENDPOINT, REFRESH_ENDPOINTS
from eero.exceptions import EeroAPIException, EeroAuthenticationException, EeroValidationException

from .conftest import api_error_response, api_success_response, create_mock_response

# Note: _mask_sensitive tests moved to tests/test_logging.py as part of SecureLogger


class TestAuthCredentials:
    """Tests for AuthCredentials dataclass."""

    def test_is_session_expired_without_expiry(self):
        """Test is_session_expired returns True without expiry."""
        creds = AuthCredentials()
        assert creds.is_session_expired() is True

    def test_is_session_expired_with_future_expiry(self):
        """Test is_session_expired returns False with future expiry."""
        creds = AuthCredentials(session_expiry=datetime.now() + timedelta(days=1))
        assert creds.is_session_expired() is False

    def test_is_session_expired_with_past_expiry(self):
        """Test is_session_expired returns True with past expiry."""
        creds = AuthCredentials(session_expiry=datetime.now() - timedelta(days=1))
        assert creds.is_session_expired() is True

    def test_has_valid_session(self):
        """Test has_valid_session with valid session."""
        creds = AuthCredentials(
            session_id="valid_session",
            session_expiry=datetime.now() + timedelta(days=1),
        )
        assert creds.has_valid_session() is True

    def test_has_valid_session_expired(self):
        """Test has_valid_session with expired session."""
        creds = AuthCredentials(
            session_id="expired_session",
            session_expiry=datetime.now() - timedelta(days=1),
        )
        assert creds.has_valid_session() is False

    def test_to_dict_and_from_dict(self):
        """Test serialization round-trip."""
        original = AuthCredentials(
            session_id="s_456",
            refresh_token="rt_789",
            session_expiry=datetime.now().replace(microsecond=0),
        )
        data = original.to_dict()
        restored = AuthCredentials.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.refresh_token == original.refresh_token
        assert restored.session_expiry == original.session_expiry

    def test_from_dict_backward_compatibility(self):
        """Test from_dict handles old format with user_token."""
        old_format = {
            "user_token": "old_token_123",
            "session_id": None,
        }
        creds = AuthCredentials.from_dict(old_format)

        # user_token should be migrated to session_id
        assert creds.session_id == "old_token_123"

    def test_clear_session(self):
        """Test clear_session clears session-related fields."""
        creds = AuthCredentials(
            session_id="s_456",
            refresh_token="rt_789",
            session_expiry=datetime.now(),
        )
        creds.clear_session()

        assert creds.session_id is None
        assert creds.session_expiry is None
        assert creds.refresh_token == "rt_789"  # Preserved

    def test_clear_all(self):
        """Test clear_all clears all auth fields."""
        creds = AuthCredentials(
            session_id="s_456",
            refresh_token="rt_789",
            session_expiry=datetime.now(),
        )
        creds.clear_all()

        assert creds.session_id is None
        assert creds.refresh_token is None
        assert creds.session_expiry is None


class TestAuthAPIInit:
    """Tests for AuthAPI initialization."""

    def test_default_init(self):
        """Test default initialization."""
        api = AuthAPI()

        assert api._session is None
        assert api._cookie_file is None
        assert api._credentials.session_id is None
        assert api._credentials.refresh_token is None
        assert api.is_authenticated is False

    def test_init_with_cookie_file(self):
        """Test initialization with cookie file."""
        api = AuthAPI(cookie_file="/path/to/cookies.json", use_keyring=False)

        assert api._cookie_file == "/path/to/cookies.json"

    def test_is_authenticated_false_without_session(self):
        """Test is_authenticated returns False without session."""
        api = AuthAPI()

        assert api.is_authenticated is False

    def test_is_authenticated_true_with_valid_session(self):
        """Test is_authenticated returns True with valid session."""
        api = AuthAPI()
        api._credentials.session_id = "valid_session"
        api._credentials.session_expiry = datetime.now() + timedelta(days=1)

        assert api.is_authenticated is True

    def test_is_authenticated_false_with_expired_session(self):
        """Test is_authenticated returns False with expired session."""
        api = AuthAPI()
        api._credentials.session_id = "expired_session"
        api._credentials.session_expiry = datetime.now() - timedelta(days=1)

        assert api.is_authenticated is False


class TestAuthAPILogin:
    """Tests for AuthAPI login flow."""

    @pytest.fixture
    def api_with_session(self, mock_session):
        """Create an AuthAPI with a mock session."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session
        return api

    @pytest.mark.asyncio
    async def test_login_success(self, api_with_session, mock_session, sample_login_response):
        """Test successful login request."""
        mock_response = create_mock_response(200, sample_login_response)
        mock_session.request.return_value = mock_response

        result = await api_with_session.login("test@example.com")

        assert result is True
        # Login stores the token in session_id (will be validated after verify)
        assert api_with_session._credentials.session_id == "ut_login_token_12345"

    @pytest.mark.asyncio
    async def test_login_clears_previous_tokens(self, api_with_session, mock_session):
        """Test that login clears previous authentication data."""
        api_with_session._credentials.session_id = "old_session"
        api_with_session._credentials.refresh_token = "old_refresh"

        mock_response = create_mock_response(200, api_success_response({"user_token": "new_token"}))
        mock_session.request.return_value = mock_response

        await api_with_session.login("test@example.com")

        assert api_with_session._credentials.session_id == "new_token"

    @pytest.mark.asyncio
    async def test_login_failure_raises_exception(self, api_with_session, mock_session):
        """Test that login failure raises authentication exception."""
        mock_response = create_mock_response(401, api_error_response(401, "invalid_credentials"))
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAuthenticationException):
            await api_with_session.login("invalid@example.com")

    @pytest.mark.asyncio
    async def test_login_no_token_returns_false(self, api_with_session, mock_session):
        """Test that login returns False when no token is received."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        result = await api_with_session.login("test@example.com")

        assert result is False


class TestAuthAPIVerify:
    """Tests for AuthAPI verification flow."""

    @pytest.fixture
    def api_pending_verification(self, mock_session):
        """Create an AuthAPI with a session_id pending verification."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session
        # Simulates state after login() - session_id set but no expiry yet
        api._credentials.session_id = "ut_pending_verification"
        return api

    @pytest.mark.asyncio
    async def test_verify_success(
        self, api_pending_verification, mock_session, sample_verify_response
    ):
        """Test successful verification."""
        mock_response = create_mock_response(200, sample_verify_response)
        mock_session.request.return_value = mock_response

        result = await api_pending_verification.verify("123456")

        assert result is True
        assert api_pending_verification._credentials.session_id == "ut_pending_verification"
        assert api_pending_verification._credentials.session_expiry is not None
        assert api_pending_verification.is_authenticated is True

    @pytest.mark.asyncio
    async def test_verify_without_session_token_raises(self, mock_session):
        """Test that verify raises without session token."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        with pytest.raises(EeroAuthenticationException, match="No session token available"):
            await api.verify("123456")

    @pytest.mark.asyncio
    async def test_verify_invalid_code_raises(self, api_pending_verification, mock_session):
        """Test that invalid verification code raises exception."""
        mock_response = create_mock_response(401, api_error_response(401, "verification.invalid"))
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAuthenticationException):
            await api_pending_verification.verify("000000")


class TestAuthAPILogout:
    """Tests for AuthAPI logout flow."""

    @pytest.fixture
    def authenticated_api(self, mock_session):
        """Create an authenticated AuthAPI."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session
        api._credentials.session_id = "active_session"
        api._credentials.session_expiry = datetime.now() + timedelta(days=1)
        return api

    @pytest.mark.asyncio
    async def test_logout_success(self, authenticated_api, mock_session):
        """Test successful logout."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        result = await authenticated_api.logout()

        assert result is True
        assert authenticated_api._credentials.session_id is None
        assert authenticated_api._credentials.refresh_token is None
        assert authenticated_api.is_authenticated is False

    @pytest.mark.asyncio
    async def test_logout_clears_cookies(self, authenticated_api, mock_session):
        """Test that logout clears cookies."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        await authenticated_api.logout()

        mock_session.cookie_jar.clear.assert_called()

    @pytest.mark.asyncio
    async def test_logout_when_not_authenticated(self, mock_session):
        """Test logout when not authenticated returns False."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        result = await api.logout()

        assert result is False


class TestAuthAPIClearAuthData:
    """Tests for clearing authentication data."""

    @pytest.mark.asyncio
    async def test_clear_auth_data(self, mock_session):
        """Test clearing all authentication data."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session
        api._credentials.session_id = "session"
        api._credentials.refresh_token = "refresh"
        api._credentials.session_expiry = datetime.now()

        await api.clear_auth_data()

        assert api._credentials.session_id is None
        assert api._credentials.refresh_token is None
        assert api._credentials.session_expiry is None
        mock_session.cookie_jar.clear.assert_called()


class TestAuthAPIKeyringStorage:
    """Tests for keyring-based token storage."""

    @pytest.mark.asyncio
    async def test_load_from_keyring(self, mock_session, mock_keyring, valid_session_data):
        """Test loading tokens from keyring."""
        mock_keyring.get_password.return_value = json.dumps(valid_session_data)

        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session

        await api._load_credentials()

        assert api._credentials.session_id == valid_session_data["session_id"]
        assert api._credentials.refresh_token == valid_session_data["refresh_token"]

    @pytest.mark.asyncio
    async def test_save_to_keyring(self, mock_session, mock_keyring):
        """Test saving tokens to keyring."""
        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session
        api._credentials.session_id = "session_123"
        api._credentials.refresh_token = "refresh_123"

        await api._save_credentials()

        mock_keyring.set_password.assert_called_once()
        call_args = mock_keyring.set_password.call_args
        assert call_args[0][0] == "eero-api"
        assert call_args[0][1] == "auth-tokens"

    @pytest.mark.asyncio
    async def test_expired_session_cleared_on_load(
        self, mock_session, mock_keyring, expired_session_data
    ):
        """Test that expired session is cleared when loaded from keyring."""
        mock_keyring.get_password.return_value = json.dumps(expired_session_data)

        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session

        await api._load_credentials()

        # Session should be cleared due to expiry
        assert api._credentials.session_id is None


class TestAuthAPIFileStorage:
    """Tests for file-based token storage."""

    @pytest.mark.asyncio
    async def test_load_from_file(self, mock_session, valid_session_data, tmp_path):
        """Test loading tokens from file."""
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
        api._credentials.session_expiry = datetime.now() + timedelta(days=1)

        await api._save_credentials()

        assert cookie_file.exists()
        saved_data = json.loads(cookie_file.read_text())
        assert saved_data["session_id"] == "session_123"

    @pytest.mark.asyncio
    async def test_load_handles_missing_file(self, mock_session, tmp_path):
        """Test that loading handles missing file gracefully."""
        cookie_file = tmp_path / "nonexistent.json"

        api = AuthAPI(session=mock_session, cookie_file=str(cookie_file), use_keyring=False)
        api._session = mock_session

        # Should not raise
        await api._load_credentials()

        assert api._credentials.session_id is None


class TestAuthAPIContextManager:
    """Tests for AuthAPI async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_loads_auth_data(self, mock_session, mock_keyring):
        """Test that entering context loads authentication data."""
        api = AuthAPI(session=mock_session, use_keyring=True)

        await api.__aenter__()

        mock_keyring.get_password.assert_called()


class TestAuthAPIResendVerification:
    """Tests for resending verification code."""

    @pytest.fixture
    def api_pending_verification(self, mock_session):
        """Create an AuthAPI with a session_id pending verification."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session
        api._credentials.session_id = "ut_pending_verification"
        return api

    @pytest.mark.asyncio
    async def test_resend_success(self, api_pending_verification, mock_session):
        """Test successful resend."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        result = await api_pending_verification.resend_verification_code()

        assert result is True

    @pytest.mark.asyncio
    async def test_resend_without_session_token_raises(self, mock_session):
        """Test resend without session token raises exception."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        with pytest.raises(EeroAuthenticationException, match="No session token available"):
            await api.resend_verification_code()


class TestAuthAPISessionRefresh:
    """Tests for session refresh functionality."""

    @pytest.fixture
    def api_with_refresh_token(self, mock_session):
        """Create an AuthAPI with refresh token."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session
        api._credentials.refresh_token = "rt_valid_refresh"
        return api

    @pytest.mark.asyncio
    async def test_refresh_session_success(self, api_with_refresh_token, mock_session):
        """Test successful session refresh via the first endpoint in REFRESH_ENDPOINTS."""
        mock_response = create_mock_response(
            200,
            api_success_response(
                {
                    "session_token": "new_session",
                    "refresh_token": "new_refresh",
                }
            ),
        )
        mock_session.request.return_value = mock_response

        result = await api_with_refresh_token.refresh_session()

        assert result is True
        assert api_with_refresh_token._credentials.session_id == "new_session"
        # Confirm the first endpoint in the ordered list was used.
        call_args = mock_session.request.call_args
        assert REFRESH_ENDPOINTS[0] in str(call_args)

    @pytest.mark.asyncio
    async def test_refresh_without_token_raises(self, mock_session):
        """Test refresh without refresh token raises exception."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        with pytest.raises(EeroAuthenticationException, match="No refresh token"):
            await api.refresh_session()

    @pytest.mark.asyncio
    async def test_refresh_session_falls_back_on_404(self, api_with_refresh_token, mock_session):
        """Test that a 404 from the first endpoint causes fall-through to the second.

        The first endpoint (LOGIN_REFRESH_ENDPOINT) returns 404; the second
        (ACCOUNT_REFRESH_ENDPOINT) succeeds.  Both endpoints must be tried in
        order and the session must be fully refreshed.
        """
        # BaseAPI.post() returns a parsed dict, not an aiohttp response object.
        success_dict = api_success_response(
            {
                "session_token": "refreshed_session",
                "refresh_token": "refreshed_token",
            }
        )

        call_count = 0

        async def side_effect(url, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if LOGIN_REFRESH_ENDPOINT in url:
                raise EeroAPIException(404, "not found")
            # Second endpoint (ACCOUNT_REFRESH_ENDPOINT) — return parsed dict.
            return success_dict

        with patch.object(api_with_refresh_token, "post", new=AsyncMock(side_effect=side_effect)):
            result = await api_with_refresh_token.refresh_session()

        assert result is True
        assert api_with_refresh_token._credentials.session_id == "refreshed_session"
        assert api_with_refresh_token._credentials.refresh_token == "refreshed_token"
        # Both endpoints must have been tried.
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_refresh_session_does_not_fall_back_on_401(
        self, api_with_refresh_token, mock_session
    ):
        """Test that a 401 from the first endpoint is treated as terminal.

        A 401 signals a real authentication failure, not a missing endpoint.
        The second endpoint must NOT be attempted and credentials must be
        cleared.
        """
        call_count = 0

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            raise EeroAPIException(401, "unauthorized")

        with patch.object(api_with_refresh_token, "post", new=AsyncMock(side_effect=side_effect)):
            result = await api_with_refresh_token.refresh_session()

        assert result is False
        # Only the first endpoint should have been tried.
        assert call_count == 1
        assert api_with_refresh_token._credentials.session_id is None
        assert api_with_refresh_token._credentials.refresh_token is None

    @pytest.mark.asyncio
    async def test_refresh_session_returns_false_if_all_endpoints_404(
        self, api_with_refresh_token, mock_session
    ):
        """Test that False is returned and credentials are cleared when every endpoint 404s.

        If neither refresh endpoint is recognised by the server, the client
        must clear credentials and return False rather than leaving stale tokens
        in place.
        """

        async def side_effect(*args, **kwargs):
            raise EeroAPIException(404, "not found")

        with patch.object(api_with_refresh_token, "post", new=AsyncMock(side_effect=side_effect)):
            result = await api_with_refresh_token.refresh_session()

        assert result is False
        assert api_with_refresh_token._credentials.session_id is None
        assert api_with_refresh_token._credentials.refresh_token is None


class TestAuthAPIEnsureAuthenticated:
    """Tests for ensure_authenticated method."""

    @pytest.mark.asyncio
    async def test_returns_false_when_not_authenticated(self, mock_session):
        """Test returns False when not authenticated."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        result = await api.ensure_authenticated()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_authenticated(self, mock_session):
        """Test returns True when authenticated."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session
        api._credentials.session_id = "valid_session"
        api._credentials.session_expiry = datetime.now() + timedelta(days=1)

        result = await api.ensure_authenticated()

        assert result is True


# ========================== SetSessionToken Tests ==========================


class TestSetSessionToken:
    """Tests for AuthAPI.set_session_token helper."""

    @pytest.mark.asyncio
    async def test_set_session_token_installs_cookie_and_credentials(
        self, mock_session, mock_cookie_jar
    ):
        """Test that set_session_token stores creds and updates the cookie jar."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        await api.set_session_token("token-abc")

        assert api._credentials.session_id == "token-abc"
        assert api._credentials.session_expiry is not None
        # Expiry should be roughly 30 days from now (allow ±5 s of clock skew).
        delta = api._credentials.session_expiry - datetime.now()
        assert timedelta(days=29, hours=23) < delta < timedelta(days=30, seconds=5)
        mock_cookie_jar.update_cookies.assert_called_with({"s": "token-abc"})

    @pytest.mark.asyncio
    async def test_set_session_token_empty_string_raises(self, mock_session):
        """Test that set_session_token raises EeroValidationException for an empty string."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        with pytest.raises(EeroValidationException):
            await api.set_session_token("")

    @pytest.mark.asyncio
    async def test_set_session_token_non_string_raises(self, mock_session):
        """Test that set_session_token raises EeroValidationException for a non-string."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        with pytest.raises(EeroValidationException):
            await api.set_session_token(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_set_session_token_persists_via_storage(self, mock_session):
        """Test that set_session_token awaits _save_credentials."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        with patch.object(api, "_save_credentials", new=AsyncMock()) as mock_save:
            await api.set_session_token("token-xyz")

        mock_save.assert_awaited_once()


# ========================== ClearSessionToken Tests ==========================


class TestClearSessionToken:
    """Tests for AuthAPI.clear_session_token helper."""

    @pytest.mark.asyncio
    async def test_clear_session_token_clears_credentials_and_cookies(
        self, mock_session, mock_cookie_jar
    ):
        """Test that clear_session_token nulls credentials and clears cookie jar."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session
        api._credentials.session_id = "existing-token"
        api._credentials.session_expiry = datetime.now() + timedelta(days=30)

        await api.clear_session_token()

        assert api._credentials.session_id is None
        assert api._credentials.session_expiry is None
        mock_cookie_jar.clear.assert_called()

    @pytest.mark.asyncio
    async def test_clear_session_token_persists_via_storage(self, mock_session):
        """Test that clear_session_token awaits _save_credentials."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session
        api._credentials.session_id = "existing-token"
        api._credentials.session_expiry = datetime.now() + timedelta(days=30)

        with patch.object(api, "_save_credentials", new=AsyncMock()) as mock_save:
            await api.clear_session_token()

        mock_save.assert_awaited_once()
