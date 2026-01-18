"""Unit tests for the SettingsAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.settings import SettingsAPI
from eero.exceptions import EeroAuthenticationException


class TestSettingsAPIInitialization:
    """Tests for SettingsAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test SettingsAPI initializes with auth API."""
        api = SettingsAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetSettings:
    """Tests for get_settings method."""

    async def test_get_settings_success(self, mock_auth_api, mock_api_response):
        """Test successful settings retrieval."""
        api = SettingsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        settings_data = {
            "network_name": "MyNetwork",
            "password": "********",
            "timezone": "America/Los_Angeles",
            "country_code": "US",
            "locale": "en-US",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(settings_data)
            result = await api.get_settings("network123")

            assert result == settings_data
            mock_get.assert_called_once_with(
                "networks/network123/settings",
                auth_token="test_token",
            )

    async def test_get_settings_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_settings returns empty dict for missing data."""
        api = SettingsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_settings("network123")

            assert result == {}

    async def test_get_settings_not_authenticated(self, mock_auth_api):
        """Test get_settings raises exception when not authenticated."""
        api = SettingsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_settings("network123")


class TestUpdateSettings:
    """Tests for update_settings method."""

    async def test_update_settings_success(self, mock_auth_api, mock_api_response):
        """Test successful settings update."""
        api = SettingsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        settings = {
            "network_name": "NewNetworkName",
            "timezone": "America/New_York",
        }

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_settings("network123", settings)

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/settings",
                auth_token="test_token",
                json=settings,
            )

    async def test_update_settings_single_field(self, mock_auth_api, mock_api_response):
        """Test updating a single setting field."""
        api = SettingsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        settings = {"locale": "es-ES"}

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_settings("network123", settings)

            assert result is True

    async def test_update_settings_failure(self, mock_auth_api, mock_api_response):
        """Test update_settings returns false on failure."""
        api = SettingsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 400}}
            result = await api.update_settings("network123", {})

            assert result is False

    async def test_update_settings_not_authenticated(self, mock_auth_api):
        """Test update_settings raises exception when not authenticated."""
        api = SettingsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.update_settings("network123", {})
