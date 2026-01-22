"""Unit tests for the ActivityAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.activity import ActivityAPI
from eero.exceptions import EeroAuthenticationException


class TestActivityAPIInitialization:
    """Tests for ActivityAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test ActivityAPI initializes with auth API."""
        api = ActivityAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetActivity:
    """Tests for get_activity method."""

    async def test_get_activity_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test get_activity returns raw API response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        activity_data = {
            "total_usage": 1024000,
            "top_clients": ["device1", "device2"],
            "period": "day",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(activity_data)
            result = await api.get_activity("network123")

            # Returns raw response with meta and data
            assert "meta" in result
            assert "data" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity",
                auth_token="test_token",
            )

    async def test_get_activity_not_authenticated(self, mock_auth_api):
        """Test get_activity raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_activity("network123")


class TestGetActivityClients:
    """Tests for get_activity_clients method."""

    async def test_get_activity_clients_returns_raw_response(
        self, mock_auth_api, mock_api_response
    ):
        """Test get_activity_clients returns raw API response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        clients_data = [
            {"device_id": "device1", "usage": 512000},
            {"device_id": "device2", "usage": 256000},
        ]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(clients_data)
            result = await api.get_activity_clients("network123")

            assert "meta" in result
            assert "data" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity/clients",
                auth_token="test_token",
            )

    async def test_get_activity_clients_not_authenticated(self, mock_auth_api):
        """Test get_activity_clients raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_activity_clients("network123")


class TestGetActivityForDevice:
    """Tests for get_activity_for_device method."""

    async def test_get_activity_for_device_returns_raw_response(
        self, mock_auth_api, mock_api_response
    ):
        """Test get_activity_for_device returns raw API response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        device_activity = {
            "device_id": "device123",
            "usage": 1024000,
            "categories": {"streaming": 500000, "gaming": 300000},
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(device_activity)
            result = await api.get_activity_for_device("network123", "device123")

            assert "meta" in result
            assert "data" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity/device123",
                auth_token="test_token",
            )

    async def test_get_activity_for_device_not_authenticated(self, mock_auth_api):
        """Test get_activity_for_device raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_activity_for_device("network123", "device123")


class TestGetActivityHistory:
    """Tests for get_activity_history method."""

    async def test_get_activity_history_returns_raw_response(
        self, mock_auth_api, mock_api_response
    ):
        """Test get_activity_history returns raw API response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        history_data = {"period": "day", "data_points": [100, 200, 300]}

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(history_data)
            result = await api.get_activity_history("network123")

            assert "meta" in result
            assert "data" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity/history",
                auth_token="test_token",
                params={"period": "day"},
            )

    async def test_get_activity_history_custom_period(self, mock_auth_api, mock_api_response):
        """Test get_activity_history with custom period."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        history_data = {"period": "week", "data_points": [1000, 2000, 3000]}

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(history_data)
            result = await api.get_activity_history("network123", period="week")

            assert "meta" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity/history",
                auth_token="test_token",
                params={"period": "week"},
            )

    async def test_get_activity_history_not_authenticated(self, mock_auth_api):
        """Test get_activity_history raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_activity_history("network123")


class TestGetActivityCategories:
    """Tests for get_activity_categories method."""

    async def test_get_activity_categories_returns_raw_response(
        self, mock_auth_api, mock_api_response
    ):
        """Test get_activity_categories returns raw API response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        categories_data = [
            {"name": "streaming", "usage": 500000},
            {"name": "gaming", "usage": 300000},
        ]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(categories_data)
            result = await api.get_activity_categories("network123")

            assert "meta" in result
            assert "data" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity/categories",
                auth_token="test_token",
            )

    async def test_get_activity_categories_not_authenticated(self, mock_auth_api):
        """Test get_activity_categories raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_activity_categories("network123")
