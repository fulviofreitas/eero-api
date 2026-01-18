"""Tests for Profile model.

Tests cover:
- Profile model with required fields
- Profile model with optional fields
- Device association and counting
- Schedule handling
- Content filtering
- Custom block/allow lists
- ID extraction from URL
"""

from eero.models.profile import ContentFilter, Profile, ProfileScheduleBlock, ProfileState

# ========================== ProfileScheduleBlock Tests ==========================


class TestProfileScheduleBlock:
    """Tests for ProfileScheduleBlock model."""

    def test_schedule_block_weekdays(self):
        """Test schedule block for weekdays."""
        block = ProfileScheduleBlock(
            days=["monday", "tuesday", "wednesday", "thursday", "friday"],
            start_time="21:00",
            end_time="07:00",
        )

        assert len(block.days) == 5
        assert "monday" in block.days
        assert block.start_time == "21:00"
        assert block.end_time == "07:00"

    def test_schedule_block_weekend(self):
        """Test schedule block for weekend."""
        block = ProfileScheduleBlock(
            days=["saturday", "sunday"],
            start_time="22:00",
            end_time="09:00",
        )

        assert len(block.days) == 2
        assert "saturday" in block.days
        assert "sunday" in block.days


# ========================== ContentFilter Tests ==========================


class TestContentFilter:
    """Tests for ContentFilter model."""

    def test_content_filter_defaults(self):
        """Test ContentFilter with default values."""
        filter = ContentFilter()

        assert filter.adblock is False
        assert filter.adblock_plus is False
        assert filter.safe_search is False
        assert filter.block_malware is False
        assert filter.block_illegal is False
        assert filter.block_violent is False
        assert filter.block_adult is False
        assert filter.youtube_restricted is False

    def test_content_filter_all_enabled(self):
        """Test ContentFilter with all features enabled."""
        filter = ContentFilter(
            adblock=True,
            adblock_plus=True,
            safe_search=True,
            block_malware=True,
            block_illegal=True,
            block_violent=True,
            block_adult=True,
            youtube_restricted=True,
        )

        assert filter.adblock is True
        assert filter.safe_search is True
        assert filter.block_adult is True
        assert filter.youtube_restricted is True

    def test_content_filter_kid_safe(self):
        """Test ContentFilter for kid-safe configuration."""
        filter = ContentFilter(
            safe_search=True,
            block_adult=True,
            block_violent=True,
            youtube_restricted=True,
        )

        assert filter.safe_search is True
        assert filter.block_adult is True
        assert filter.block_violent is True
        assert filter.youtube_restricted is True
        assert filter.adblock is False  # Not related to kid safety


# ========================== ProfileState Tests ==========================


class TestProfileState:
    """Tests for ProfileState model."""

    def test_profile_state_active(self):
        """Test active profile state."""
        state = ProfileState(value="active")

        assert state.value == "active"
        assert state.schedule is None

    def test_profile_state_paused(self):
        """Test paused profile state."""
        state = ProfileState(value="paused")

        assert state.value == "paused"

    def test_profile_state_scheduled(self):
        """Test scheduled profile state."""
        state = ProfileState(value="scheduled", schedule="Bedtime 9PM-7AM")

        assert state.value == "scheduled"
        assert state.schedule == "Bedtime 9PM-7AM"


# ========================== Profile Basic Tests ==========================


class TestProfileBasic:
    """Tests for basic Profile model functionality."""

    def test_profile_required_fields(self):
        """Test Profile with only required fields."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
        )

        assert profile.url == "/2.2/networks/network_123/profiles/profile_001"
        assert profile.name == "Kids"
        assert profile.paused is False
        assert profile.default is False

    def test_profile_all_core_fields(self):
        """Test Profile with all core fields."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            paused=True,
            default=False,
            state=ProfileState(value="paused"),
            devices=[
                {"url": "/2.2/networks/network_123/devices/device_001"},
                {"url": "/2.2/networks/network_123/devices/device_002"},
            ],
        )

        assert profile.name == "Kids"
        assert profile.paused is True
        assert len(profile.devices) == 2


# ========================== Profile ID Extraction Tests ==========================


