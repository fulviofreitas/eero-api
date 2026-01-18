"""Unit tests for the InsightsAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.insights import InsightsAPI
from eero.exceptions import EeroAuthenticationException


class TestInsightsAPIInitialization:
    """Tests for InsightsAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test InsightsAPI initializes with auth API."""
        api = InsightsAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetInsights:
    """Tests for get_insights method."""

    async def test_get_insights_success(self, mock_auth_api, mock_api_response):
        """Test successful insights retrieval."""
        api = InsightsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        insights_data = {
            "total_devices": 15,
            "active_devices": 10,
            "blocked_threats": 5,
            "data_usage": {"download": 1024000, "upload": 512000},
            "network_score": 95,
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(insights_data)
            result = await api.get_insights("network123")

            assert result == insights_data
            mock_get.assert_called_once_with(
                "networks/network123/insights",
                auth_token="test_token",
            )

    async def test_get_insights_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_insights returns empty dict for missing data."""
        api = InsightsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_insights("network123")

            assert result == {}

    async def test_get_insights_not_authenticated(self, mock_auth_api):
        """Test get_insights raises exception when not authenticated."""
        api = InsightsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_insights("network123")


class TestGetInsight:
    """Tests for get_insight method."""

    async def test_get_insight_success(self, mock_auth_api, mock_api_response):
        """Test successful specific insight retrieval."""
        api = InsightsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        insight_data = {
            "id": "security_threat",
            "title": "Security Threats Blocked",
            "value": 5,
            "description": "5 threats blocked in the last 24 hours",
            "severity": "info",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(insight_data)
            result = await api.get_insight("network123", "security_threat")

            assert result == insight_data
            mock_get.assert_called_once_with(
                "networks/network123/insights/security_threat",
                auth_token="test_token",
            )

    async def test_get_insight_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_insight returns empty dict for missing insight."""
        api = InsightsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_insight("network123", "nonexistent")

            assert result == {}

    async def test_get_insight_not_authenticated(self, mock_auth_api):
        """Test get_insight raises exception when not authenticated."""
        api = InsightsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_insight("network123", "insight123")
