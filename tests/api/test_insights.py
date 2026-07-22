"""Tests for InsightsAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.insights import InsightsAPI
from eero.exceptions import EeroAuthenticationException

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


class TestInsightsAPIRunInsights:
    """Tests for run_insights method."""

    @pytest.fixture
    def insights_api(self, mock_session):
        """Create an InsightsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return InsightsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_run_insights_returns_raw_response(self, insights_api, mock_session):
        """Test run_insights returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await insights_api.run_insights("network_123")

        assert "meta" in result
