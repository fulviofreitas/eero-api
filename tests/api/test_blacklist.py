"""Unit tests for the BlacklistAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.blacklist import BlacklistAPI
from eero.exceptions import EeroAuthenticationException


class TestBlacklistAPIInitialization:
    """Tests for BlacklistAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test BlacklistAPI initializes with auth API."""
        api = BlacklistAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetBlacklist:
    """Tests for get_blacklist method."""

    async def test_get_blacklist_list_response(self, mock_auth_api, mock_api_response):
        """Test get_blacklist with list response."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        blacklist_data = [
            {"device_id": "device1", "mac": "AA:BB:CC:DD:EE:FF"},
            {"device_id": "device2", "mac": "11:22:33:44:55:66"},
        ]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(blacklist_data)
            result = await api.get_blacklist("network123")

            assert result == blacklist_data
            mock_get.assert_called_once_with(
                "networks/network123/blacklist",
                auth_token="test_token",
            )

    async def test_get_blacklist_nested_data_response(self, mock_auth_api, mock_api_response):
        """Test get_blacklist with nested data response."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        blacklist_data = [{"device_id": "device1", "mac": "AA:BB:CC:DD:EE:FF"}]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"data": blacklist_data}}
            result = await api.get_blacklist("network123")

            assert result == blacklist_data

    async def test_get_blacklist_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_blacklist returns empty list for invalid response format."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": "invalid"}
            result = await api.get_blacklist("network123")

            assert result == []

    async def test_get_blacklist_not_authenticated(self, mock_auth_api):
        """Test get_blacklist raises exception when not authenticated."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_blacklist("network123")


class TestAddToBlacklist:
    """Tests for add_to_blacklist method."""

    async def test_add_to_blacklist_success(self, mock_auth_api, mock_api_response):
        """Test successful device addition to blacklist."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"meta": {"code": 200}}
            result = await api.add_to_blacklist("network123", "device456")

            assert result is True
            mock_post.assert_called_once_with(
                "networks/network123/blacklist",
                auth_token="test_token",
                json={"device_id": "device456"},
            )

    async def test_add_to_blacklist_failure(self, mock_auth_api, mock_api_response):
        """Test add_to_blacklist returns false on failure."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"meta": {"code": 400}}
            result = await api.add_to_blacklist("network123", "device456")

            assert result is False

    async def test_add_to_blacklist_not_authenticated(self, mock_auth_api):
        """Test add_to_blacklist raises exception when not authenticated."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.add_to_blacklist("network123", "device456")


class TestRemoveFromBlacklist:
    """Tests for remove_from_blacklist method."""

    async def test_remove_from_blacklist_success(self, mock_auth_api, mock_api_response):
        """Test successful device removal from blacklist."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {"meta": {"code": 200}}
            result = await api.remove_from_blacklist("network123", "device456")

            assert result is True
            mock_delete.assert_called_once_with(
                "networks/network123/blacklist/device456",
                auth_token="test_token",
            )

    async def test_remove_from_blacklist_failure(self, mock_auth_api, mock_api_response):
        """Test remove_from_blacklist returns false on failure."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {"meta": {"code": 400}}
            result = await api.remove_from_blacklist("network123", "device456")

            assert result is False

    async def test_remove_from_blacklist_not_authenticated(self, mock_auth_api):
        """Test remove_from_blacklist raises exception when not authenticated."""
        api = BlacklistAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.remove_from_blacklist("network123", "device456")
