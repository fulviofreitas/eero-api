"""Unit tests for the BackupAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.backup import BackupAPI
from eero.exceptions import EeroAuthenticationException


class TestBackupAPIInitialization:
    """Tests for BackupAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test BackupAPI initializes with auth API."""
        api = BackupAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetBackupNetwork:
    """Tests for get_backup_network method."""

    async def test_get_backup_network_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test get_backup_network returns raw API response."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        backup_data = {
            "enabled": True,
            "status": "standby",
            "phone_number": "+1234567890",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(backup_data)
            result = await api.get_backup_network("network123")

            assert "meta" in result
            assert "data" in result
            mock_get.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
            )

    async def test_get_backup_network_not_authenticated(self, mock_auth_api):
        """Test get_backup_network raises exception when not authenticated."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_backup_network("network123")


class TestGetBackupStatus:
    """Tests for get_backup_status method."""

    async def test_get_backup_status_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test get_backup_status returns raw API response."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        status_data = {
            "active": True,
            "connected": True,
            "signal_strength": 75,
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(status_data)
            result = await api.get_backup_status("network123")

            assert "meta" in result
            assert "data" in result
            mock_get.assert_called_once_with(
                "networks/network123/backup/status",
                auth_token="test_token",
            )

    async def test_get_backup_status_not_authenticated(self, mock_auth_api):
        """Test get_backup_status raises exception when not authenticated."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_backup_status("network123")


class TestSetBackupNetwork:
    """Tests for set_backup_network method."""

    async def test_set_backup_network_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test set_backup_network returns raw API response."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}, "data": {}}
            result = await api.set_backup_network("network123", enabled=True)

            assert "meta" in result
            mock_put.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
                json={"enabled": True},
            )

    async def test_set_backup_network_not_authenticated(self, mock_auth_api):
        """Test set_backup_network raises exception when not authenticated."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.set_backup_network("network123", enabled=True)


class TestConfigureBackupNetwork:
    """Tests for configure_backup_network method."""

    async def test_configure_backup_network_returns_raw_response(
        self, mock_auth_api, mock_api_response
    ):
        """Test configure_backup_network returns raw API response."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}, "data": {}}
            result = await api.configure_backup_network("network123", enabled=True)

            assert "meta" in result
            mock_put.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
                json={"enabled": True},
            )

    async def test_configure_backup_network_with_phone_number(
        self, mock_auth_api, mock_api_response
    ):
        """Test configure_backup_network with phone number."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}, "data": {}}
            result = await api.configure_backup_network("network123", phone_number="+1234567890")

            assert "meta" in result
            mock_put.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
                json={"phone_number": "+1234567890"},
            )

    async def test_configure_backup_network_no_settings_returns_raw(
        self, mock_auth_api, mock_api_response
    ):
        """Test configure_backup_network with no settings returns raw response."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}, "data": {}}
            result = await api.configure_backup_network("network123")

            # With no settings, method should return raw response
            assert "meta" in result

    async def test_configure_backup_network_not_authenticated(self, mock_auth_api):
        """Test configure_backup_network raises exception when not authenticated."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.configure_backup_network("network123", enabled=True)
