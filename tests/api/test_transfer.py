"""Unit tests for the TransferAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.transfer import TransferAPI
from eero.exceptions import EeroAuthenticationException


class TestTransferAPIInitialization:
    """Tests for TransferAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test TransferAPI initializes with auth API."""
        api = TransferAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetTransfer:
    """Tests for get_transfer method."""

    async def test_get_transfer_success(self, mock_auth_api, mock_api_response):
        """Test successful transfer info retrieval."""
        api = TransferAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        transfer_data = {
            "total_download": 1073741824,  # 1 GB
            "total_upload": 536870912,  # 512 MB
            "period": "month",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-31T23:59:59Z",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(transfer_data)
            result = await api.get_transfer("network123")

            assert result == transfer_data
            mock_get.assert_called_once_with(
                "networks/network123/transfer",
                auth_token="test_token",
            )

    async def test_get_transfer_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_transfer returns empty dict for missing data."""
        api = TransferAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_transfer("network123")

            assert result == {}

    async def test_get_transfer_not_authenticated(self, mock_auth_api):
        """Test get_transfer raises exception when not authenticated."""
        api = TransferAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_transfer("network123")


class TestGetTransferStats:
    """Tests for get_transfer_stats method."""

    async def test_get_transfer_stats_network(self, mock_auth_api, mock_api_response):
        """Test get_transfer_stats for entire network."""
        api = TransferAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        stats_data = {
            "total_download": 1073741824,
            "total_upload": 536870912,
            "average_download": 100.5,
            "average_upload": 50.2,
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(stats_data)
            result = await api.get_transfer_stats("network123")

            assert result == stats_data
            mock_get.assert_called_once_with(
                "networks/network123/transfer",
                auth_token="test_token",
            )

    async def test_get_transfer_stats_device(self, mock_auth_api, mock_api_response):
        """Test get_transfer_stats for specific device."""
        api = TransferAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        stats_data = {
            "device_id": "device456",
            "download": 104857600,  # 100 MB
            "upload": 52428800,  # 50 MB
            "last_activity": "2024-01-15T10:00:00Z",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(stats_data)
            result = await api.get_transfer_stats("network123", device_id="device456")

            assert result == stats_data
            mock_get.assert_called_once_with(
                "networks/network123/transfer/device456",
                auth_token="test_token",
            )

    async def test_get_transfer_stats_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_transfer_stats returns empty dict for missing data."""
        api = TransferAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_transfer_stats("network123")

            assert result == {}

    async def test_get_transfer_stats_not_authenticated(self, mock_auth_api):
        """Test get_transfer_stats raises exception when not authenticated."""
        api = TransferAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_transfer_stats("network123")

    async def test_get_transfer_stats_device_not_authenticated(self, mock_auth_api):
        """Test get_transfer_stats with device raises exception when not authenticated."""
        api = TransferAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_transfer_stats("network123", device_id="device456")
