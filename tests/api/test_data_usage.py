"""Tests for DataUsageAPI module."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.data_usage import DataUsageAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response

START = "2026-07-01T00:00:00Z"
END = "2026-07-02T00:00:00Z"


class TestDataUsageAPIInit:
    """Tests for DataUsageAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = DataUsageAPI(auth_api)
        assert api._auth_api is auth_api


@pytest.fixture
def data_usage_api(mock_session):
    """Create a DataUsageAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return DataUsageAPI(auth_api)


class TestDataUsageAPIGetDataUsage:
    """Tests for get_data_usage (required cadence, root path)."""

    @pytest.mark.asyncio
    async def test_url_and_params(self, data_usage_api, mock_session):
        """Test the URL, method, and query parameters."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"download": 1})
        )

        result = await data_usage_api.get_data_usage(
            "network_123", start=START, end=END, cadence="daily"
        )

        assert "meta" in result and "data" in result
        call_args = mock_session.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1].endswith("networks/network_123/data_usage")
        assert call_args[1]["params"] == {"start": START, "end": END, "cadence": "daily"}
        assert "json" not in call_args[1] or call_args[1]["json"] is None

    @pytest.mark.asyncio
    async def test_timezone_included_when_supplied(self, data_usage_api, mock_session):
        """Test timezone is included in params when supplied."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await data_usage_api.get_data_usage(
            "network_123", start=START, end=END, cadence="hourly", timezone="UTC"
        )

        call_args = mock_session.request.call_args
        assert call_args[1]["params"] == {
            "start": START,
            "end": END,
            "cadence": "hourly",
            "timezone": "UTC",
        }

    @pytest.mark.asyncio
    async def test_timezone_omitted_when_none(self, data_usage_api, mock_session):
        """Test timezone key is absent from params when not supplied."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await data_usage_api.get_data_usage("network_123", start=START, end=END, cadence="daily")

        call_args = mock_session.request.call_args
        assert "timezone" not in call_args[1]["params"]

    @pytest.mark.asyncio
    async def test_cadence_required(self, data_usage_api):
        """Test cadence is a required keyword argument."""
        with pytest.raises(TypeError):
            await data_usage_api.get_data_usage("network_123", start=START, end=END)  # type: ignore[call-arg]

    @pytest.mark.parametrize("bad_cadence", ["weekly", "", "DAILY", None])
    @pytest.mark.asyncio
    async def test_invalid_cadence_rejected_before_request(
        self, data_usage_api, mock_session, bad_cadence
    ):
        """Test an invalid cadence is rejected before any request is made."""
        with pytest.raises(EeroValidationException):
            await data_usage_api.get_data_usage(
                "network_123", start=START, end=END, cadence=bad_cadence
            )
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_not_authenticated(self, data_usage_api):
        """Test raises when not authenticated."""
        data_usage_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await data_usage_api.get_data_usage(
                "network_123", start=START, end=END, cadence="daily"
            )


class TestDataUsageAPIOptionalCadenceFamily:
    """Parametrised tests for reads where cadence is optional (not API-required)."""

    @pytest.mark.parametrize(
        "method_name, extra_args, path_suffix",
        [
            ("get_breakdown", {}, "data_usage/breakdown"),
            ("get_devices_usage", {}, "data_usage/devices"),
            ("get_unprofiled_devices", {}, "data_usage/unprofiled/devices"),
        ],
    )
    @pytest.mark.asyncio
    async def test_url_and_required_params(
        self, data_usage_api, mock_session, method_name, extra_args, path_suffix
    ):
        """Test path template and that start/end are always present."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        method = getattr(data_usage_api, method_name)

        await method("network_123", start=START, end=END, **extra_args)

        call_args = mock_session.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1].endswith(f"networks/network_123/{path_suffix}")
        params = call_args[1]["params"]
        assert params["start"] == START
        assert params["end"] == END
        assert "cadence" not in params

    @pytest.mark.parametrize(
        "method_name, extra_args",
        [
            ("get_breakdown", {}),
            ("get_devices_usage", {}),
            ("get_unprofiled_devices", {}),
        ],
    )
    @pytest.mark.asyncio
    async def test_cadence_included_when_supplied(
        self, data_usage_api, mock_session, method_name, extra_args
    ):
        """Test cadence is forwarded when explicitly supplied."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        method = getattr(data_usage_api, method_name)

        await method("network_123", start=START, end=END, cadence="hourly", **extra_args)

        call_args = mock_session.request.call_args
        assert call_args[1]["params"]["cadence"] == "hourly"

    @pytest.mark.parametrize(
        "method_name",
        ["get_breakdown", "get_devices_usage", "get_unprofiled_devices"],
    )
    @pytest.mark.asyncio
    async def test_invalid_cadence_rejected(self, data_usage_api, mock_session, method_name):
        """Test an explicitly-supplied invalid cadence is still rejected."""
        method = getattr(data_usage_api, method_name)

        with pytest.raises(EeroValidationException):
            await method("network_123", start=START, end=END, cadence="weekly")
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_devices_usage_profile_id_included_when_supplied(
        self, data_usage_api, mock_session
    ):
        """Test profile_id is included when supplied."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await data_usage_api.get_devices_usage(
            "network_123", start=START, end=END, profile_id="profile_abc"
        )

        call_args = mock_session.request.call_args
        assert call_args[1]["params"]["profile_id"] == "profile_abc"

    @pytest.mark.asyncio
    async def test_devices_usage_profile_id_omitted_when_none(self, data_usage_api, mock_session):
        """Test profile_id key is absent from params when not supplied."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await data_usage_api.get_devices_usage("network_123", start=START, end=END)

        call_args = mock_session.request.call_args
        assert "profile_id" not in call_args[1]["params"]


