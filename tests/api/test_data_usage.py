"""Tests for DataUsageAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.data_usage import DataUsageAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestDataUsageAPIInit:
    """Tests for DataUsageAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = DataUsageAPI(auth_api)
        assert api._auth_api is auth_api


class TestDataUsageAPIGetDataUsage:
    """Tests for get_data_usage method."""

    @pytest.fixture
    def data_usage_api(self, mock_session):
        """Create a DataUsageAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return DataUsageAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_data_usage_network_level(self, data_usage_api, mock_session):
        """Test get_data_usage returns raw response for network-level usage."""
        usage_data = {
            "download": 1024000,
            "upload": 512000,
        }
        mock_response = create_mock_response(200, api_success_response(usage_data))
        mock_session.request.return_value = mock_response

        payload = {"timezone": "America/New_York"}
        result = await data_usage_api.get_data_usage("network_123", payload)

        assert "meta" in result
        assert "data" in result
        # Verify the correct URL was called without resource suffix
        call_args = mock_session.request.call_args
        assert "networks/network_123/data_usage" in call_args[0][1]
        assert call_args[1]["json"] == payload

    @pytest.mark.asyncio
    async def test_get_data_usage_devices_resource(self, data_usage_api, mock_session):
        """Test get_data_usage with resource='devices'."""
        usage_data = [{"device_id": "dev_1", "download": 100}]
        mock_response = create_mock_response(200, api_success_response(usage_data))
        mock_session.request.return_value = mock_response

        payload = {"timezone": "America/New_York"}
        result = await data_usage_api.get_data_usage("network_123", payload, resource="devices")

        assert "meta" in result
        assert "data" in result
        call_args = mock_session.request.call_args
        assert "networks/network_123/data_usage/devices" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_data_usage_eeros_resource(self, data_usage_api, mock_session):
        """Test get_data_usage with resource='eeros'."""
        usage_data = [{"eero_id": "eero_1", "download": 200}]
        mock_response = create_mock_response(200, api_success_response(usage_data))
        mock_session.request.return_value = mock_response

        payload = {"timezone": "America/New_York"}
        result = await data_usage_api.get_data_usage("network_123", payload, resource="eeros")

        assert "meta" in result
        assert "data" in result
        call_args = mock_session.request.call_args
        assert "networks/network_123/data_usage/eeros" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_data_usage_not_authenticated(self, data_usage_api):
        """Test get_data_usage raises when not authenticated."""
        data_usage_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await data_usage_api.get_data_usage("network_123", {})

    @pytest.mark.asyncio
    async def test_get_data_usage_sends_json_payload(self, data_usage_api, mock_session):
        """Test that payload is sent as json kwarg on GET request."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        payload = {"timezone": "UTC", "period": "day"}
        await data_usage_api.get_data_usage("network_123", payload)

        call_args = mock_session.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[1]["json"] == payload
