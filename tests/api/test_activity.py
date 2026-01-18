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

    async def test_get_activity_success(self, mock_auth_api, mock_api_response):
        """Test successful activity retrieval."""
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

            assert result == activity_data
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

    async def test_get_activity_clients_list_response(self, mock_auth_api, mock_api_response):
        """Test get_activity_clients with list response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        clients_data = [
            {"device_id": "device1", "usage": 512000},
            {"device_id": "device2", "usage": 256000},
        ]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(clients_data)
            result = await api.get_activity_clients("network123")

            assert result == clients_data
            mock_get.assert_called_once_with(
                "networks/network123/activity/clients",
                auth_token="test_token",
            )

    async def test_get_activity_clients_nested_data_response(
        self, mock_auth_api, mock_api_response
    ):
        """Test get_activity_clients with nested data response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        clients_data = [{"device_id": "device1", "usage": 512000}]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"data": clients_data}}
            result = await api.get_activity_clients("network123")

            assert result == clients_data

    async def test_get_activity_clients_clients_key_response(
        self, mock_auth_api, mock_api_response
    ):
        """Test get_activity_clients with 'clients' key response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        clients_data = [{"device_id": "device1", "usage": 512000}]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"clients": clients_data}}
            result = await api.get_activity_clients("network123")

            assert result == clients_data

    async def test_get_activity_clients_not_authenticated(self, mock_auth_api):
        """Test get_activity_clients raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_activity_clients("network123")


class TestGetActivityForDevice:
    """Tests for get_activity_for_device method."""

    async def test_get_activity_for_device_success(self, mock_auth_api, mock_api_response):
        """Test successful device activity retrieval."""
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

            assert result == device_activity
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

    async def test_get_activity_history_default_period(self, mock_auth_api, mock_api_response):
        """Test get_activity_history with default period."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        history_data = {"period": "day", "data_points": [100, 200, 300]}

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(history_data)
            result = await api.get_activity_history("network123")

            assert result == history_data
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

            assert result == history_data
            mock_get.assert_called_once_with(
                "networks/network123/activity/history",
                auth_token="test_token",
                params={"period": "week"},
            )

    async def test_get_activity_history_invalid_period_defaults_to_day(
        self, mock_auth_api, mock_api_response
    ):
        """Test get_activity_history with invalid period defaults to 'day'."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        history_data = {"period": "day", "data_points": [100, 200, 300]}

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(history_data)
            result = await api.get_activity_history("network123", period="invalid")

            assert result == history_data
            mock_get.assert_called_once_with(
                "networks/network123/activity/history",
                auth_token="test_token",
                params={"period": "day"},
            )

    async def test_get_activity_history_not_authenticated(self, mock_auth_api):
        """Test get_activity_history raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_activity_history("network123")


class TestGetActivityCategories:
    """Tests for get_activity_categories method."""

    async def test_get_activity_categories_list_response(self, mock_auth_api, mock_api_response):
        """Test get_activity_categories with list response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        categories_data = [
            {"name": "streaming", "usage": 500000},
            {"name": "gaming", "usage": 300000},
            {"name": "social", "usage": 200000},
        ]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(categories_data)
            result = await api.get_activity_categories("network123")

            assert result == categories_data
            mock_get.assert_called_once_with(
                "networks/network123/activity/categories",
                auth_token="test_token",
            )

    async def test_get_activity_categories_dict_response(self, mock_auth_api, mock_api_response):
        """Test get_activity_categories with dict response containing categories key."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        categories_data = [{"name": "streaming", "usage": 500000}]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"categories": categories_data}}
            result = await api.get_activity_categories("network123")

            assert result == categories_data

    async def test_get_activity_categories_not_authenticated(self, mock_auth_api):
        """Test get_activity_categories raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_activity_categories("network123")
