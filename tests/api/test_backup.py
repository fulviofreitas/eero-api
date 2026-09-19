"""Tests for BackupAPI module.

Tests cover:
- Getting backup internet configuration, cellular backup usage, and
  cellular backup events (raw responses, literal paths)
- Setting backup internet (JSON write, uncharacterised-write warning)
- id/path/URL polymorphism
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.backup import BackupAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def backup_api(mock_session):
    """Create a BackupAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return BackupAPI(auth_api)


class TestBackupAPIInit:
    """Tests for BackupAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = BackupAPI(auth_api)

        assert api._auth_api is auth_api


class TestBackupAPIGetBackupInternet:
    """Tests for get_backup_internet method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "network_id,expected_suffix",
        [
            ("network_123", "/2.2/networks/network_123/backupinternet"),
            (
                "https://api-user.e2ro.com/2.2/networks/network_123",
                "/2.2/networks/network_123/backupinternet",
            ),
        ],
    )
    async def test_get_backup_internet_accepts_id_or_url(
        self, backup_api, mock_session, network_id, expected_suffix
    ):
        """Test get_backup_internet accepts a bare id or an absolute URL."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"enabled": False})
        )

        result = await backup_api.get_backup_internet(network_id)

        assert result["data"]["enabled"] is False
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith(expected_suffix)

    @pytest.mark.asyncio
    async def test_get_backup_internet_not_authenticated(self, backup_api):
        """Test get_backup_internet raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.get_backup_internet("network_123")


class TestBackupAPISetBackupInternet:
    """Tests for set_backup_internet method."""

    @pytest.mark.asyncio
    async def test_set_backup_internet_sends_json_payload(self, backup_api, mock_session, caplog):
        """Test set_backup_internet PUTs {"backup_internet_enabled": bool} and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await backup_api.set_backup_internet("network_123", True)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/backupinternet")
        assert call_args.kwargs["json"] == {"backup_internet_enabled": True}
        assert any("set backup internet for network" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_backup_internet_not_authenticated(self, backup_api):
        """Test set_backup_internet raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.set_backup_internet("network_123", True)


class TestBackupAPICellularUsage:
    """Tests for get_cellular_backup_usage method."""

    @pytest.mark.asyncio
    async def test_get_cellular_backup_usage_returns_raw_response(self, backup_api, mock_session):
        """Test get_cellular_backup_usage GETs the literal usage path."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"bytes_used": 1024})
        )

        result = await backup_api.get_cellular_backup_usage("network_123")

        assert result["data"]["bytes_used"] == 1024
        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.2/networks/network_123/cellular_backup_usage")

    @pytest.mark.asyncio
    async def test_get_cellular_backup_usage_not_authenticated(self, backup_api):
        """Test get_cellular_backup_usage raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.get_cellular_backup_usage("network_123")


class TestBackupAPICellularEvents:
    """Tests for get_cellular_backup_events method."""

    @pytest.mark.asyncio
    async def test_get_cellular_backup_events_returns_raw_response(self, backup_api, mock_session):
        """Test get_cellular_backup_events GETs the literal events path."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"events": []})
        )

        result = await backup_api.get_cellular_backup_events("network_123")

        assert result["data"]["events"] == []
        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.2/networks/network_123/cellular_backup_events")

    @pytest.mark.asyncio
    async def test_get_cellular_backup_events_not_authenticated(self, backup_api):
        """Test get_cellular_backup_events raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.get_cellular_backup_events("network_123")
