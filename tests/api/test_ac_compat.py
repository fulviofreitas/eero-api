"""Unit tests for the ACCompatAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.ac_compat import ACCompatAPI
from eero.exceptions import EeroAuthenticationException


class TestACCompatAPIInitialization:
    """Tests for ACCompatAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test ACCompatAPI initializes with auth API."""
        api = ACCompatAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetACCompat:
    """Tests for get_ac_compat method."""

    async def test_get_ac_compat_success(self, mock_auth_api, mock_api_response):
        """Test successful AC compatibility info retrieval."""
        api = ACCompatAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        ac_compat_data = {
            "ac_compatible": True,
            "mode": "auto",
            "supported_standards": ["802.11n", "802.11ac", "802.11ax"],
            "legacy_devices_connected": 2,
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(ac_compat_data)
            result = await api.get_ac_compat("network123")

            assert result == ac_compat_data
            mock_get.assert_called_once_with(
                "networks/network123/ac_compat",
                auth_token="test_token",
            )

    async def test_get_ac_compat_legacy_mode(self, mock_auth_api, mock_api_response):
        """Test get_ac_compat when in legacy compatibility mode."""
        api = ACCompatAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        ac_compat_data = {
            "ac_compatible": True,
            "mode": "legacy",
            "supported_standards": ["802.11n"],
            "legacy_devices_connected": 5,
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(ac_compat_data)
            result = await api.get_ac_compat("network123")

            assert result["mode"] == "legacy"
            assert result["legacy_devices_connected"] == 5

    async def test_get_ac_compat_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_ac_compat returns empty dict for missing data."""
        api = ACCompatAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_ac_compat("network123")

            assert result == {}

    async def test_get_ac_compat_not_authenticated(self, mock_auth_api):
        """Test get_ac_compat raises exception when not authenticated."""
        api = ACCompatAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_ac_compat("network123")
