"""Tests for ScheduleAPI module.

Tests cover profile schedule and bedtime settings.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.schedule import ScheduleAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestScheduleAPIInit:
    """Tests for ScheduleAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = ScheduleAPI(auth_api)
        assert api._auth_api is auth_api


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
    async def test_get_profile_schedule_returns_raw_response(self, schedule_api, mock_session):
        """Test getting profile schedule returns raw response."""
        profile_data = {"schedule": [{"days": ["monday"], "start": "21:00", "end": "07:00"}]}
        mock_response = create_mock_response(200, api_success_response(profile_data))
        mock_session.request.return_value = mock_response

        result = await schedule_api.get_profile_schedule("network_123", "profile_001")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_profile_schedule_not_authenticated(self, schedule_api):
        """Test get_profile_schedule raises when not authenticated."""
        schedule_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await schedule_api.get_profile_schedule("network_123", "profile_001")


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
    async def test_set_profile_schedule_returns_raw_response(self, schedule_api, mock_session):
        """Test setting profile schedule returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        time_blocks = [{"days": ["monday"], "start": "21:00", "end": "07:00"}]
        result = await schedule_api.set_profile_schedule("network_123", "profile_001", time_blocks)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_profile_schedule_not_authenticated(self, schedule_api):
        """Test set_profile_schedule raises when not authenticated."""
        schedule_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await schedule_api.set_profile_schedule("network_123", "profile_001", [])


class TestScheduleAPIBedtime:
    """Tests for bedtime methods."""

    @pytest.fixture
    def schedule_api(self, mock_session):
        """Create a ScheduleAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ScheduleAPI(auth_api)

    @pytest.mark.asyncio
    async def test_enable_bedtime_returns_raw_response(self, schedule_api, mock_session):
        """Test enabling bedtime returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await schedule_api.enable_bedtime("network_123", "profile_001", "21:00", "07:00")

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_set_weekday_bedtime_returns_raw_response(self, schedule_api, mock_session):
        """Test setting weekday bedtime returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await schedule_api.set_weekday_bedtime(
            "network_123", "profile_001", "21:00", "07:00"
        )

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_clear_profile_schedule_returns_raw_response(self, schedule_api, mock_session):
        """Test clearing profile schedule returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await schedule_api.clear_profile_schedule("network_123", "profile_001")

        assert "meta" in result
