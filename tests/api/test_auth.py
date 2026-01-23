"""Tests for AuthAPI authentication module.

Tests cover:
- Login flow (request verification code)
- Verification flow (submit code)
- Logout
- Session management and expiry
- Token storage (keyring and file)
- Session refresh
"""

import json
from datetime import datetime, timedelta

import pytest

from eero.api.auth import AuthAPI
from eero.api.auth_storage import AuthCredentials
from eero.exceptions import EeroAuthenticationException

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
            preferred_network_id="net_789",
            session_expiry=datetime.now().replace(microsecond=0),
        )
        data = original.to_dict()
        restored = AuthCredentials.from_dict(data)

        assert restored.session_id == original.session_id
        assert restored.refresh_token == original.refresh_token
        assert restored.preferred_network_id == original.preferred_network_id
        assert restored.session_expiry == original.session_expiry

    def test_from_dict_backward_compatibility(self):
        """Test from_dict handles old format with user_token."""
        old_format = {
            "user_token": "old_token_123",
            "session_id": None,
            "preferred_network_id": "net_789",
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
            preferred_network_id="net_789",
        )
        creds.clear_session()

        assert creds.session_id is None
        assert creds.session_expiry is None
        assert creds.refresh_token == "rt_789"  # Preserved
        assert creds.preferred_network_id == "net_789"  # Preserved

    def test_clear_all(self):
        """Test clear_all clears auth fields but preserves network preference."""
        creds = AuthCredentials(
            session_id="s_456",
            refresh_token="rt_789",
            session_expiry=datetime.now(),
            preferred_network_id="net_789",
        )
        creds.clear_all()

        assert creds.session_id is None
        assert creds.refresh_token is None
        assert creds.session_expiry is None
        assert creds.preferred_network_id == "net_789"  # Preserved

    def test_clear_all_with_preferences(self):
        """Test clear_all with include_preferences=True clears everything."""
        creds = AuthCredentials(
            session_id="s_456",
            refresh_token="rt_789",
            session_expiry=datetime.now(),
            preferred_network_id="net_789",
        )
        creds.clear_all(include_preferences=True)

        assert creds.session_id is None
        assert creds.refresh_token is None
        assert creds.session_expiry is None
        assert creds.preferred_network_id is None  # Also cleared


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
    async def test_verify_extracts_network_id(
        self, api_pending_verification, mock_session, sample_verify_response
    ):
        """Test that verification extracts network ID from response."""
        mock_response = create_mock_response(200, sample_verify_response)
        mock_session.request.return_value = mock_response

        await api_pending_verification.verify("123456")

        assert api_pending_verification._credentials.preferred_network_id == "network_123"

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
        api._credentials.preferred_network_id = "network_123"

        await api.clear_auth_data()

        assert api._credentials.session_id is None
        assert api._credentials.refresh_token is None
        assert api._credentials.session_expiry is None
        assert api._credentials.preferred_network_id is None  # Also cleared
        mock_session.cookie_jar.clear.assert_called()


class TestAuthAPIPreferredNetwork:
    """Tests for preferred network management."""

    def test_get_preferred_network_id(self):
        """Test getting preferred network ID."""
        api = AuthAPI()
        api._credentials.preferred_network_id = "network_123"

        assert api.preferred_network_id == "network_123"

    def test_set_preferred_network_id(self):
        """Test setting preferred network ID."""
        api = AuthAPI()

        api.preferred_network_id = "network_456"

        assert api._credentials.preferred_network_id == "network_456"
        assert api._preferred_network_dirty is True


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
        assert api._credentials.preferred_network_id == valid_session_data["preferred_network_id"]

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

    @pytest.mark.asyncio
    async def test_context_manager_saves_preferred_network(self, mock_session, mock_keyring):
        """Test that exiting context saves preferred network if changed."""
        api = AuthAPI(session=mock_session, use_keyring=True)
        api._session = mock_session
        api._preferred_network_dirty = True

        await api.__aenter__()
        await api.__aexit__(None, None, None)

        # Should have saved the data
        mock_keyring.set_password.assert_called()


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
        """Test successful session refresh."""
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

    @pytest.mark.asyncio
    async def test_refresh_without_token_raises(self, mock_session):
        """Test refresh without refresh token raises exception."""
        api = AuthAPI(session=mock_session, use_keyring=False)
        api._session = mock_session

        with pytest.raises(EeroAuthenticationException, match="No refresh token"):
            await api.refresh_session()


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
