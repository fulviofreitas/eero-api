"""Unit tests for the UpdatesAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.updates import UpdatesAPI
from eero.exceptions import EeroAuthenticationException


class TestUpdatesAPIInitialization:
    """Tests for UpdatesAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test UpdatesAPI initializes with auth API."""
        api = UpdatesAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetUpdates:
    """Tests for get_updates method."""

    async def test_get_updates_available(self, mock_auth_api, mock_api_response):
        """Test get_updates when updates are available."""
        api = UpdatesAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        updates_data = {
            "available": True,
            "current_version": "6.15.0",
            "new_version": "6.16.0",
            "release_notes": "Bug fixes and performance improvements",
            "size_bytes": 52428800,
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(updates_data)
            result = await api.get_updates("network123")

            assert result == updates_data
            assert result["available"] is True
            mock_get.assert_called_once_with(
                "networks/network123/updates",
                auth_token="test_token",
            )

    async def test_get_updates_no_updates(self, mock_auth_api, mock_api_response):
        """Test get_updates when no updates are available."""
        api = UpdatesAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        updates_data = {
            "available": False,
            "current_version": "6.16.0",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(updates_data)
            result = await api.get_updates("network123")

            assert result["available"] is False
            assert result["current_version"] == "6.16.0"

    async def test_get_updates_in_progress(self, mock_auth_api, mock_api_response):
        """Test get_updates when update is in progress."""
        api = UpdatesAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        updates_data = {
            "available": False,
            "updating": True,
            "progress": 45,
            "current_version": "6.15.0",
            "new_version": "6.16.0",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(updates_data)
            result = await api.get_updates("network123")

            assert result["updating"] is True
            assert result["progress"] == 45

    async def test_get_updates_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_updates returns empty dict for missing data."""
        api = UpdatesAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_updates("network123")

            assert result == {}

    async def test_get_updates_not_authenticated(self, mock_auth_api):
        """Test get_updates raises exception when not authenticated."""
        api = UpdatesAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_updates("network123")


class TestInstallUpdates:
    """Tests for install_updates method."""

    async def test_install_updates_success(self, mock_auth_api, mock_api_response):
        """Test successful update installation."""
        api = UpdatesAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"meta": {"code": 200}}
            result = await api.install_updates("network123")

            assert result is True
            mock_post.assert_called_once_with(
                "networks/network123/updates",
                auth_token="test_token",
                json={},
            )

    async def test_install_updates_failure(self, mock_auth_api, mock_api_response):
        """Test install_updates returns false on failure."""
        api = UpdatesAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {"meta": {"code": 400}}
            result = await api.install_updates("network123")

            assert result is False

    async def test_install_updates_already_up_to_date(self, mock_auth_api, mock_api_response):
        """Test install_updates when already up to date."""
        api = UpdatesAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            # Even if no updates, API might return 200
            mock_post.return_value = {"meta": {"code": 200}}
            result = await api.install_updates("network123")

            assert result is True

    async def test_install_updates_not_authenticated(self, mock_auth_api):
        """Test install_updates raises exception when not authenticated."""
        api = UpdatesAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.install_updates("network123")
