"""Tests for ProfilesAPI module.

Tests cover:
- Getting profile list
- Getting profile details
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

# ========================== ProfilesAPI Init Tests ==========================


class TestProfilesAPIInit:
    """Tests for ProfilesAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = ProfilesAPI(auth_api)

        assert api._auth_api is auth_api


# ========================== GetProfiles Tests ==========================


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
    async def test_get_profiles_success(self, profiles_api, mock_session, sample_profile_data):
        """Test successful profiles retrieval."""
        profiles_list = [sample_profile_data]
        mock_response = create_mock_response(200, api_success_response(profiles_list))
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profiles("network_123")

        assert len(result) == 1
        assert result[0]["name"] == "Kids"

    @pytest.mark.asyncio
    async def test_get_profiles_nested_data_format(
        self, profiles_api, mock_session, sample_profile_data
    ):
        """Test profiles retrieval with nested data format."""
        mock_response = create_mock_response(
            200, api_success_response({"data": [sample_profile_data]})
        )
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profiles("network_123")

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_profiles_empty_list(self, profiles_api, mock_session):
        """Test profiles retrieval with empty list."""
        mock_response = create_mock_response(200, api_success_response([]))
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profiles("network_123")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_profiles_not_authenticated(self, profiles_api):
        """Test get_profiles raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await profiles_api.get_profiles("network_123")


# ========================== GetProfile Tests ==========================


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
    async def test_get_profile_success(self, profiles_api, mock_session, sample_profile_data):
        """Test successful profile retrieval."""
        mock_response = create_mock_response(200, api_success_response(sample_profile_data))
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profile("network_123", "profile_001")

        assert result["name"] == "Kids"
        assert result["paused"] is False

    @pytest.mark.asyncio
    async def test_get_profile_not_authenticated(self, profiles_api):
        """Test get_profile raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.get_profile("network_123", "profile_001")


# ========================== PauseProfile Tests ==========================


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
    async def test_pause_profile_success(self, profiles_api, mock_session):
        """Test successful profile pause."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await profiles_api.pause_profile("network_123", "profile_001", True)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"paused": True}

    @pytest.mark.asyncio
    async def test_unpause_profile_success(self, profiles_api, mock_session):
        """Test successful profile unpause."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await profiles_api.pause_profile("network_123", "profile_001", False)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"paused": False}

    @pytest.mark.asyncio
    async def test_pause_profile_not_authenticated(self, profiles_api):
        """Test pause_profile raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.pause_profile("network_123", "profile_001", True)


# ========================== Content Filter Tests ==========================


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
    async def test_update_content_filter_success(self, profiles_api, mock_session):
        """Test updating content filter settings."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await profiles_api.update_profile_content_filter(
            "network_123",
            "profile_001",
            {"safe_search": True, "block_adult": True},
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["content_filter"]["safe_search"] is True
        assert payload["content_filter"]["block_adult"] is True

    @pytest.mark.asyncio
    async def test_update_content_filter_ignores_invalid(self, profiles_api, mock_session):
        """Test that invalid filter keys are ignored."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await profiles_api.update_profile_content_filter(
            "network_123",
            "profile_001",
            {"safe_search": True, "invalid_key": True},
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert "invalid_key" not in payload["content_filter"]
        assert payload["content_filter"]["safe_search"] is True

    @pytest.mark.asyncio
    async def test_update_content_filter_not_authenticated(self, profiles_api):
        """Test update_profile_content_filter raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.update_profile_content_filter(
                "network_123", "profile_001", {"safe_search": True}
            )


