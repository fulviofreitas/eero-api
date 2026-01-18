"""Tests for ScheduleAPI module.

Tests cover:
- Getting profile schedules
- Setting profile schedules
- Clearing schedules
- Bedtime configuration
- Weekday/weekend bedtime
- Adding time-off periods
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.schedule import ScheduleAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response

# ========================== ScheduleAPI Init Tests ==========================


class TestScheduleAPIInit:
    """Tests for ScheduleAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = ScheduleAPI(auth_api)

        assert api._auth_api is auth_api


# ========================== Get Profile Schedule Tests ==========================


class TestScheduleAPIGetSchedule:
    """Tests for get_profile_schedule method."""

    @pytest.fixture
    def schedule_api(self, mock_session):
        """Create a ScheduleAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ScheduleAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_schedule_with_list(self, schedule_api, mock_session):
        """Test getting schedule with list format."""
        profile_data = {
            "schedule": [
                {"days": ["monday", "tuesday"], "start": "21:00", "end": "07:00"},
            ],
            "paused": False,
        }
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await schedule_api.get_profile_schedule("network_123", "profile_001")

        assert result["enabled"] is True
        assert len(result["time_blocks"]) == 1
        assert result["paused"] is False

    @pytest.mark.asyncio
    async def test_get_schedule_with_dict(self, schedule_api, mock_session):
        """Test getting schedule with dict format."""
        profile_data = {
            "schedule": {
                "enabled": True,
                "type": "bedtime",
                "blocks": [{"start": "21:00", "end": "07:00"}],
            },
        }
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await schedule_api.get_profile_schedule("network_123", "profile_001")

        assert result["enabled"] is True
        assert result["schedule_type"] == "bedtime"
        assert len(result["time_blocks"]) == 1

    @pytest.mark.asyncio
    async def test_get_schedule_empty(self, schedule_api, mock_session):
        """Test getting empty schedule."""
        profile_data = {"schedule": []}
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await schedule_api.get_profile_schedule("network_123", "profile_001")

        assert result["enabled"] is False
        assert result["time_blocks"] == []

    @pytest.mark.asyncio
    async def test_get_schedule_with_bedtime_active(self, schedule_api, mock_session):
        """Test getting schedule with bedtime active in state."""
        profile_data = {
            "schedule": [],
            "state": {"schedule": "bedtime active"},
        }
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await schedule_api.get_profile_schedule("network_123", "profile_001")

        assert result["bedtime_active"] is True

    @pytest.mark.asyncio
    async def test_get_schedule_not_authenticated(self, schedule_api):
        """Test get_profile_schedule raises when not authenticated."""
        schedule_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await schedule_api.get_profile_schedule("network_123", "profile_001")


# ========================== Set Profile Schedule Tests ==========================


class TestScheduleAPISetSchedule:
    """Tests for set_profile_schedule method."""

    @pytest.fixture
    def schedule_api(self, mock_session):
        """Create a ScheduleAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ScheduleAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_schedule_single_block(self, schedule_api, mock_session):
        """Test setting a single time block."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        time_blocks = [{"days": ["monday", "tuesday"], "start": "21:00", "end": "07:00"}]
        result = await schedule_api.set_profile_schedule("network_123", "profile_001", time_blocks)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"schedule": time_blocks}

    @pytest.mark.asyncio
    async def test_set_schedule_multiple_blocks(self, schedule_api, mock_session):
        """Test setting multiple time blocks."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        time_blocks = [
            {
                "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "start": "21:00",
                "end": "07:00",
            },
            {"days": ["saturday", "sunday"], "start": "22:00", "end": "09:00"},
        ]
        result = await schedule_api.set_profile_schedule("network_123", "profile_001", time_blocks)

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"schedule": time_blocks}

    @pytest.mark.asyncio
    async def test_set_schedule_not_authenticated(self, schedule_api):
        """Test set_profile_schedule raises when not authenticated."""
        schedule_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await schedule_api.set_profile_schedule("network_123", "profile_001", [])


# ========================== Clear Profile Schedule Tests ==========================


class TestScheduleAPIClearSchedule:
    """Tests for clear_profile_schedule method."""

    @pytest.fixture
    def schedule_api(self, mock_session):
        """Create a ScheduleAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ScheduleAPI(auth_api)

    @pytest.mark.asyncio
    async def test_clear_schedule(self, schedule_api, mock_session):
        """Test clearing a schedule."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await schedule_api.clear_profile_schedule("network_123", "profile_001")

        assert result is True
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"schedule": []}


# ========================== Enable Bedtime Tests ==========================


