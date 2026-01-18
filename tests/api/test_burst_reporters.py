"""Unit tests for the BurstReportersAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.burst_reporters import BurstReportersAPI
from eero.exceptions import EeroAuthenticationException


class TestBurstReportersAPIInitialization:
    """Tests for BurstReportersAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test BurstReportersAPI initializes with auth API."""
        api = BurstReportersAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetBurstReporters:
    """Tests for get_burst_reporters method."""

    async def test_get_burst_reporters_list_response(self, mock_auth_api, mock_api_response):
        """Test get_burst_reporters with list response."""
        api = BurstReportersAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        reporters_data = [
            {"id": "reporter1", "name": "SpeedTest Reporter", "type": "speed"},
            {"id": "reporter2", "name": "Usage Reporter", "type": "usage"},
        ]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(reporters_data)
            result = await api.get_burst_reporters("network123")

            assert result == reporters_data
            mock_get.assert_called_once_with(
                "networks/network123/burst_reporters",
                auth_token="test_token",
            )

    async def test_get_burst_reporters_nested_data_response(self, mock_auth_api, mock_api_response):
        """Test get_burst_reporters with nested data response."""
        api = BurstReportersAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        reporters_data = [{"id": "reporter1", "name": "SpeedTest Reporter"}]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"data": reporters_data}}
            result = await api.get_burst_reporters("network123")

            assert result == reporters_data

    async def test_get_burst_reporters_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_burst_reporters returns empty list for invalid response."""
        api = BurstReportersAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": "invalid"}
            result = await api.get_burst_reporters("network123")

            assert result == []

    async def test_get_burst_reporters_not_authenticated(self, mock_auth_api):
        """Test get_burst_reporters raises exception when not authenticated."""
        api = BurstReportersAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_burst_reporters("network123")


class TestGetBurstReporter:
    """Tests for get_burst_reporter method."""

    async def test_get_burst_reporter_success(self, mock_auth_api, mock_api_response):
        """Test successful specific burst reporter retrieval."""
        api = BurstReportersAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        reporter_data = {
            "id": "reporter123",
            "name": "SpeedTest Reporter",
            "type": "speed",
            "last_report": "2024-01-15T10:00:00Z",
            "results": {"download": 100.5, "upload": 50.2},
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(reporter_data)
            result = await api.get_burst_reporter("network123", "reporter123")

            assert result == reporter_data
            mock_get.assert_called_once_with(
                "networks/network123/burst_reporters/reporter123",
                auth_token="test_token",
            )

    async def test_get_burst_reporter_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_burst_reporter returns empty dict for missing reporter."""
        api = BurstReportersAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_burst_reporter("network123", "nonexistent")

            assert result == {}

    async def test_get_burst_reporter_not_authenticated(self, mock_auth_api):
        """Test get_burst_reporter raises exception when not authenticated."""
        api = BurstReportersAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_burst_reporter("network123", "reporter123")