# ========================== Block List Tests ==========================


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
    async def test_update_block_list(self, profiles_api, mock_session):
        """Test updating custom block list."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await profiles_api.update_profile_block_list(
            "network_123",
            "profile_001",
            ["example.com", "badsite.com"],
            block=True,
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["custom_block_list"] == ["example.com", "badsite.com"]

    @pytest.mark.asyncio
    async def test_update_allow_list(self, profiles_api, mock_session):
        """Test updating custom allow list."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await profiles_api.update_profile_block_list(
            "network_123",
            "profile_001",
            ["allowed.com"],
            block=False,
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["custom_allow_list"] == ["allowed.com"]

    @pytest.mark.asyncio
    async def test_update_block_list_not_authenticated(self, profiles_api):
        """Test update_profile_block_list raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.update_profile_block_list(
                "network_123", "profile_001", ["example.com"]
            )


# ========================== Blocked Applications Tests ==========================


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
    async def test_get_blocked_applications(self, profiles_api, mock_session):
        """Test getting blocked applications."""
        profile_data = {
            "name": "Kids",
            "premium_dns": {
                "blocked_applications": ["youtube", "tiktok", "fortnite"],
            },
        }
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_blocked_applications("network_123", "profile_001")

        assert result == ["youtube", "tiktok", "fortnite"]

    @pytest.mark.asyncio
    async def test_get_blocked_applications_direct_field(self, profiles_api, mock_session):
        """Test getting blocked applications from direct field."""
        profile_data = {
            "name": "Kids",
            "blocked_applications": ["instagram", "snapchat"],
        }
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_blocked_applications("network_123", "profile_001")

        assert result == ["instagram", "snapchat"]

    @pytest.mark.asyncio
    async def test_get_blocked_applications_empty(self, profiles_api, mock_session):
        """Test getting blocked applications when none are blocked."""
        profile_data = {"name": "Kids"}
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_blocked_applications("network_123", "profile_001")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_blocked_applications_not_authenticated(self, profiles_api):
        """Test get_blocked_applications raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.get_blocked_applications("network_123", "profile_001")

    @pytest.mark.asyncio
    async def test_set_blocked_applications(self, profiles_api, mock_session):
        """Test setting blocked applications."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await profiles_api.set_blocked_applications(
            "network_123", "profile_001", ["youtube", "netflix"]
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["blocked_applications"] == ["youtube", "netflix"]

    @pytest.mark.asyncio
    async def test_set_blocked_applications_empty(self, profiles_api, mock_session):
        """Test clearing all blocked applications."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await profiles_api.set_blocked_applications("network_123", "profile_001", [])

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["blocked_applications"] == []

    @pytest.mark.asyncio
    async def test_set_blocked_applications_not_authenticated(self, profiles_api):
        """Test set_blocked_applications raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.set_blocked_applications("network_123", "profile_001", ["youtube"])


# ========================== Add/Remove Blocked Application Tests ==========================


class TestProfilesAPIBlockedAppModification:
    """Tests for adding/removing individual blocked applications."""

    @pytest.fixture
    def profiles_api(self, mock_session):
        """Create a ProfilesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ProfilesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_add_blocked_application(self, profiles_api, mock_session):
        """Test adding a blocked application."""
        # First call returns current blocked apps
        get_response = create_mock_response(
            200, api_success_response({"blocked_applications": ["youtube"]})
        )
        # Second call sets new list
        set_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.side_effect = [get_response, set_response]

        result = await profiles_api.add_blocked_application("network_123", "profile_001", "tiktok")

        assert result is True
        # Verify the set call includes both apps
        set_call = mock_session.request.call_args_list[1]
        payload = set_call.kwargs["json"]
        assert "youtube" in payload["blocked_applications"]
        assert "tiktok" in payload["blocked_applications"]

    @pytest.mark.asyncio
    async def test_add_blocked_application_already_blocked(self, profiles_api, mock_session):
        """Test adding an already blocked application returns True without API call."""
        get_response = create_mock_response(
            200, api_success_response({"blocked_applications": ["youtube", "tiktok"]})
        )
        mock_session.request.return_value = get_response

        result = await profiles_api.add_blocked_application("network_123", "profile_001", "youtube")

        assert result is True
        # Only one call should have been made (get, not set)
        assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_remove_blocked_application(self, profiles_api, mock_session):
        """Test removing a blocked application."""
        # First call returns current blocked apps
        get_response = create_mock_response(
            200, api_success_response({"blocked_applications": ["youtube", "tiktok"]})
        )
        # Second call sets new list
        set_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.side_effect = [get_response, set_response]

        result = await profiles_api.remove_blocked_application(
            "network_123", "profile_001", "youtube"
        )

        assert result is True
        # Verify the set call only includes tiktok
        set_call = mock_session.request.call_args_list[1]
        payload = set_call.kwargs["json"]
        assert payload["blocked_applications"] == ["tiktok"]

    @pytest.mark.asyncio
    async def test_remove_blocked_application_not_blocked(self, profiles_api, mock_session):
        """Test removing an app that isn't blocked returns True without API call."""
        get_response = create_mock_response(
            200, api_success_response({"blocked_applications": ["youtube"]})
        )
        mock_session.request.return_value = get_response

        result = await profiles_api.remove_blocked_application(
            "network_123", "profile_001", "tiktok"
        )

        assert result is True
        # Only one call should have been made (get, not set)
        assert mock_session.request.call_count == 1