class TestScheduleAPIEnableBedtime:
    """Tests for enable_bedtime method."""

    @pytest.fixture
    def schedule_api(self, mock_session):
        """Create a ScheduleAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ScheduleAPI(auth_api)

    @pytest.mark.asyncio
    async def test_enable_bedtime_all_days(self, schedule_api, mock_session):
        """Test enabling bedtime for all days."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await schedule_api.enable_bedtime("network_123", "profile_001", "21:00", "07:00")

        assert result is True
        call_args = mock_session.request.call_args
        schedule = call_args.kwargs["json"]["schedule"]
        assert len(schedule) == 1
        assert schedule[0]["days"] == [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        assert schedule[0]["start"] == "21:00"
        assert schedule[0]["end"] == "07:00"
        assert schedule[0]["type"] == "bedtime"

    @pytest.mark.asyncio
    async def test_enable_bedtime_specific_days(self, schedule_api, mock_session):
        """Test enabling bedtime for specific days."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await schedule_api.enable_bedtime(
            "network_123",
            "profile_001",
            "21:00",
            "07:00",
            days=["monday", "tuesday", "wednesday"],
        )

        assert result is True
        call_args = mock_session.request.call_args
        schedule = call_args.kwargs["json"]["schedule"]
        assert schedule[0]["days"] == ["monday", "tuesday", "wednesday"]


# ========================== Weekday/Weekend Bedtime Tests ==========================


class TestScheduleAPIWeekdayWeekendBedtime:
    """Tests for weekday and weekend bedtime methods."""

    @pytest.fixture
    def schedule_api(self, mock_session):
        """Create a ScheduleAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ScheduleAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_weekday_bedtime(self, schedule_api, mock_session):
        """Test setting weekday bedtime."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await schedule_api.set_weekday_bedtime(
            "network_123", "profile_001", "21:00", "07:00"
        )

        assert result is True
        call_args = mock_session.request.call_args
        schedule = call_args.kwargs["json"]["schedule"]
        assert schedule[0]["days"] == ["monday", "tuesday", "wednesday", "thursday", "friday"]

    @pytest.mark.asyncio
    async def test_set_weekend_bedtime(self, schedule_api, mock_session):
        """Test setting weekend bedtime."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.return_value = mock_response

        result = await schedule_api.set_weekend_bedtime(
            "network_123", "profile_001", "22:00", "09:00"
        )

        assert result is True
        call_args = mock_session.request.call_args
        schedule = call_args.kwargs["json"]["schedule"]
        assert schedule[0]["days"] == ["saturday", "sunday"]
        assert schedule[0]["start"] == "22:00"
        assert schedule[0]["end"] == "09:00"


# ========================== Add Time Off Tests ==========================


class TestScheduleAPIAddTimeOff:
    """Tests for add_time_off method."""

    @pytest.fixture
    def schedule_api(self, mock_session):
        """Create a ScheduleAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ScheduleAPI(auth_api)

    @pytest.mark.asyncio
    async def test_add_time_off_to_empty_schedule(self, schedule_api, mock_session):
        """Test adding time off to empty schedule."""
        # First call gets current schedule (empty)
        get_response = create_mock_response(200, api_success_response({"schedule": []}))
        # Second call sets schedule
        set_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.side_effect = [get_response, set_response]

        result = await schedule_api.add_time_off(
            "network_123",
            "profile_001",
            "14:00",
            "16:00",
            days=["monday", "wednesday", "friday"],
        )

        assert result is True
        set_call = mock_session.request.call_args_list[1]
        schedule = set_call.kwargs["json"]["schedule"]
        assert len(schedule) == 1
        assert schedule[0]["days"] == ["monday", "wednesday", "friday"]
        assert schedule[0]["start"] == "14:00"
        assert schedule[0]["end"] == "16:00"

    @pytest.mark.asyncio
    async def test_add_time_off_to_existing_schedule(self, schedule_api, mock_session):
        """Test adding time off to existing schedule."""
        # First call gets current schedule (with existing block)
        existing_schedule = [{"days": ["monday", "tuesday"], "start": "21:00", "end": "07:00"}]
        get_response = create_mock_response(
            200, api_success_response({"schedule": existing_schedule})
        )
        # Second call sets schedule
        set_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.side_effect = [get_response, set_response]

        result = await schedule_api.add_time_off(
            "network_123",
            "profile_001",
            "14:00",
            "16:00",
            days=["wednesday"],
        )

        assert result is True
        set_call = mock_session.request.call_args_list[1]
        schedule = set_call.kwargs["json"]["schedule"]
        assert len(schedule) == 2  # Original + new block

    @pytest.mark.asyncio
    async def test_add_time_off_with_name(self, schedule_api, mock_session):
        """Test adding time off with a name."""
        get_response = create_mock_response(200, api_success_response({"schedule": []}))
        set_response = create_mock_response(200, {"meta": {"code": 200}})
        mock_session.request.side_effect = [get_response, set_response]

        result = await schedule_api.add_time_off(
            "network_123",
            "profile_001",
            "15:00",
            "17:00",
            days=["saturday", "sunday"],
            name="Homework Time",
        )

        assert result is True
        set_call = mock_session.request.call_args_list[1]
        schedule = set_call.kwargs["json"]["schedule"]
        assert schedule[0]["name"] == "Homework Time"
