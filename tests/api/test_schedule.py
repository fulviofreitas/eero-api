"""Tests for ScheduleAPI module.

Scheduled pauses are sub-resources of a profile
(``networks/{id}/profiles/{profile}/schedules``), created/read via that
collection and updated/deleted via their own URL. Tests cover:

- get_schedules / create_schedule (collection URL, parent-link preference)
- update_schedule / delete_schedule (own-URL resolution from a path or envelope)
- clear_profile_schedule (one read + N deletes)
- enable_bedtime / set_weekday_bedtime / set_weekend_bedtime (built on create_schedule)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.schedule import ScheduleAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def schedule_api(mock_session):
    """Create a ScheduleAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return ScheduleAPI(auth_api)


class TestScheduleAPIInit:
    """Tests for ScheduleAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = ScheduleAPI(auth_api)
        assert api._auth_api is auth_api


class TestScheduleAPIGetSchedules:
    """Tests for get_schedules method."""

    @pytest.mark.asyncio
    async def test_get_schedules_builds_template_url(self, schedule_api, mock_session):
        mock_session.request.return_value = create_mock_response(200, api_success_response([]))

        await schedule_api.get_schedules("network_123", "profile_001")

        method, url = mock_session.request.call_args.args[:2]
        assert method == "GET"
        assert url == (
            "https://api-user.e2ro.com/2.2/networks/network_123/profiles/profile_001/schedules"
        )

    @pytest.mark.asyncio
    async def test_get_schedules_prefers_parent_schedules_link(self, schedule_api, mock_session):
        mock_session.request.return_value = create_mock_response(200, api_success_response([]))
        parent = {
            "url": "/2.2/networks/network_123/profiles/profile_001",
            "resources": {"schedules": "/2.3/networks/network_123/profiles/profile_001/schedules"},
        }

        await schedule_api.get_schedules("network_123", "profile_001", parent=parent)

        _, url = mock_session.request.call_args.args[:2]
        assert url == (
            "https://api-user.e2ro.com/2.3/networks/network_123/profiles/profile_001/schedules"
        )

    @pytest.mark.asyncio
    async def test_get_schedules_network_id_with_brace_does_not_break_template(
        self, schedule_api, mock_session
    ):
        """A brace-containing network id must never leak into a format template.

        `_schedules_url` used to splice `network` into an f-string that was
        then handed to `resource_url` as its `template` argument -- a
        second `str.format` call over that combined string. A network id
        containing a stray `{...}` group broke that second call with a bare
        `KeyError` instead of a clean, caller-facing error.
        """
        mock_session.request.return_value = create_mock_response(200, api_success_response([]))

        try:
            await schedule_api.get_schedules("network{evil}", "profile_001")
        except EeroValidationException:
            pass  # acceptable: cleanly rejected
        except (KeyError, ValueError) as exc:
            pytest.fail(f"brace in network id leaked into a template: {exc!r}")

    @pytest.mark.asyncio
    async def test_get_schedules_not_authenticated(self, schedule_api):
        schedule_api._auth_api.get_auth_token = AsyncMock(return_value=None)
        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await schedule_api.get_schedules("network_123", "profile_001")


class TestScheduleAPICreateSchedule:
    """Tests for create_schedule method."""

    @pytest.mark.asyncio
    async def test_create_schedule_posts_to_schedules_collection(self, schedule_api, mock_session):
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"url": "/2.2/.../schedules/s_1"})
        )

        await schedule_api.create_schedule(
            "network_123",
            "profile_001",
            name="Bedtime",
            days=["monday", "tuesday"],
            start="21:00",
            end="07:00",
        )

        method, url = mock_session.request.call_args.args[:2]
        assert method == "POST"
        assert url.endswith("networks/network_123/profiles/profile_001/schedules")
        payload = mock_session.request.call_args.kwargs["json"]
        assert payload == {
            "name": "Bedtime",
            "days": ["monday", "tuesday"],
            "start": "21:00",
            "end": "07:00",
            "enabled": True,
        }

    @pytest.mark.asyncio
    async def test_create_schedule_logs_uncharacterised_write_warning(
        self, schedule_api, mock_session, caplog
    ):
        import logging

        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})

        with caplog.at_level(logging.WARNING, logger="eero.api.schedule"):
            await schedule_api.create_schedule(
                "network_123",
                "profile_001",
                name="Bedtime",
                days=["monday"],
                start="21:00",
                end="07:00",
            )

        assert any("not been fully characterised" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_create_schedule_not_authenticated(self, schedule_api):
        schedule_api._auth_api.get_auth_token = AsyncMock(return_value=None)
        with pytest.raises(EeroAuthenticationException):
            await schedule_api.create_schedule(
                "network_123", "profile_001", name="x", days=[], start="21:00", end="07:00"
            )


class TestScheduleAPIUpdateSchedule:
    """Tests for update_schedule method."""

    @pytest.mark.asyncio
    async def test_update_schedule_from_path_string(self, schedule_api, mock_session):
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})

        await schedule_api.update_schedule(
            "/2.2/networks/network_123/profiles/profile_001/schedules/s_1",
            enabled=False,
        )

        method, url = mock_session.request.call_args.args[:2]
        assert method == "PUT"
        assert url == (
            "https://api-user.e2ro.com/2.2/networks/network_123/profiles/profile_001/schedules/s_1"
        )
        assert mock_session.request.call_args.kwargs["json"] == {"enabled": False}

    @pytest.mark.asyncio
    async def test_update_schedule_from_envelope(self, schedule_api, mock_session):
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})
        envelope = {
            "url": "/2.3/networks/network_123/profiles/profile_001/schedules/s_1",
            "name": "Bedtime",
        }

        await schedule_api.update_schedule(envelope, start="20:00")

        _, url = mock_session.request.call_args.args[:2]
        assert url == (
            "https://api-user.e2ro.com/2.3/networks/network_123/profiles/profile_001/schedules/s_1"
        )

    @pytest.mark.asyncio
    async def test_update_schedule_envelope_without_url_raises(self, schedule_api):
        with pytest.raises(EeroValidationException):
            await schedule_api.update_schedule({"name": "no url"}, enabled=True)

    @pytest.mark.asyncio
    async def test_update_schedule_rejects_invalid_type(self, schedule_api):
        with pytest.raises(EeroValidationException):
            await schedule_api.update_schedule(12345, enabled=True)

    @pytest.mark.asyncio
    async def test_update_schedule_no_fields_raises_before_request(
        self, schedule_api, mock_session
    ):
        """No optional field supplied raises before any request is issued."""
        with pytest.raises(EeroValidationException):
            await schedule_api.update_schedule(
                "/2.2/networks/network_123/profiles/profile_001/schedules/s_1"
            )

        mock_session.request.assert_not_called()


class TestScheduleAPIDeleteSchedule:
    """Tests for delete_schedule method."""

    @pytest.mark.asyncio
    async def test_delete_schedule_deletes_own_url(self, schedule_api, mock_session):
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})

        await schedule_api.delete_schedule(
            "/2.2/networks/network_123/profiles/profile_001/schedules/s_1"
        )

        method, url = mock_session.request.call_args.args[:2]
        assert method == "DELETE"
        assert url.endswith("profiles/profile_001/schedules/s_1")

    @pytest.mark.asyncio
    async def test_delete_schedule_warns_uncharacterised_write(
        self, schedule_api, mock_session, caplog
    ):
        import logging

        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})

        with caplog.at_level(logging.WARNING, logger="eero.api.schedule"):
            await schedule_api.delete_schedule(
                "/2.2/networks/network_123/profiles/profile_001/schedules/s_1"
            )

        warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and "not been fully characterised" in r.message
        ]
        assert len(warnings) == 1


_SCHEDULE_PATH = "/2.2/networks/n1/profiles/p1/schedules/s1"
_SCHEDULE_URL = f"https://api-user.e2ro.com{_SCHEDULE_PATH}"


class TestScheduleOwnUrlConfinement:
    """A caller-supplied schedule path or URL must name a scheduled pause."""

    @pytest.fixture(params=["update", "delete"])
    def write(self, request, schedule_api):
        """Return the write under test and its expected HTTP method."""
        if request.param == "update":
            return "PUT", lambda target: schedule_api.update_schedule(target, enabled=False)
        return "DELETE", schedule_api.delete_schedule

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "target",
        [
            "/2.2/networks/n1",
            "/2.2/networks/n1/forwards/f1",
            "/2.2/account",
            "/2.2/networks/n1/profiles/p1",
            "/2.2/networks/n1/profiles/p1/schedules",
            "/2.2/networks/n1/profiles/p1/schedules/s1/extra",
            "/2.2/networks/n1/profiles/p1/devices/s1",
            "/2.2/networks/n1/extra/profiles/p1/schedules/s1",
            "/2.2/profiles/p1/schedules/s1",
            "https://api-user.e2ro.com/2.2/networks/n1/forwards/f1",
            "https://api-user.e2ro.com/2.2/account",
            "https://api-user.e2ro.com/2.2/networks/n1/profiles/p1/schedules/s1/extra",
        ],
        ids=[
            "network",
            "forward",
            "account",
            "profile",
            "collection",
            "extra-tail",
            "other-subresource",
            "extra-head",
            "no-network",
            "forward-url",
            "account-url",
            "extra-tail-url",
        ],
    )
    async def test_other_resource_is_refused_before_transport(
        self, write, mock_session, target
    ) -> None:
        """A path or URL of another shape never reaches the transport."""
        _, call = write
        with pytest.raises(EeroValidationException) as caught:
            await call(target)
        assert caught.value.field == "schedule"
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("target", [_SCHEDULE_PATH, _SCHEDULE_URL, f"{_SCHEDULE_PATH}/"])
    async def test_schedule_path_and_url_reach_the_own_url(
        self, write, mock_session, target
    ) -> None:
        """A correctly shaped path or absolute URL is written to unchanged."""
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})
        method, call = write

        await call(target)

        sent_method, url = mock_session.request.call_args.args[:2]
        assert sent_method == method
        assert url == _SCHEDULE_URL.rstrip("/")

    @pytest.mark.asyncio
    async def test_version_of_a_schedule_path_is_the_callers_own(self, write, mock_session) -> None:
        """Confinement is to the shape, not to the default API version."""
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})
        _, call = write

        await call("/2.3/networks/n1/profiles/p1/schedules/s1")

        assert mock_session.request.call_args.args[1].endswith(
            "/2.3/networks/n1/profiles/p1/schedules/s1"
        )

    @pytest.mark.asyncio
    async def test_published_envelope_url_is_not_confined(self, write, mock_session) -> None:
        """A link the API published in an envelope is used as published."""
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})
        _, call = write

        await call({"url": "/2.4/some/other/published/shape"})

        assert mock_session.request.call_args.args[1] == (
            "https://api-user.e2ro.com/2.4/some/other/published/shape"
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("target", ["s1", "account", "networks", "S1", "../account"])
    async def test_bare_id_is_refused_before_transport(self, write, mock_session, target) -> None:
        """A bare id cannot name its network and profile, so it is never sent.

        In particular a one-segment endpoint name such as ``account`` must not
        reach the transport as ``/2.2/account``.
        """
        _, call = write
        with pytest.raises(EeroValidationException) as caught:
            await call(target)
        assert caught.value.field == "schedule"
        assert "bare id" in str(caught.value)
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_envelope_url_branch_is_unchanged_by_bare_id_rule(
        self, write, mock_session
    ) -> None:
        """A full envelope still resolves to its published own URL."""
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})
        _, call = write

        await call({"meta": {"code": 200}, "data": {"url": _SCHEDULE_PATH}})

        assert mock_session.request.call_args.args[1] == _SCHEDULE_URL


class TestScheduleAPIClearProfileSchedule:
    """Tests for clear_profile_schedule (one read + N deletes)."""

    @pytest.mark.asyncio
    async def test_clear_profile_schedule_issues_one_delete_per_pause(
        self, schedule_api, mock_session
    ):
        pauses = [
            {"url": "/2.2/networks/network_123/profiles/profile_001/schedules/s_1"},
            {"url": "/2.2/networks/network_123/profiles/profile_001/schedules/s_2"},
            {"url": "/2.2/networks/network_123/profiles/profile_001/schedules/s_3"},
        ]
        get_response = create_mock_response(200, api_success_response(pauses))
        delete_responses = [create_mock_response(200, {"meta": {"code": 200}}) for _ in pauses]
        mock_session.request.side_effect = [get_response, *delete_responses]

        results = await schedule_api.clear_profile_schedule("network_123", "profile_001")

        assert len(results) == 3
        assert mock_session.request.call_count == 4  # 1 GET + 3 DELETEs
        methods = [call.args[0] for call in mock_session.request.call_args_list[1:]]
        assert methods == ["DELETE", "DELETE", "DELETE"]

    @pytest.mark.asyncio
    async def test_clear_profile_schedule_no_pauses_issues_no_deletes(
        self, schedule_api, mock_session
    ):
        mock_session.request.return_value = create_mock_response(200, api_success_response([]))

        results = await schedule_api.clear_profile_schedule("network_123", "profile_001")

        assert results == []
        assert mock_session.request.call_count == 1  # only the GET


class TestScheduleAPIBedtime:
    """Tests for enable_bedtime / set_weekday_bedtime / set_weekend_bedtime."""

    @pytest.mark.asyncio
    async def test_enable_bedtime_creates_single_pause_for_all_days(
        self, schedule_api, mock_session
    ):
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})

        await schedule_api.enable_bedtime("network_123", "profile_001", "21:00", "07:00")

        assert mock_session.request.call_count == 1
        payload = mock_session.request.call_args.kwargs["json"]
        assert payload["days"] == [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        assert payload["start"] == "21:00"
        assert payload["end"] == "07:00"

    @pytest.mark.asyncio
    async def test_set_weekday_bedtime_uses_weekdays_only(self, schedule_api, mock_session):
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})

        await schedule_api.set_weekday_bedtime("network_123", "profile_001", "21:00", "07:00")

        payload = mock_session.request.call_args.kwargs["json"]
        assert payload["days"] == ["monday", "tuesday", "wednesday", "thursday", "friday"]

    @pytest.mark.asyncio
    async def test_set_weekend_bedtime_uses_weekend_only(self, schedule_api, mock_session):
        mock_session.request.return_value = create_mock_response(200, {"meta": {"code": 200}})

        await schedule_api.set_weekend_bedtime("network_123", "profile_001", "21:00", "07:00")

        payload = mock_session.request.call_args.kwargs["json"]
        assert payload["days"] == ["saturday", "sunday"]
