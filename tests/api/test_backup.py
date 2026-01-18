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

    async def test_get_backup_network_success(self, mock_auth_api, mock_api_response):
        """Test successful backup network retrieval."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        backup_data = {
            "enabled": True,
            "status": "standby",
            "phone_number": "+1234567890",
            "last_used": "2024-01-15T10:00:00Z",
            "data_used": 1024000,
            "connection_type": "cellular",
            "provider": "carrier",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(backup_data)
            result = await api.get_backup_network("network123")

            assert result["enabled"] is True
            assert result["status"] == "standby"
            assert result["phone_number"] == "+1234567890"
            assert result["data_used"] == 1024000
            mock_get.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
            )

    async def test_get_backup_network_defaults(self, mock_auth_api, mock_api_response):
        """Test get_backup_network returns defaults for missing data."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {}}
            result = await api.get_backup_network("network123")

            assert result["enabled"] is False
            assert result["status"] == "disabled"
            assert result["phone_number"] is None
            assert result["data_used"] == 0

    async def test_get_backup_network_not_authenticated(self, mock_auth_api):
        """Test get_backup_network raises exception when not authenticated."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_backup_network("network123")


class TestGetBackupStatus:
    """Tests for get_backup_status method."""

    async def test_get_backup_status_success(self, mock_auth_api, mock_api_response):
        """Test successful backup status retrieval."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        status_data = {
            "active": True,
            "connected": True,
            "signal_strength": 75,
            "connection_type": "LTE",
            "using_backup": True,
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(status_data)
            result = await api.get_backup_status("network123")

            assert result["active"] is True
            assert result["connected"] is True
            assert result["signal_strength"] == 75
            assert result["using_backup"] is True
            mock_get.assert_called_once_with(
                "networks/network123/backup/status",
                auth_token="test_token",
            )

    async def test_get_backup_status_defaults(self, mock_auth_api, mock_api_response):
        """Test get_backup_status returns defaults for missing data."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {}}
            result = await api.get_backup_status("network123")

            assert result["active"] is False
            assert result["connected"] is False
            assert result["using_backup"] is False

    async def test_get_backup_status_not_authenticated(self, mock_auth_api):
        """Test get_backup_status raises exception when not authenticated."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_backup_status("network123")


class TestSetBackupNetwork:
    """Tests for set_backup_network method."""

    async def test_set_backup_network_enable(self, mock_auth_api, mock_api_response):
        """Test enabling backup network."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.set_backup_network("network123", enabled=True)

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
                json={"enabled": True},
            )

    async def test_set_backup_network_disable(self, mock_auth_api, mock_api_response):
        """Test disabling backup network."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.set_backup_network("network123", enabled=False)

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
                json={"enabled": False},
            )

    async def test_set_backup_network_failure(self, mock_auth_api, mock_api_response):
        """Test set_backup_network returns false on failure."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 400}}
            result = await api.set_backup_network("network123", enabled=True)

            assert result is False

    async def test_set_backup_network_not_authenticated(self, mock_auth_api):
        """Test set_backup_network raises exception when not authenticated."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.set_backup_network("network123", enabled=True)


class TestConfigureBackupNetwork:
    """Tests for configure_backup_network method."""

    async def test_configure_backup_network_with_enabled(self, mock_auth_api, mock_api_response):
        """Test configuring backup network with enabled setting."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.configure_backup_network("network123", enabled=True)

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
                json={"enabled": True},
            )

    async def test_configure_backup_network_with_phone_number(
        self, mock_auth_api, mock_api_response
    ):
        """Test configuring backup network with phone number."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.configure_backup_network("network123", phone_number="+1234567890")

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
                json={"phone_number": "+1234567890"},
            )

    async def test_configure_backup_network_with_both_settings(
        self, mock_auth_api, mock_api_response
    ):
        """Test configuring backup network with both enabled and phone number."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.configure_backup_network(
                "network123", enabled=True, phone_number="+1234567890"
            )

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/backup",
                auth_token="test_token",
                json={"enabled": True, "phone_number": "+1234567890"},
            )

    async def test_configure_backup_network_no_settings(self, mock_auth_api, mock_api_response):
        """Test configure_backup_network returns false when no settings provided."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        result = await api.configure_backup_network("network123")

        assert result is False

    async def test_configure_backup_network_not_authenticated(self, mock_auth_api):
        """Test configure_backup_network raises exception when not authenticated."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.configure_backup_network("network123", enabled=True)


class TestIsUsingBackup:
    """Tests for is_using_backup method."""

    async def test_is_using_backup_true_via_using_backup(self, mock_auth_api, mock_api_response):
        """Test is_using_backup returns true when using_backup is true."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"using_backup": True, "active": False}}
            result = await api.is_using_backup("network123")

            assert result is True

    async def test_is_using_backup_true_via_active(self, mock_auth_api, mock_api_response):
        """Test is_using_backup returns true when active is true."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"using_backup": False, "active": True}}
            result = await api.is_using_backup("network123")

            assert result is True

    async def test_is_using_backup_false(self, mock_auth_api, mock_api_response):
        """Test is_using_backup returns false when not using backup."""
        api = BackupAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"using_backup": False, "active": False}}
            result = await api.is_using_backup("network123")

            assert result is False
