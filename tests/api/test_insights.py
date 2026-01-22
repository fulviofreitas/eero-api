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
    """Tests for get_insights method."""

    @pytest.fixture
    def insights_api(self, mock_session):
        """Create an InsightsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return InsightsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_insights_returns_raw_response(self, insights_api, mock_session):
        """Test get_insights returns raw response."""
        insights_data = {"network_health": "good", "recommendations": []}
        mock_response = create_mock_response(200, api_success_response(insights_data))
        mock_session.request.return_value = mock_response

        result = await insights_api.get_insights("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_insights_not_authenticated(self, insights_api):
        """Test get_insights raises when not authenticated."""
        insights_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await insights_api.get_insights("network_123")


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