class TestProfileIDExtraction:
    """Tests for Profile ID extraction from URL."""

    def test_extract_profile_id_from_url(self):
        """Test profile ID extraction from URL."""
        profile = Profile(
            url="/2.2/networks/3401709/profiles/123456",
            name="Test",
            state=ProfileState(value="active"),
        )

        assert profile.id == "123456"

    def test_extract_network_id_from_url(self):
        """Test network ID extraction from URL."""
        profile = Profile(
            url="/2.2/networks/3401709/profiles/123456",
            name="Test",
            state=ProfileState(value="active"),
        )

        assert profile.network_id == "3401709"


# ========================== Profile Device Count Tests ==========================


class TestProfileDeviceCount:
    """Tests for Profile device counting."""

    def test_device_count_explicitly_provided(self):
        """Test that device_count is used when explicitly provided."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            devices=[
                {"url": "/2.2/networks/network_123/devices/device_001"},
                {"url": "/2.2/networks/network_123/devices/device_002"},
                {"url": "/2.2/networks/network_123/devices/device_003"},
            ],
            device_count=3,
        )

        assert profile.device_count == 3

    def test_device_count_empty_explicit(self):
        """Test device_count when explicitly set to 0."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Empty",
            state=ProfileState(value="active"),
            devices=[],
            device_count=0,
        )

        assert profile.device_count == 0

    def test_connected_device_count_explicit(self):
        """Test connected device count when explicitly provided."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            devices=[
                {"url": "/devices/d1", "connected": True},
                {"url": "/devices/d2", "connected": True},
                {"url": "/devices/d3", "connected": False},
            ],
            connected_device_count=2,
        )

        assert profile.connected_device_count == 2

    def test_wired_wireless_device_counts_explicit(self):
        """Test wired and wireless device count when explicitly provided."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            devices=[
                {"url": "/devices/d1", "connected": True, "wireless": True},
                {"url": "/devices/d2", "connected": True, "wireless": False},
                {"url": "/devices/d3", "connected": True, "wireless": True},
                {"url": "/devices/d4", "connected": False, "wireless": True},
            ],
            wired_device_count=1,
            wireless_device_count=2,
        )

        assert profile.wired_device_count == 1
        assert profile.wireless_device_count == 2


# ========================== Profile Device IDs Tests ==========================


class TestProfileDeviceIDs:
    """Tests for Profile device ID extraction."""

    def test_device_ids_explicitly_provided(self):
        """Test that device IDs are used when explicitly provided."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            devices=[
                {"url": "/2.2/networks/3401709/devices/abc123"},
                {"url": "/2.2/networks/3401709/devices/def456"},
            ],
            device_ids=["abc123", "def456"],
        )

        assert profile.device_ids is not None
        assert len(profile.device_ids) == 2
        assert "abc123" in profile.device_ids
        assert "def456" in profile.device_ids


# ========================== Profile Schedule Tests ==========================


class TestProfileSchedule:
    """Tests for Profile schedule handling."""

    def test_schedule_enabled_explicit(self):
        """Test that schedule_enabled is used when explicitly provided."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            schedule=[{"type": "bedtime", "start": "21:00", "end": "07:00"}],
            schedule_enabled=True,
        )

        assert profile.schedule_enabled is True

    def test_schedule_disabled_explicit(self):
        """Test that schedule_enabled is False when explicitly set."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            schedule=[],
            schedule_enabled=False,
        )

        assert profile.schedule_enabled is False


# ========================== Profile Content Filter Tests ==========================


class TestProfileContentFilterIntegration:
    """Tests for Profile content filter integration."""

    def test_content_filter_explicitly_provided(self):
        """Test content filter when explicitly provided."""
        content_filter = ContentFilter(
            safe_search=True,
            youtube_restricted=True,
            block_adult=True,
            block_violent=True,
            block_illegal=False,
        )
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            content_filter=content_filter,
        )

        assert profile.content_filter is not None
        assert profile.content_filter.safe_search is True
        assert profile.content_filter.youtube_restricted is True
        assert profile.content_filter.block_adult is True
        assert profile.content_filter.block_violent is True
        assert profile.content_filter.block_illegal is False


# ========================== Profile Block/Allow Lists Tests ==========================


class TestProfileBlockAllowLists:
    """Tests for Profile custom block/allow lists."""

    def test_custom_block_list_provided(self):
        """Test custom block list when explicitly provided."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            custom_block_list=["badsite.com", "dangerous.net"],
        )

        assert len(profile.custom_block_list) == 2
        assert "badsite.com" in profile.custom_block_list
        assert "dangerous.net" in profile.custom_block_list

    def test_custom_allow_list_provided(self):
        """Test custom allow list when explicitly provided."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            custom_allow_list=["educational.com", "homework.org"],
        )

        assert len(profile.custom_allow_list) == 2
        assert "educational.com" in profile.custom_allow_list

    def test_empty_block_allow_lists(self):
        """Test empty block/allow lists."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
        )

        assert profile.custom_block_list == []
        assert profile.custom_allow_list == []


