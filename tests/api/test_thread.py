"""Unit tests for the ThreadAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.thread import ThreadAPI
from eero.exceptions import EeroAuthenticationException


class TestThreadAPIInitialization:
    """Tests for ThreadAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test ThreadAPI initializes with auth API."""
        api = ThreadAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetThread:
    """Tests for get_thread method."""

    async def test_get_thread_success(self, mock_auth_api, mock_api_response):
        """Test successful Thread info retrieval."""
        api = ThreadAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        thread_data = {
            "enabled": True,
            "network_name": "MyThreadNetwork",
            "channel": 15,
            "pan_id": "0x1234",
            "extended_pan_id": "dead1234beef5678",
            "devices": [
                {"id": "device1", "name": "Smart Lock"},
                {"id": "device2", "name": "Thermostat"},
            ],
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(thread_data)
            result = await api.get_thread("network123")

            assert result == thread_data
            mock_get.assert_called_once_with(
                "networks/network123/thread",
                auth_token="test_token",
            )

    async def test_get_thread_disabled(self, mock_auth_api, mock_api_response):
        """Test get_thread when Thread is disabled."""
        api = ThreadAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        thread_data = {
            "enabled": False,
            "devices": [],
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(thread_data)
            result = await api.get_thread("network123")

            assert result["enabled"] is False
            assert result["devices"] == []

    async def test_get_thread_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_thread returns empty dict for missing data."""
        api = ThreadAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_thread("network123")

            assert result == {}

    async def test_get_thread_not_authenticated(self, mock_auth_api):
        """Test get_thread raises exception when not authenticated."""
        api = ThreadAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_thread("network123")


class TestUpdateThread:
    """Tests for update_thread method."""

    async def test_update_thread_enable(self, mock_auth_api, mock_api_response):
        """Test enabling Thread network."""
        api = ThreadAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        thread_config = {"enabled": True}

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_thread("network123", thread_config)

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/thread",
                auth_token="test_token",
                json=thread_config,
            )

    async def test_update_thread_disable(self, mock_auth_api, mock_api_response):
        """Test disabling Thread network."""
        api = ThreadAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        thread_config = {"enabled": False}

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_thread("network123", thread_config)

            assert result is True

    async def test_update_thread_change_settings(self, mock_auth_api, mock_api_response):
        """Test updating Thread network settings."""
        api = ThreadAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        thread_config = {
            "network_name": "NewThreadName",
            "channel": 20,
        }

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_thread("network123", thread_config)

            assert result is True

    async def test_update_thread_failure(self, mock_auth_api, mock_api_response):
        """Test update_thread returns false on failure."""
        api = ThreadAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 400}}
            result = await api.update_thread("network123", {})

            assert result is False

    async def test_update_thread_not_authenticated(self, mock_auth_api):
        """Test update_thread raises exception when not authenticated."""
        api = ThreadAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.update_thread("network123", {})
