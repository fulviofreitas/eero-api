"""Tests for InsightsAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.insights import InsightsAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response


class TestInsightsAPIInit:
    """Tests for InsightsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = InsightsAPI(auth_api)
        assert api._auth_api is auth_api


class TestInsightsAPIGetInsights:
    """Tests for get_insights method — verifies required query params.

    The Eero cloud API rejects /insights without start/end/insight_type/cadence
    (400 error.form.errors), so the SDK forwards all four as query params.
    Only cadence has an SDK-supplied default of "daily".
    """

    @pytest.fixture
    def insights_api(self, mock_session):
        """Create an InsightsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return InsightsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_insights_forwards_all_params(self, insights_api, mock_session):
        """Test all four required params (start/end/insight_type/cadence) are sent."""
        mock_response = create_mock_response(200, api_success_response({"series": []}))
        mock_session.request.return_value = mock_response

        await insights_api.get_insights(
            "network_123",
            start="2026-07-21T00:00:00Z",
            end="2026-07-22T00:00:00Z",
            insight_type="adblock",
            cadence="hourly",
        )

        params = mock_session.request.call_args.kwargs["params"]
        assert params == {
            "start": "2026-07-21T00:00:00Z",
            "end": "2026-07-22T00:00:00Z",
            "cadence": "hourly",
            "insight_type": "adblock",
        }

    @pytest.mark.asyncio
    async def test_get_insights_cadence_defaults_to_daily(self, insights_api, mock_session):
        """Test cadence defaults to 'daily' when caller omits it (only SDK default)."""
        mock_response = create_mock_response(200, api_success_response({"series": []}))
        mock_session.request.return_value = mock_response

        await insights_api.get_insights(
            "network_123",
            start="2026-07-21T00:00:00Z",
            end="2026-07-22T00:00:00Z",
            insight_type="blocked",
        )

        params = mock_session.request.call_args.kwargs["params"]
        assert params["cadence"] == "daily"

    @pytest.mark.asyncio
    async def test_get_insights_returns_raw_response(self, insights_api, mock_session):
        """Test get_insights returns raw response without transformation."""
        raw = {"meta": {"code": 200}, "data": {"series": [{"insight_type": "adblock"}]}}
        mock_response = create_mock_response(200, raw)
        mock_session.request.return_value = mock_response

        result = await insights_api.get_insights(
            "network_123",
            start="2026-07-21T00:00:00Z",
            end="2026-07-22T00:00:00Z",
            insight_type="adblock",
        )

        # v2.0 contract: envelope passes through untouched.
        assert result == raw

    @pytest.mark.asyncio
    async def test_get_insights_rejects_cadence_outside_the_api_set(
        self, insights_api, mock_session
    ):
        """Only the API's two cadence buckets are accepted; nothing is sent otherwise."""
        from eero.exceptions import EeroValidationException

        with pytest.raises(EeroValidationException):
            await insights_api.get_insights(
                "network_123",
                start="2026-07-21T00:00:00Z",
                end="2026-07-22T00:00:00Z",
                insight_type="adblock",
                cadence="weekly",
            )

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_insights_rejects_invalid_cadence(self, insights_api):
        """Test get_insights now validates cadence like its siblings."""
        with pytest.raises(EeroValidationException):
            await insights_api.get_insights(
                "network_123",
                start="2026-07-21T00:00:00Z",
                end="2026-07-22T00:00:00Z",
                insight_type="adblock",
                cadence="monthly",
            )

    @pytest.mark.asyncio
    async def test_get_insights_requires_keyword_args(self, insights_api):
        """Test start/end/insight_type are keyword-only (positional call raises)."""
        with pytest.raises(TypeError):
            await insights_api.get_insights(
                "network_123", "2026-07-21T00:00:00Z"  # type: ignore[call-arg]
            )

    @pytest.mark.asyncio
    async def test_get_insights_not_authenticated(self, insights_api):
        """Test get_insights raises when not authenticated."""
        insights_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await insights_api.get_insights(
                "network_123",
                start="2026-07-21T00:00:00Z",
                end="2026-07-22T00:00:00Z",
                insight_type="adblock",
            )


