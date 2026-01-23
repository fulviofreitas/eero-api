"""Tests for EeroAPI facade class.

Tests cover:
- API composition (sub-APIs are properly initialized)
- Context manager lifecycle
- Authentication delegation
- Preferred network management
"""

from unittest.mock import AsyncMock

import pytest

from eero.api import EeroAPI
from eero.api.auth import AuthAPI
from eero.api.devices import DevicesAPI
from eero.api.eeros import EerosAPI
from eero.api.networks import NetworksAPI
from eero.api.profiles import ProfilesAPI


class TestEeroAPIInit:
    """Tests for EeroAPI initialization."""

    def test_default_init(self):
        """Test default initialization creates sub-APIs."""
        api = EeroAPI()

        assert api.auth is not None
        assert isinstance(api.auth, AuthAPI)

    def test_init_with_session(self, mock_session):
        """Test initialization with existing session."""
        api = EeroAPI(session=mock_session)

        assert api.auth._session is mock_session

    def test_init_with_cookie_file(self):
        """Test initialization with cookie file."""
        api = EeroAPI(cookie_file="/path/to/cookies.json", use_keyring=False)

        assert api.auth._cookie_file == "/path/to/cookies.json"
        # Storage is now encapsulated - we verify via the storage type
        from eero.api.auth_storage import FileStorage

        assert isinstance(api.auth._storage, FileStorage)

    def test_init_creates_all_sub_apis(self):
        """Test that all sub-APIs are created."""
        api = EeroAPI()

        # Core APIs
        assert hasattr(api, "auth")
        assert hasattr(api, "networks")
        assert hasattr(api, "devices")
        assert hasattr(api, "eeros")
        assert hasattr(api, "profiles")

        # Feature APIs
        assert hasattr(api, "activity")
        assert hasattr(api, "backup")
        assert hasattr(api, "dns")
        assert hasattr(api, "security")
        assert hasattr(api, "sqm")
        assert hasattr(api, "diagnostics")
        assert hasattr(api, "settings")
        assert hasattr(api, "updates")
        assert hasattr(api, "insights")
        assert hasattr(api, "routing")
        assert hasattr(api, "thread")
        assert hasattr(api, "support")
        assert hasattr(api, "blacklist")
        assert hasattr(api, "reservations")
        assert hasattr(api, "forwards")
        assert hasattr(api, "transfer")
        assert hasattr(api, "burst_reporters")
        assert hasattr(api, "ac_compat")
        assert hasattr(api, "ouicheck")
        assert hasattr(api, "password")


class TestEeroAPISubAPIs:
    """Tests for sub-API types."""

    def test_networks_api_type(self):
        """Test that networks is a NetworksAPI."""
        api = EeroAPI()
        assert isinstance(api.networks, NetworksAPI)

    def test_devices_api_type(self):
        """Test that devices is a DevicesAPI."""
        api = EeroAPI()
        assert isinstance(api.devices, DevicesAPI)

    def test_eeros_api_type(self):
        """Test that eeros is an EerosAPI."""
        api = EeroAPI()
        assert isinstance(api.eeros, EerosAPI)

    def test_profiles_api_type(self):
        """Test that profiles is a ProfilesAPI."""
        api = EeroAPI()
        assert isinstance(api.profiles, ProfilesAPI)

    def test_sub_apis_share_auth(self):
        """Test that all sub-APIs share the same AuthAPI instance."""
        api = EeroAPI()

        # All authenticated APIs should reference the same auth
        assert api.networks._auth_api is api.auth
        assert api.devices._auth_api is api.auth
        assert api.eeros._auth_api is api.auth
        assert api.profiles._auth_api is api.auth


class TestEeroAPIContextManager:
    """Tests for EeroAPI async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_enters_auth(self, mock_session, mock_keyring):
        """Test that entering context manager enters auth API."""
        api = EeroAPI(session=mock_session, use_keyring=True)

        # Mock the auth's __aenter__
        api.auth.__aenter__ = AsyncMock(return_value=api.auth)

        result = await api.__aenter__()

        assert result is api
        api.auth.__aenter__.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_manager_exits_auth(self, mock_session):
        """Test that exiting context manager exits auth API."""
        api = EeroAPI(session=mock_session, use_keyring=False)

        # Mock both enter and exit
        api.auth.__aenter__ = AsyncMock(return_value=api.auth)
        api.auth.__aexit__ = AsyncMock(return_value=None)

        async with api:
            pass

        api.auth.__aexit__.assert_awaited_once()


class TestEeroAPIAuthentication:
    """Tests for authentication delegation."""

    def test_is_authenticated_delegates_to_auth(self, mock_session):
        """Test that is_authenticated delegates to auth API."""
        api = EeroAPI(session=mock_session)

        # Initially not authenticated
        assert api.is_authenticated is False

    @pytest.mark.asyncio
    async def test_login_delegates_to_auth(self, mock_session):
        """Test that login delegates to auth API."""
        api = EeroAPI(session=mock_session, use_keyring=False)
        api.auth.login = AsyncMock(return_value=True)

        result = await api.login("test@example.com")

        assert result is True
        api.auth.login.assert_awaited_once_with("test@example.com")

    @pytest.mark.asyncio
    async def test_verify_delegates_to_auth(self, mock_session):
        """Test that verify delegates to auth API."""
        api = EeroAPI(session=mock_session, use_keyring=False)
        api.auth.verify = AsyncMock(return_value=True)

        result = await api.verify("123456")

        assert result is True
        api.auth.verify.assert_awaited_once_with("123456")

    @pytest.mark.asyncio
    async def test_logout_delegates_to_auth(self, mock_session):
        """Test that logout delegates to auth API."""
        api = EeroAPI(session=mock_session, use_keyring=False)
        api.auth.logout = AsyncMock(return_value=True)

        result = await api.logout()

        assert result is True
        api.auth.logout.assert_awaited_once()


class TestEeroAPIPreferredNetwork:
    """Tests for preferred network management (in-memory only)."""

    def test_set_preferred_network(self, mock_session):
        """Test setting preferred network ID."""
        api = EeroAPI(session=mock_session)

        api.set_preferred_network("network_123")

        assert api._preferred_network_id == "network_123"

    def test_get_preferred_network_id(self, mock_session):
        """Test getting preferred network ID."""
        api = EeroAPI(session=mock_session)
        api._preferred_network_id = "network_456"

        result = api.preferred_network_id

        assert result == "network_456"

    def test_preferred_network_id_none_by_default(self, mock_session):
        """Test that preferred network ID is None by default."""
        api = EeroAPI(session=mock_session)

        assert api.preferred_network_id is None
