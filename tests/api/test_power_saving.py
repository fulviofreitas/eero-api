"""Tests for PowerSavingAPI module.

Tests cover:
- set_power_saving: only-given-keys, no-field rejection, the
  uncharacterised-write warning
- get_schedules: verified read
- create_schedule / update_schedule / delete_schedule: JSON bodies, URL
  construction, the uncharacterised-write warning
- Not-authenticated errors on every method
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.power_saving import PowerSavingAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def power_saving_api(mock_session):
    """Create a PowerSavingAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return PowerSavingAPI(auth_api)


class TestPowerSavingAPIInit:
    """Tests for PowerSavingAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = PowerSavingAPI(auth_api)

        assert api._auth_api is auth_api


class TestPowerSavingAPISetPowerSaving:
    """Tests for set_power_saving method."""

    @pytest.mark.asyncio
    async def test_set_power_saving_sends_only_given_fields(
        self, power_saving_api, mock_session, caplog
    ):
        """Test set_power_saving PUTs only the supplied fields and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await power_saving_api.set_power_saving("network_123", enable=True)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/power_saving")
        assert call_args.kwargs["json"] == {"enable": True}
        assert any("set power saving for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_power_saving_sends_both_fields(self, power_saving_api, mock_session):
        """Test set_power_saving PUTs both fields when both are supplied."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await power_saving_api.set_power_saving(
            "network_123", enable=True, power_saving_schedule_enabled=False
        )

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {
            "enable": True,
            "power_saving_schedule_enabled": False,
        }

    @pytest.mark.asyncio
    async def test_set_power_saving_rejects_no_fields(self, power_saving_api):
        """Test set_power_saving rejects a call with no field supplied."""
        with pytest.raises(EeroValidationException):
            await power_saving_api.set_power_saving("network_123")

    @pytest.mark.asyncio
    async def test_set_power_saving_not_authenticated(self, power_saving_api):
        """Test set_power_saving raises when not authenticated."""
        power_saving_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await power_saving_api.set_power_saving("network_123", enable=True)


class TestPowerSavingAPIGetSchedules:
    """Tests for get_schedules method."""

    @pytest.mark.asyncio
    async def test_get_schedules_returns_raw_response(self, power_saving_api, mock_session):
        """Test get_schedules GETs the power_saving/schedules sub-resource."""
        expected = {"schedules": []}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(expected)
        )

        result = await power_saving_api.get_schedules("network_123")

        assert result["data"] == expected
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/power_saving/schedules")

    @pytest.mark.asyncio
    async def test_get_schedules_not_authenticated(self, power_saving_api):
        """Test get_schedules raises when not authenticated."""
        power_saving_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await power_saving_api.get_schedules("network_123")


class TestPowerSavingAPICreateSchedule:
    """Tests for create_schedule method."""

    @pytest.mark.asyncio
    async def test_create_schedule_sends_json(self, power_saving_api, mock_session, caplog):
        """Test create_schedule POSTs the schedule fields and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await power_saving_api.create_schedule(
                "network_123",
                name="Overnight",
                days=["MON", "TUE"],
                start_time="22:00",
                end_time="06:00",
            )

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/networks/network_123/power_saving/schedules")
        assert call_args.kwargs["json"] == {
            "name": "Overnight",
            "days": ["MON", "TUE"],
            "start_time": "22:00",
            "end_time": "06:00",
            "enabled": True,
        }
        assert any(
            "create power saving schedule for network" in message for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_create_schedule_not_authenticated(self, power_saving_api):
        """Test create_schedule raises when not authenticated."""
        power_saving_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await power_saving_api.create_schedule(
                "network_123", name="x", days=[], start_time="00:00", end_time="01:00"
            )


class TestPowerSavingAPIUpdateSchedule:
    """Tests for update_schedule method."""

    @pytest.mark.asyncio
    async def test_update_schedule_sends_only_given_fields(
        self, power_saving_api, mock_session, caplog
    ):
        """Test update_schedule PUTs only the supplied fields and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await power_saving_api.update_schedule("network_123", "schedule_001", enabled=False)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/power_saving/schedules/schedule_001"
        )
        assert call_args.kwargs["json"] == {"enabled": False}
        assert any(
            "update power saving schedule schedule_001 for network" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_update_schedule_rejects_no_fields(self, power_saving_api):
        """Test update_schedule rejects a call with no field supplied."""
        with pytest.raises(EeroValidationException):
            await power_saving_api.update_schedule("network_123", "schedule_001")

    @pytest.mark.asyncio
    async def test_update_schedule_not_authenticated(self, power_saving_api):
        """Test update_schedule raises when not authenticated."""
        power_saving_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await power_saving_api.update_schedule("network_123", "schedule_001", enabled=True)


class TestPowerSavingAPIDeleteSchedule:
    """Tests for delete_schedule method."""

    @pytest.mark.asyncio
    async def test_delete_schedule_sends_delete(self, power_saving_api, mock_session, caplog):
        """Test delete_schedule DELETEs the schedule sub-resource and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await power_saving_api.delete_schedule("network_123", "schedule_001")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "DELETE"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/power_saving/schedules/schedule_001"
        )
        assert any(
            "delete power saving schedule schedule_001 for network" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_delete_schedule_not_authenticated(self, power_saving_api):
        """Test delete_schedule raises when not authenticated."""
        power_saving_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await power_saving_api.delete_schedule("network_123", "schedule_001")
