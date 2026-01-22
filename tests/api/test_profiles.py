"""Tests for ProfilesAPI module.

Tests cover:
- Getting profile list (raw response)
- Getting profile details (raw response)
- Pausing/unpausing profiles
- Content filter management
- Custom block/allow lists
- Blocked applications management (Eero Plus)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.profiles import ProfilesAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestProfilesAPIInit:
    """Tests for ProfilesAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = ProfilesAPI(auth_api)

        assert api._auth_api is auth_api


class TestProfilesAPIGetProfiles:
    """Tests for get_profiles method."""

    @pytest.fixture
    def profiles_api(self, mock_session):
        """Create a ProfilesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ProfilesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_profiles_returns_raw_response(
        self, profiles_api, mock_session, sample_profile_data
    ):
        """Test get_profiles returns raw API response."""
        profiles_list = [sample_profile_data]
        expected_response = api_success_response(profiles_list)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profiles("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_profiles_not_authenticated(self, profiles_api):
        """Test get_profiles raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await profiles_api.get_profiles("network_123")


class TestProfilesAPIGetProfile:
    """Tests for get_profile method."""

    @pytest.fixture
    def profiles_api(self, mock_session):
        """Create a ProfilesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ProfilesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_profile_returns_raw_response(
        self, profiles_api, mock_session, sample_profile_data
    ):
        """Test get_profile returns raw API response."""
        expected_response = api_success_response(sample_profile_data)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profile("network_123", "profile_001")

        assert "meta" in result
        assert "data" in result
        assert result["data"]["name"] == "Kids"
        assert result["data"]["paused"] is False

    @pytest.mark.asyncio
    async def test_get_profile_not_authenticated(self, profiles_api):
        """Test get_profile raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.get_profile("network_123", "profile_001")


class TestProfilesAPIPauseProfile:
    """Tests for pause_profile method."""

    @pytest.fixture
    def profiles_api(self, mock_session):
        """Create a ProfilesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ProfilesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_pause_profile_returns_raw_response(self, profiles_api, mock_session):
        """Test successful profile pause returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await profiles_api.pause_profile("network_123", "profile_001", True)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"paused": True}

    @pytest.mark.asyncio
    async def test_pause_profile_not_authenticated(self, profiles_api):
        """Test pause_profile raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.pause_profile("network_123", "profile_001", True)


class TestProfilesAPIContentFilter:
    """Tests for content filter management."""

    @pytest.fixture
    def profiles_api(self, mock_session):
        """Create a ProfilesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ProfilesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_update_content_filter_returns_raw_response(self, profiles_api, mock_session):
        """Test updating content filter returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await profiles_api.update_profile_content_filter(
            "network_123",
            "profile_001",
            {"safe_search": True, "block_adult": True},
        )

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["content_filter"]["safe_search"] is True
        assert payload["content_filter"]["block_adult"] is True

    @pytest.mark.asyncio
    async def test_update_content_filter_not_authenticated(self, profiles_api):
        """Test update_profile_content_filter raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.update_profile_content_filter(
                "network_123", "profile_001", {"safe_search": True}
            )


class TestProfilesAPIBlockList:
    """Tests for custom block/allow list management."""

    @pytest.fixture
    def profiles_api(self, mock_session):
        """Create a ProfilesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ProfilesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_update_block_list_returns_raw_response(self, profiles_api, mock_session):
        """Test updating custom block list returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await profiles_api.update_profile_block_list(
            "network_123",
            "profile_001",
            ["example.com", "badsite.com"],
            block=True,
        )

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["custom_block_list"] == ["example.com", "badsite.com"]

    @pytest.mark.asyncio
    async def test_update_block_list_not_authenticated(self, profiles_api):
        """Test update_profile_block_list raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.update_profile_block_list(
                "network_123", "profile_001", ["example.com"]
            )


class TestProfilesAPIBlockedApplications:
    """Tests for blocked applications management (Eero Plus)."""

    @pytest.fixture
    def profiles_api(self, mock_session):
        """Create a ProfilesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ProfilesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_blocked_applications_returns_raw_response(self, profiles_api, mock_session):
        """Test getting blocked applications returns raw response."""
        profile_data = {
            "name": "Kids",
            "premium_dns": {
                "blocked_applications": ["youtube", "tiktok", "fortnite"],
            },
        }
        expected_response = api_success_response(profile_data)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_blocked_applications("network_123", "profile_001")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_blocked_applications_not_authenticated(self, profiles_api):
        """Test get_blocked_applications raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.get_blocked_applications("network_123", "profile_001")

    @pytest.mark.asyncio
    async def test_set_blocked_applications_returns_raw_response(self, profiles_api, mock_session):
        """Test setting blocked applications returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await profiles_api.set_blocked_applications(
            "network_123", "profile_001", ["youtube", "netflix"]
        )

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["blocked_applications"] == ["youtube", "netflix"]

    @pytest.mark.asyncio
    async def test_set_blocked_applications_not_authenticated(self, profiles_api):
        """Test set_blocked_applications raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.set_blocked_applications("network_123", "profile_001", ["youtube"])


class TestProfilesAPIDeviceManagement:
    """Tests for profile device management."""

    @pytest.fixture
    def profiles_api(self, mock_session):
        """Create a ProfilesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ProfilesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_profile_devices_returns_raw_response(self, profiles_api, mock_session):
        """Test getting devices assigned to a profile returns raw response."""
        profile_data = {
            "name": "Kids",
            "devices": [
                {"url": "/2.2/networks/net123/devices/dev001"},
                {"url": "/2.2/networks/net123/devices/dev002"},
            ],
        }
        expected_response = api_success_response(profile_data)
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profile_devices("network_123", "profile_001")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_profile_devices_not_authenticated(self, profiles_api):
        """Test get_profile_devices raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.get_profile_devices("network_123", "profile_001")

    @pytest.mark.asyncio
    async def test_set_profile_devices_returns_raw_response(self, profiles_api, mock_session):
        """Test setting devices for a profile returns raw response."""
        expected_response = {"meta": {"code": 200}, "data": {}}
        mock_response = create_mock_response(200, expected_response)
        mock_session.request.return_value = mock_response

        device_urls = [
            "/2.2/networks/net123/devices/dev001",
            "/2.2/networks/net123/devices/dev002",
        ]
        result = await profiles_api.set_profile_devices("network_123", "profile_001", device_urls)

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["devices"] == [
            {"url": "/2.2/networks/net123/devices/dev001"},
            {"url": "/2.2/networks/net123/devices/dev002"},
        ]

    @pytest.mark.asyncio
    async def test_set_profile_devices_not_authenticated(self, profiles_api):
        """Test set_profile_devices raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.set_profile_devices(
                "network_123", "profile_001", ["/2.2/networks/net123/devices/dev001"]
            )