@pytest.fixture
def insights_api(mock_session):
    """Create an InsightsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return InsightsAPI(auth_api)


_WINDOW = {"start": "2026-07-21T00:00:00Z", "end": "2026-07-22T00:00:00Z"}


class TestInsightsAPIDevicesInsights:
    """Tests for get_devices_insights (collection) and get_device_insights (single)."""

    @pytest.mark.asyncio
    async def test_get_devices_insights_builds_url_and_params(self, insights_api, mock_session):
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"series": []})
        )

        await insights_api.get_devices_insights(
            "network_123", cadence="daily", insight_type="blocked", **_WINDOW
        )

        method, url = mock_session.request.call_args.args[:2]
        assert method == "GET"
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123/insights/devices"
        assert mock_session.request.call_args.kwargs["params"] == {
            "start": _WINDOW["start"],
            "end": _WINDOW["end"],
            "cadence": "daily",
            "insight_type": "blocked",
        }

    @pytest.mark.asyncio
    async def test_get_devices_insights_invalid_cadence_raises(self, insights_api):
        with pytest.raises(EeroValidationException):
            await insights_api.get_devices_insights(
                "network_123", cadence="weekly", insight_type="blocked", **_WINDOW
            )

    @pytest.mark.asyncio
    async def test_get_device_insights_builds_url(self, insights_api, mock_session):
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"series": []})
        )

        await insights_api.get_device_insights(
            "network_123", "aabbccddeeff", cadence="hourly", insight_type="inspected", **_WINDOW
        )

        _, url = mock_session.request.call_args.args[:2]
        assert url == (
            "https://api-user.e2ro.com/2.2/networks/network_123/insights/devices/aabbccddeeff"
        )

    @pytest.mark.asyncio
    async def test_get_device_insights_network_id_with_brace_does_not_break_template(
        self, insights_api, mock_session
    ):
        """A brace-containing network id must never leak into a format template.

        This call used to build `resource_url(mac, f"networks/{network}/...")`
        -- splicing `network` into the `template` argument, which `resource_url`
        then formats a second time to substitute `mac`. A network id
        containing a stray `{...}` group broke that second `.format()` call
        with a bare `KeyError`.
        """
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"series": []})
        )

        try:
            await insights_api.get_device_insights(
                "network{evil}",
                "aabbccddeeff",
                cadence="hourly",
                insight_type="inspected",
                **_WINDOW,
            )
        except EeroValidationException:
            pass  # acceptable: cleanly rejected
        except (KeyError, ValueError) as exc:
            pytest.fail(f"brace in network id leaked into a template: {exc!r}")


class TestInsightsAPIProfilesInsights:
    """Tests for get_profiles_insights (collection), get_profile_insights (single),
    and get_profile_devices_insights."""

    @pytest.mark.asyncio
    async def test_get_profiles_insights_builds_url(self, insights_api, mock_session):
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"series": []})
        )

        await insights_api.get_profiles_insights(
            "network_123", cadence="daily", insight_type="adblock", **_WINDOW
        )

        _, url = mock_session.request.call_args.args[:2]
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123/insights/profiles"

    @pytest.mark.asyncio
    async def test_get_profile_insights_builds_url(self, insights_api, mock_session):
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"series": []})
        )

        await insights_api.get_profile_insights(
            "network_123", "profile_001", cadence="daily", insight_type="adblock", **_WINDOW
        )

        _, url = mock_session.request.call_args.args[:2]
        assert url == (
            "https://api-user.e2ro.com/2.2/networks/network_123/insights/profiles/profile_001"
        )

    @pytest.mark.asyncio
    async def test_get_profile_devices_insights_builds_url(self, insights_api, mock_session):
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"series": []})
        )

        await insights_api.get_profile_devices_insights(
            "network_123", "profile_001", cadence="daily", insight_type="adblock", **_WINDOW
        )

        _, url = mock_session.request.call_args.args[:2]
        assert url == (
            "https://api-user.e2ro.com/2.2/networks/network_123"
            "/insights/profiles/profile_001/devices"
        )

    @pytest.mark.asyncio
    async def test_get_profile_insights_network_id_with_brace_does_not_break_template(
        self, insights_api, mock_session
    ):
        """A brace-containing network id must never leak into a format template."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"series": []})
        )

        try:
            await insights_api.get_profile_insights(
                "network{evil}",
                "profile_001",
                cadence="daily",
                insight_type="adblock",
                **_WINDOW,
            )
        except EeroValidationException:
            pass  # acceptable: cleanly rejected
        except (KeyError, ValueError) as exc:
            pytest.fail(f"brace in network id leaked into a template: {exc!r}")

    @pytest.mark.asyncio
    async def test_get_profile_devices_insights_network_id_with_brace_does_not_break_template(
        self, insights_api, mock_session
    ):
        """A brace-containing network id must never leak into a format template."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"series": []})
        )

        try:
            await insights_api.get_profile_devices_insights(
                "network{evil}",
                "profile_001",
                cadence="daily",
                insight_type="adblock",
                **_WINDOW,
            )
        except EeroValidationException:
            pass  # acceptable: cleanly rejected
        except (KeyError, ValueError) as exc:
            pytest.fail(f"brace in network id leaked into a template: {exc!r}")

    @pytest.mark.asyncio
    async def test_get_profile_insights_not_authenticated(self, insights_api):
        insights_api._auth_api.get_auth_token = AsyncMock(return_value=None)
        with pytest.raises(EeroAuthenticationException):
            await insights_api.get_profile_insights(
                "network_123", "profile_001", cadence="daily", insight_type="adblock", **_WINDOW
            )
