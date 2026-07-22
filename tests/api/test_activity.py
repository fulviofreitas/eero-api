"""Unit tests for the ActivityAPI module.

All five methods now emit a DeprecationWarning (issue #107): the underlying
/networks/{id}/activity* endpoints return 404 on every call. Tests wrap
each invocation with ``pytest.warns(DeprecationWarning)`` and additionally
assert the message points migrators to the replacement endpoints and to
the tracking issue.
"""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.activity import ACTIVITY_DEPRECATION_MSG, ActivityAPI
from eero.exceptions import EeroAuthenticationException


class TestActivityAPIInitialization:
    """Tests for ActivityAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test ActivityAPI initializes with auth API."""
        api = ActivityAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestActivityAPIDeprecationMessage:
    """Verifies the shared deprecation message is discoverable and actionable."""

    def test_message_names_replacement_endpoints(self):
        """The migration pointer names both replacement APIs."""
        assert "InsightsAPI.get_insights" in ACTIVITY_DEPRECATION_MSG
        assert "DataUsageAPI.get_data_usage" in ACTIVITY_DEPRECATION_MSG

    def test_message_mentions_removal_target_and_issue(self):
        """The message states removal target and links the tracking issue."""
        assert "v6.0.0" in ACTIVITY_DEPRECATION_MSG
        assert "issue" in ACTIVITY_DEPRECATION_MSG.lower()
        assert "107" in ACTIVITY_DEPRECATION_MSG


class TestGetActivity:
    """Tests for get_activity method."""

    async def test_emits_deprecation_warning(self, mock_auth_api, mock_api_response):
        """Test get_activity emits DeprecationWarning naming the method."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response({})
            with pytest.warns(DeprecationWarning, match=r"get_activity"):
                await api.get_activity("network123")

    async def test_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test get_activity returns raw API response (v2.0 pass-through)."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        activity_data = {"total_usage": 1024000, "period": "day"}
        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(activity_data)
            with pytest.warns(DeprecationWarning):
                result = await api.get_activity("network123")

            assert "meta" in result
            assert "data" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity",
                auth_token="test_token",
            )

    async def test_not_authenticated(self, mock_auth_api):
        """Test get_activity raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.warns(DeprecationWarning):
            with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
                await api.get_activity("network123")


class TestGetActivityClients:
    """Tests for get_activity_clients method."""

    async def test_emits_deprecation_warning(self, mock_auth_api, mock_api_response):
        """Test get_activity_clients emits DeprecationWarning."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response([])
            with pytest.warns(DeprecationWarning, match=r"get_activity_clients"):
                await api.get_activity_clients("network123")

    async def test_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test get_activity_clients returns raw API response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        clients_data = [{"device_id": "d1", "usage": 512000}]
        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(clients_data)
            with pytest.warns(DeprecationWarning):
                result = await api.get_activity_clients("network123")

            assert "meta" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity/clients",
                auth_token="test_token",
            )

    async def test_not_authenticated(self, mock_auth_api):
        """Test get_activity_clients raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.warns(DeprecationWarning):
            with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
                await api.get_activity_clients("network123")


class TestGetActivityForDevice:
    """Tests for get_activity_for_device method."""

    async def test_emits_deprecation_warning(self, mock_auth_api, mock_api_response):
        """Test get_activity_for_device emits DeprecationWarning."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response({})
            with pytest.warns(DeprecationWarning, match=r"get_activity_for_device"):
                await api.get_activity_for_device("network123", "device123")

    async def test_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test get_activity_for_device returns raw API response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        device_activity = {"device_id": "device123", "usage": 1024000}
        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(device_activity)
            with pytest.warns(DeprecationWarning):
                result = await api.get_activity_for_device("network123", "device123")

            assert "meta" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity/device123",
                auth_token="test_token",
            )

    async def test_not_authenticated(self, mock_auth_api):
        """Test get_activity_for_device raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.warns(DeprecationWarning):
            with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
                await api.get_activity_for_device("network123", "device123")


class TestGetActivityHistory:
    """Tests for get_activity_history method."""

    async def test_emits_deprecation_warning(self, mock_auth_api, mock_api_response):
        """Test get_activity_history emits DeprecationWarning."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response({})
            with pytest.warns(DeprecationWarning, match=r"get_activity_history"):
                await api.get_activity_history("network123")

    async def test_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test get_activity_history returns raw API response with default period."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        history_data = {"period": "day", "data_points": [100, 200, 300]}
        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(history_data)
            with pytest.warns(DeprecationWarning):
                result = await api.get_activity_history("network123")

            assert "meta" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity/history",
                auth_token="test_token",
                params={"period": "day"},
            )

    async def test_custom_period(self, mock_auth_api, mock_api_response):
        """Test get_activity_history with custom period still forwards it correctly."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response({"period": "week"})
            with pytest.warns(DeprecationWarning):
                await api.get_activity_history("network123", period="week")

            mock_get.assert_called_once_with(
                "networks/network123/activity/history",
                auth_token="test_token",
                params={"period": "week"},
            )

    async def test_not_authenticated(self, mock_auth_api):
        """Test get_activity_history raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.warns(DeprecationWarning):
            with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
                await api.get_activity_history("network123")


class TestGetActivityCategories:
    """Tests for get_activity_categories method."""

    async def test_emits_deprecation_warning(self, mock_auth_api, mock_api_response):
        """Test get_activity_categories emits DeprecationWarning."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response([])
            with pytest.warns(DeprecationWarning, match=r"get_activity_categories"):
                await api.get_activity_categories("network123")

    async def test_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test get_activity_categories returns raw API response."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        categories_data = [{"name": "streaming", "usage": 500000}]
        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(categories_data)
            with pytest.warns(DeprecationWarning):
                result = await api.get_activity_categories("network123")

            assert "meta" in result
            mock_get.assert_called_once_with(
                "networks/network123/activity/categories",
                auth_token="test_token",
            )

    async def test_not_authenticated(self, mock_auth_api):
        """Test get_activity_categories raises exception when not authenticated."""
        api = ActivityAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.warns(DeprecationWarning):
            with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
                await api.get_activity_categories("network123")