class TestDataUsageAPIRequiredCadenceFamily:
    """Parametrised tests for reads where the API requires cadence."""

    @pytest.mark.parametrize(
        "method_name, args, path_suffix",
        [
            ("get_device_usage", ("device_mac_aa",), "data_usage/devices/device_mac_aa"),
            ("get_eeros_summary", (), "data_usage/eeros/summary"),
            ("get_eero_usage", ("eero_1",), "data_usage/eeros/eero_1"),
            ("get_profile_usage", ("profile_1",), "data_usage/profiles/profile_1"),
            ("get_unprofiled_summary", (), "data_usage/unprofiled/summary"),
        ],
    )
    @pytest.mark.asyncio
    async def test_url_and_params(
        self, data_usage_api, mock_session, method_name, args, path_suffix
    ):
        """Test path template and that cadence is present and required."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        method = getattr(data_usage_api, method_name)

        await method("network_123", *args, start=START, end=END, cadence="daily")

        call_args = mock_session.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1].endswith(f"networks/network_123/{path_suffix}")
        assert call_args[1]["params"] == {"start": START, "end": END, "cadence": "daily"}

    @pytest.mark.parametrize(
        "method_name, args",
        [
            ("get_device_usage", ("device_mac_aa",)),
            ("get_eeros_summary", ()),
            ("get_eero_usage", ("eero_1",)),
            ("get_profile_usage", ("profile_1",)),
            ("get_unprofiled_summary", ()),
        ],
    )
    @pytest.mark.asyncio
    async def test_cadence_required(self, data_usage_api, method_name, args):
        """Test omitting cadence raises TypeError before any request."""
        method = getattr(data_usage_api, method_name)

        with pytest.raises(TypeError):
            await method("network_123", *args, start=START, end=END)  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "method_name, args",
        [
            ("get_device_usage", ("device_mac_aa",)),
            ("get_eeros_summary", ()),
            ("get_eero_usage", ("eero_1",)),
            ("get_profile_usage", ("profile_1",)),
            ("get_unprofiled_summary", ()),
        ],
    )
    @pytest.mark.asyncio
    async def test_invalid_cadence_rejected(self, data_usage_api, mock_session, method_name, args):
        """Test an invalid cadence is rejected before any request is made."""
        method = getattr(data_usage_api, method_name)

        with pytest.raises(EeroValidationException):
            await method("network_123", *args, start=START, end=END, cadence="weekly")
        mock_session.request.assert_not_called()


class TestDataUsageAPIReportSettings:
    """Tests for get_report_settings / set_report_settings."""

    @pytest.mark.asyncio
    async def test_get_report_settings_url(self, data_usage_api, mock_session):
        """Test GET path and no query parameters."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        result = await data_usage_api.get_report_settings("network_123")

        assert "meta" in result and "data" in result
        call_args = mock_session.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1].endswith("networks/network_123/data_usage/report_settings")

    @pytest.mark.asyncio
    async def test_set_report_settings_sends_json_body(self, data_usage_api, mock_session):
        """Test PUT sends the cadence/notification_day JSON body."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        result = await data_usage_api.set_report_settings(
            "network_123", cadence="daily", notification_day="monday"
        )

        assert "meta" in result and "data" in result
        call_args = mock_session.request.call_args
        assert call_args[0][0] == "PUT"
        assert call_args[0][1].endswith("networks/network_123/data_usage/report_settings")
        assert call_args[1]["json"] == {"cadence": "daily", "notification_day": "monday"}

    @pytest.mark.asyncio
    async def test_set_report_settings_invalid_cadence_rejected(self, data_usage_api, mock_session):
        """Test an invalid cadence is rejected before any request is made."""
        with pytest.raises(EeroValidationException):
            await data_usage_api.set_report_settings(
                "network_123", cadence="weekly", notification_day="monday"
            )
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_report_settings_logs_uncharacterised_warning(
        self, data_usage_api, mock_session, caplog
    ):
        """Test the write logs a WARNING that its side effects are uncharacterised."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await data_usage_api.set_report_settings(
                "network_123", cadence="daily", notification_day="monday"
            )

        assert any(
            "characteris" in record.getMessage().lower()
            and "side effect" in record.getMessage().lower()
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_get_report_settings_not_authenticated(self, data_usage_api):
        """Test raises when not authenticated."""
        data_usage_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await data_usage_api.get_report_settings("network_123")

    @pytest.mark.asyncio
    async def test_set_report_settings_not_authenticated(self, data_usage_api):
        """Test raises when not authenticated."""
        data_usage_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await data_usage_api.set_report_settings(
                "network_123", cadence="daily", notification_day="monday"
            )
