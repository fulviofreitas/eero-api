"""Tests for BackupAccessPointsAPI module.

Tests cover:
- list: verified read, parent-link preference
- add: JSON body (ssid/password/uuid), password never logged
- update: only-given-fields JSON body
- delete_backup_access_point: DELETE
- rearrange: JSON body (rearranged_ids)
- discover_ssids: verified read
- start_ssid_discovery / connectivity_check: empty-string-body POSTs
- The uncharacterised-write warning on every unverified write
- Not-authenticated errors on every method
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.backup_access_points import BackupAccessPointsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def backup_api(mock_session):
    """Create a BackupAccessPointsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return BackupAccessPointsAPI(auth_api)


class TestBackupAccessPointsAPIInit:
    """Tests for BackupAccessPointsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = BackupAccessPointsAPI(auth_api)

        assert api._auth_api is auth_api


class TestBackupAccessPointsAPIList:
    """Tests for list method."""

    @pytest.mark.asyncio
    async def test_list_returns_raw_response(self, backup_api, mock_session):
        """Test list GETs the backup_access_points sub-resource."""
        expected = {"backup_access_points": []}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(expected)
        )

        result = await backup_api.list("network_123")

        assert result["data"] == expected
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/backup_access_points")

    @pytest.mark.asyncio
    async def test_list_prefers_parent_link(self, backup_api, mock_session):
        """Test list uses the published link over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {
            "resources": {"backup_access_points": "/2.3/networks/network_123/backup_access_points"}
        }

        await backup_api.list("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/backup_access_points")

    @pytest.mark.asyncio
    async def test_list_not_authenticated(self, backup_api):
        """Test list raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.list("network_123")


class TestBackupAccessPointsAPIAdd:
    """Tests for add method."""

    @pytest.mark.asyncio
    async def test_add_sends_json(self, backup_api, mock_session, caplog):
        """Test add POSTs ssid/password/uuid and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await backup_api.add(
                "network_123",
                ssid="example-ssid",
                password="example-password",
                uuid="uuid-placeholder",
            )

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/networks/network_123/backup_access_points")
        assert call_args.kwargs["json"] == {
            "ssid": "example-ssid",
            "password": "example-password",
            "uuid": "uuid-placeholder",
        }
        assert any("add backup access point for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_add_omits_uuid_when_not_given(self, backup_api, mock_session):
        """Test add omits uuid from the body when not supplied."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await backup_api.add("network_123", ssid="example-ssid", password="example-password")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {
            "ssid": "example-ssid",
            "password": "example-password",
        }

    @pytest.mark.asyncio
    async def test_add_never_logs_password(self, backup_api, mock_session, caplog):
        """Test add never logs the plaintext password value."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.DEBUG):
            await backup_api.add("network_123", ssid="example-ssid", password="super-secret-value")

        assert not any("super-secret-value" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_add_not_authenticated(self, backup_api):
        """Test add raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.add("network_123", ssid="example-ssid", password="p")


class TestBackupAccessPointsAPIUpdate:
    """Tests for update method."""

    @pytest.mark.asyncio
    async def test_update_sends_only_given_fields(self, backup_api, mock_session, caplog):
        """Test update PUTs only the supplied fields and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await backup_api.update("network_123", "backup_001", enabled=False)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/backup_access_points/backup_001"
        )
        assert call_args.kwargs["json"] == {"enabled": False}
        assert any(
            "update backup access point backup_001 for network" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_update_never_logs_password(self, backup_api, mock_session, caplog):
        """Test update never logs the plaintext password value."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.DEBUG):
            await backup_api.update("network_123", "backup_001", password="super-secret-value")

        assert not any("super-secret-value" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_update_not_authenticated(self, backup_api):
        """Test update raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.update("network_123", "backup_001", enabled=True)


class TestBackupAccessPointsAPIDelete:
    """Tests for delete_backup_access_point method."""

    @pytest.mark.asyncio
    async def test_delete_sends_delete(self, backup_api, mock_session, caplog):
        """Test delete_backup_access_point DELETEs the sub-resource and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await backup_api.delete_backup_access_point("network_123", "backup_001")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "DELETE"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/backup_access_points/backup_001"
        )
        assert any(
            "delete backup access point backup_001 for network" in message
            for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_delete_not_authenticated(self, backup_api):
        """Test delete_backup_access_point raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.delete_backup_access_point("network_123", "backup_001")


class TestBackupAccessPointsAPIRearrange:
    """Tests for rearrange method."""

    @pytest.mark.asyncio
    async def test_rearrange_sends_json(self, backup_api, mock_session, caplog):
        """Test rearrange POSTs the reordered IDs and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await backup_api.rearrange("network_123", ["backup_002", "backup_001"])

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/backup_access_points/rearrange"
        )
        assert call_args.kwargs["json"] == {"rearranged_ids": ["backup_002", "backup_001"]}
        assert any(
            "rearrange backup access points for network" in message for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_rearrange_not_authenticated(self, backup_api):
        """Test rearrange raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.rearrange("network_123", [])


class TestBackupAccessPointsAPIDiscoverSsids:
    """Tests for discover_ssids method."""

    @pytest.mark.asyncio
    async def test_discover_ssids_returns_raw_response(self, backup_api, mock_session):
        """Test discover_ssids GETs the ssid_discovery sub-resource."""
        expected = {"discovered_ssids": []}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(expected)
        )

        result = await backup_api.discover_ssids("network_123")

        assert result["data"] == expected
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/backup_access_points/ssid_discovery"
        )

    @pytest.mark.asyncio
    async def test_discover_ssids_not_authenticated(self, backup_api):
        """Test discover_ssids raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.discover_ssids("network_123")


class TestBackupAccessPointsAPIStartSsidDiscovery:
    """Tests for start_ssid_discovery method."""

    @pytest.mark.asyncio
    async def test_start_ssid_discovery_sends_empty_string_body(
        self, backup_api, mock_session, caplog
    ):
        """Test start_ssid_discovery POSTs the two-character empty-JSON-string body."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await backup_api.start_ssid_discovery("network_123")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/backup_access_points/ssid_discovery"
        )
        assert call_args.kwargs["data"] == '""'
        assert any("start SSID discovery for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_start_ssid_discovery_not_authenticated(self, backup_api):
        """Test start_ssid_discovery raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.start_ssid_discovery("network_123")


class TestBackupAccessPointsAPIConnectivityCheck:
    """Tests for connectivity_check method."""

    @pytest.mark.asyncio
    async def test_connectivity_check_sends_empty_string_body(
        self, backup_api, mock_session, caplog
    ):
        """Test connectivity_check POSTs the two-character empty-JSON-string body."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            await backup_api.connectivity_check("network_123")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith(
            "/2.2/networks/network_123/backup_access_points/connectivity_check"
        )
        assert call_args.kwargs["data"] == '""'
        assert any(
            "start backup connectivity check for network" in message for message in caplog.messages
        )

    @pytest.mark.asyncio
    async def test_connectivity_check_not_authenticated(self, backup_api):
        """Test connectivity_check raises when not authenticated."""
        backup_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await backup_api.connectivity_check("network_123")
