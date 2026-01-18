"""Unit tests for the OUICheckAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.ouicheck import OUICheckAPI
from eero.exceptions import EeroAuthenticationException


class TestOUICheckAPIInitialization:
    """Tests for OUICheckAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test OUICheckAPI initializes with auth API."""
        api = OUICheckAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetOUICheck:
    """Tests for get_ouicheck method."""

    async def test_get_ouicheck_success(self, mock_auth_api, mock_api_response):
        """Test successful OUI check info retrieval."""
        api = OUICheckAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        ouicheck_data = {
            "devices_checked": 15,
            "known_vendors": 12,
            "unknown_vendors": 3,
            "last_check": "2024-01-15T10:00:00Z",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(ouicheck_data)
            result = await api.get_ouicheck("network123")

            assert result == ouicheck_data
            mock_get.assert_called_once_with(
                "networks/network123/ouicheck",
                auth_token="test_token",
            )

    async def test_get_ouicheck_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_ouicheck returns empty dict for missing data."""
        api = OUICheckAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_ouicheck("network123")

            assert result == {}

    async def test_get_ouicheck_not_authenticated(self, mock_auth_api):
        """Test get_ouicheck raises exception when not authenticated."""
        api = OUICheckAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_ouicheck("network123")


class TestCheckOUI:
    """Tests for check_oui method."""

    async def test_check_oui_known_vendor(self, mock_auth_api, mock_api_response):
        """Test check_oui for a known vendor."""
        api = OUICheckAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        oui_result = {
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "vendor": "Apple Inc.",
            "is_known": True,
            "vendor_code": "AABBCC",
        }

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_api_response(oui_result)
            result = await api.check_oui("network123", "AA:BB:CC:DD:EE:FF")

            assert result == oui_result
            assert result["is_known"] is True
            mock_post.assert_called_once_with(
                "networks/network123/ouicheck",
                auth_token="test_token",
                json={"mac_address": "AA:BB:CC:DD:EE:FF"},
            )

    async def test_check_oui_unknown_vendor(self, mock_auth_api, mock_api_response):
        """Test check_oui for an unknown vendor."""
        api = OUICheckAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        oui_result = {
            "mac_address": "11:22:33:44:55:66",
            "vendor": None,
            "is_known": False,
            "vendor_code": "112233",
        }

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_api_response(oui_result)
            result = await api.check_oui("network123", "11:22:33:44:55:66")

            assert result["is_known"] is False
            assert result["vendor"] is None

    async def test_check_oui_empty_response(self, mock_auth_api, mock_api_response):
        """Test check_oui returns empty dict on error."""
        api = OUICheckAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {}
            result = await api.check_oui("network123", "AA:BB:CC:DD:EE:FF")

            assert result == {}

    async def test_check_oui_not_authenticated(self, mock_auth_api):
        """Test check_oui raises exception when not authenticated."""
        api = OUICheckAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.check_oui("network123", "AA:BB:CC:DD:EE:FF")