# ========================== Profile Premium Tests ==========================


class TestProfilePremium:
    """Tests for Profile premium feature detection."""

    def test_premium_enabled_explicit_true(self):
        """Test premium_enabled when explicitly set to True."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            premium_enabled=True,
        )

        assert profile.premium_enabled is True

    def test_premium_enabled_explicit_false(self):
        """Test premium_enabled when explicitly set to False."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            premium_enabled=False,
        )

        assert profile.premium_enabled is False

    def test_premium_dns_data_preserved(self):
        """Test that premium_dns data is preserved."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            state=ProfileState(value="active"),
            premium_dns={
                "ad_block_settings": {"enabled": True},
            },
        )

        assert profile.premium_dns is not None
        assert profile.premium_dns["ad_block_settings"]["enabled"] is True


# ========================== Profile API Response Tests ==========================


class TestProfileAPIResponse:
    """Tests for parsing Profile from API response."""

    def test_parse_from_api_response(self):
        """Test parsing Profile from typical API response."""
        api_response = {
            "url": "/2.2/networks/network_123/profiles/profile_001",
            "name": "Kids",
            "paused": False,
            "default": False,
            "state": {"value": "active"},
            "devices": [
                {"url": "/2.2/networks/network_123/devices/device_001", "connected": True},
            ],
            "schedule": [],
            "proxied_nodes": [],
        }

        profile = Profile.model_validate(api_response)

        assert profile.name == "Kids"
        assert profile.paused is False
        assert len(profile.devices) == 1

    def test_parse_full_api_response(self):
        """Test parsing Profile from full API response with all fields."""
        api_response = {
            "url": "/2.2/networks/3401709/profiles/123456",
            "name": "Kids",
            "paused": False,
            "default": False,
            "state": {"value": "active"},
            "devices": [
                {
                    "url": "/2.2/networks/3401709/devices/abc123",
                    "connected": True,
                    "wireless": True,
                },
                {
                    "url": "/2.2/networks/3401709/devices/def456",
                    "connected": True,
                    "wireless": False,
                },
            ],
            "schedule": [{"type": "bedtime"}],
            "proxied_nodes": [],
            "premium_dns": {
                "ad_block_settings": {"enabled": True},
                "dns_policies": {"safe_search_enabled": True},
                "advanced_content_filters": {
                    "blocked_list": ["badsite.com"],
                    "allowed_list": ["homework.edu"],
                },
            },
            "unified_content_filters": {
                "dns_policies": {
                    "safe_search_enabled": True,
                    "youtube_restricted": True,
                    "block_pornographic_content": True,
                },
            },
        }

        profile = Profile.model_validate(api_response)

        assert profile.id == "123456"
        assert profile.network_id == "3401709"
        assert len(profile.devices) == 2
        assert len(profile.schedule) == 1
        assert profile.premium_dns is not None
        assert profile.unified_content_filters is not None


# ========================== Profile Default Tests ==========================


class TestProfileDefault:
    """Tests for default profile."""

    def test_default_profile(self):
        """Test default profile flag."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_default",
            name="Default",
            default=True,
            state=ProfileState(value="active"),
        )

        assert profile.default is True

    def test_non_default_profile(self):
        """Test non-default profile flag."""
        profile = Profile(
            url="/2.2/networks/network_123/profiles/profile_001",
            name="Kids",
            default=False,
            state=ProfileState(value="active"),
        )

        assert profile.default is False
