"""Tests for TransferAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.transfer import TransferAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestTransferAPIInit:
    """Tests for TransferAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = TransferAPI(auth_api)
        assert api._auth_api is auth_api


class TestTransferAPIGetTransferStats:
    """Tests for get_transfer_stats method."""

    @pytest.fixture
    def transfer_api(self, mock_session):
        """Create a TransferAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return TransferAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_transfer_stats_returns_raw_response(self, transfer_api, mock_session):
        """Test get_transfer_stats returns raw response."""
        transfer_data = {"total_download": 1073741824, "total_upload": 536870912}
        mock_response = create_mock_response(200, api_success_response(transfer_data))
        mock_session.request.return_value = mock_response

        result = await transfer_api.get_transfer_stats("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_transfer_stats_with_device_returns_raw_response(
        self, transfer_api, mock_session
    ):
        """Test get_transfer_stats with device ID returns raw response."""
        transfer_data = {"device_id": "device456", "download": 104857600}
        mock_response = create_mock_response(200, api_success_response(transfer_data))
        mock_session.request.return_value = mock_response

        result = await transfer_api.get_transfer_stats("network_123", "device456")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_transfer_stats_not_authenticated(self, transfer_api):
        """Test get_transfer_stats raises when not authenticated."""
        transfer_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await transfer_api.get_transfer_stats("network_123")

    @pytest.mark.asyncio
    async def test_get_transfer_stats_uses_transfer_link_template(self, transfer_api, mock_session):
        """Test get_transfer_stats (no device) builds the URL from the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await transfer_api.get_transfer_stats("network_123")

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.2/networks/network_123/transfer")

    @pytest.mark.asyncio
    async def test_get_transfer_stats_prefers_parent_link(self, transfer_api, mock_session):
        """Test get_transfer_stats (no device) uses the network's published transfer link."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"resources": {"transfer": "/2.3/networks/network_123/transfer"}}

        await transfer_api.get_transfer_stats("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/transfer")

    @pytest.mark.asyncio
    async def test_get_transfer_stats_with_device_uses_literal_path(
        self, transfer_api, mock_session
    ):
        """Test get_transfer_stats with a device ID builds the literal per-device path."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await transfer_api.get_transfer_stats("network_123", "device456")

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.2/networks/network_123/devices/device456/transfer")