# ========================== Profile Device Management Tests ==========================


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
    async def test_get_profile_devices(self, profiles_api, mock_session):
        """Test getting devices assigned to a profile."""
        profile_data = {
            "name": "Kids",
            "devices": [
                {"url": "/2.2/networks/net123/devices/dev001"},
                {"url": "/2.2/networks/net123/devices/dev002"},
            ],
        }
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profile_devices("network_123", "profile_001")

        assert len(result) == 2
        assert result[0]["url"] == "/2.2/networks/net123/devices/dev001"
        assert result[1]["url"] == "/2.2/networks/net123/devices/dev002"

    @pytest.mark.asyncio
    async def test_get_profile_devices_empty(self, profiles_api, mock_session):
        """Test getting devices when profile has no devices assigned."""
        profile_data = {"name": "Kids", "devices": []}
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profile_devices("network_123", "profile_001")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_profile_devices_no_devices_field(self, profiles_api, mock_session):
        """Test getting devices when profile has no devices field."""
        profile_data = {"name": "Kids"}
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await profiles_api.get_profile_devices("network_123", "profile_001")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_profile_devices_not_authenticated(self, profiles_api):
        """Test get_profile_devices raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.get_profile_devices("network_123", "profile_001")

    @pytest.mark.asyncio
    async def test_set_profile_devices(self, profiles_api, mock_session):
        """Test setting devices for a profile."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        device_urls = [
            "/2.2/networks/net123/devices/dev001",
            "/2.2/networks/net123/devices/dev002",
        ]
        result = await profiles_api.set_profile_devices(
            "network_123", "profile_001", device_urls
        )

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["devices"] == [
            {"url": "/2.2/networks/net123/devices/dev001"},
            {"url": "/2.2/networks/net123/devices/dev002"},
        ]

    @pytest.mark.asyncio
    async def test_set_profile_devices_empty(self, profiles_api, mock_session):
        """Test clearing all devices from a profile."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await profiles_api.set_profile_devices("network_123", "profile_001", [])

        assert result is True
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["devices"] == []

    @pytest.mark.asyncio
    async def test_set_profile_devices_not_authenticated(self, profiles_api):
        """Test set_profile_devices raises when not authenticated."""
        profiles_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await profiles_api.set_profile_devices(
                "network_123", "profile_001", ["/2.2/networks/net123/devices/dev001"]
            )

    @pytest.mark.asyncio
    async def test_add_device_to_profile(self, profiles_api, mock_session):
        """Test adding a device to a profile."""
        # First call returns current devices
        get_response = create_mock_response(
            200,
            api_success_response(
                {"devices": [{"url": "/2.2/networks/network_123/devices/dev001"}]}
            ),
        )
        # Second call sets new list
        set_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.side_effect = [get_response, set_response]

        result = await profiles_api.add_device_to_profile(
            "network_123", "profile_001", "dev002"
        )

        assert result is True
        # Verify the set call includes both devices
        set_call = mock_session.request.call_args_list[1]
        payload = set_call.kwargs["json"]
        assert len(payload["devices"]) == 2
        device_urls = [d["url"] for d in payload["devices"]]
        assert "/2.2/networks/network_123/devices/dev001" in device_urls
        assert "/2.2/networks/network_123/devices/dev002" in device_urls

    @pytest.mark.asyncio
    async def test_add_device_to_profile_already_in_profile(self, profiles_api, mock_session):
        """Test adding a device that's already in the profile."""
        get_response = create_mock_response(
            200,
            api_success_response(
                {"devices": [{"url": "/2.2/networks/network_123/devices/dev001"}]}
            ),
        )
        mock_session.request.return_value = get_response

        result = await profiles_api.add_device_to_profile(
            "network_123", "profile_001", "dev001"
        )

        assert result is True
        # Only one call should have been made (get, not set)
        assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_remove_device_from_profile(self, profiles_api, mock_session):
        """Test removing a device from a profile."""
        # First call returns current devices
        get_response = create_mock_response(
            200,
            api_success_response(
                {
                    "devices": [
                        {"url": "/2.2/networks/network_123/devices/dev001"},
                        {"url": "/2.2/networks/network_123/devices/dev002"},
                    ]
                }
            ),
        )
        # Second call sets new list
        set_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.side_effect = [get_response, set_response]

        result = await profiles_api.remove_device_from_profile(
            "network_123", "profile_001", "dev001"
        )

        assert result is True
        # Verify the set call only includes dev002
        set_call = mock_session.request.call_args_list[1]
        payload = set_call.kwargs["json"]
        assert len(payload["devices"]) == 1
        assert payload["devices"][0]["url"] == "/2.2/networks/network_123/devices/dev002"

    @pytest.mark.asyncio
    async def test_remove_device_from_profile_not_in_profile(self, profiles_api, mock_session):
        """Test removing a device that's not in the profile."""
        get_response = create_mock_response(
            200,
            api_success_response(
                {"devices": [{"url": "/2.2/networks/network_123/devices/dev001"}]}
            ),
        )
        mock_session.request.return_value = get_response

        result = await profiles_api.remove_device_from_profile(
            "network_123", "profile_001", "dev999"
        )

        assert result is True
        # Only one call should have been made (get, not set)
        assert mock_session.request.call_count == 1
