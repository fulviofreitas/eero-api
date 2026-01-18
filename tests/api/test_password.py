"""Unit tests for the PasswordAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.password import PasswordAPI
from eero.exceptions import EeroAuthenticationException


class TestPasswordAPIInitialization:
    """Tests for PasswordAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test PasswordAPI initializes with auth API."""
        api = PasswordAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetPassword:
    """Tests for get_password method."""

    async def test_get_password_success(self, mock_auth_api, mock_api_response):
        """Test successful password info retrieval."""
        api = PasswordAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        password_data = {
            "password": "MySecurePassword123",
            "last_changed": "2024-01-15T10:00:00Z",
            "strength": "strong",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(password_data)
            result = await api.get_password("network123")

            assert result == password_data
            mock_get.assert_called_once_with(
                "networks/network123/password",
                auth_token="test_token",
            )

    async def test_get_password_masked(self, mock_auth_api, mock_api_response):
        """Test get_password with masked password."""
        api = PasswordAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        password_data = {
            "password": "********",
            "last_changed": "2024-01-15T10:00:00Z",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(password_data)
            result = await api.get_password("network123")

            assert result["password"] == "********"

    async def test_get_password_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_password returns empty dict for missing data."""
        api = PasswordAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_password("network123")

            assert result == {}

    async def test_get_password_not_authenticated(self, mock_auth_api):
        """Test get_password raises exception when not authenticated."""
        api = PasswordAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_password("network123")


class TestUpdatePassword:
    """Tests for update_password method."""

    async def test_update_password_success(self, mock_auth_api, mock_api_response):
        """Test successful password update."""
        api = PasswordAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_password("network123", "NewSecurePassword456")

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/password",
                auth_token="test_token",
                json={"password": "NewSecurePassword456"},
            )

    async def test_update_password_failure(self, mock_auth_api, mock_api_response):
        """Test update_password returns false on failure."""
        api = PasswordAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 400}}
            result = await api.update_password("network123", "WeakPwd")

            assert result is False

    async def test_update_password_validation_error(self, mock_auth_api, mock_api_response):
        """Test update_password when password doesn't meet requirements."""
        api = PasswordAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            # API might return 422 for validation errors
            mock_put.return_value = {"meta": {"code": 422}}
            result = await api.update_password("network123", "123")

            assert result is False

    async def test_update_password_not_authenticated(self, mock_auth_api):
        """Test update_password raises exception when not authenticated."""
        api = PasswordAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.update_password("network123", "NewPassword")
