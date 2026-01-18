"""Unit tests for the ForwardsAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.forwards import ForwardsAPI
from eero.exceptions import EeroAuthenticationException


class TestForwardsAPIInitialization:
    """Tests for ForwardsAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test ForwardsAPI initializes with auth API."""
        api = ForwardsAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetForwards:
    """Tests for get_forwards method."""

    async def test_get_forwards_list_response(self, mock_auth_api, mock_api_response):
        """Test get_forwards with list response."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        forwards_data = [
            {
                "id": "forward1",
                "external_port": 8080,
                "internal_port": 80,
                "device_id": "device1",
                "protocol": "tcp",
            },
            {
                "id": "forward2",
                "external_port": 443,
                "internal_port": 443,
                "device_id": "device2",
                "protocol": "tcp",
            },
        ]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(forwards_data)
            result = await api.get_forwards("network123")

            assert result == forwards_data
            mock_get.assert_called_once_with(
                "networks/network123/forwards",
                auth_token="test_token",
            )

    async def test_get_forwards_nested_data_response(self, mock_auth_api, mock_api_response):
        """Test get_forwards with nested data response."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        forwards_data = [{"id": "forward1", "external_port": 8080}]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"data": forwards_data}}
            result = await api.get_forwards("network123")

            assert result == forwards_data

    async def test_get_forwards_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_forwards returns empty list for invalid response format."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": "invalid"}
            result = await api.get_forwards("network123")

            assert result == []

    async def test_get_forwards_not_authenticated(self, mock_auth_api):
        """Test get_forwards raises exception when not authenticated."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_forwards("network123")


class TestCreateForward:
    """Tests for create_forward method."""

    async def test_create_forward_success(self, mock_auth_api, mock_api_response):
        """Test successful port forward creation."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        forward_data = {
            "external_port": 8080,
            "internal_port": 80,
            "device_id": "device1",
            "protocol": "tcp",
        }

        created_forward = {
            "id": "forward123",
            **forward_data,
        }

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_api_response(created_forward)
            result = await api.create_forward("network123", forward_data)

            assert result == created_forward
            mock_post.assert_called_once_with(
                "networks/network123/forwards",
                auth_token="test_token",
                json=forward_data,
            )

    async def test_create_forward_not_authenticated(self, mock_auth_api):
        """Test create_forward raises exception when not authenticated."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.create_forward("network123", {"external_port": 8080})


class TestUpdateForward:
    """Tests for update_forward method."""

    async def test_update_forward_success(self, mock_auth_api, mock_api_response):
        """Test successful port forward update."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        forward_data = {"external_port": 9090}

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_forward("network123", "forward456", forward_data)

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/forwards/forward456",
                auth_token="test_token",
                json=forward_data,
            )

    async def test_update_forward_failure(self, mock_auth_api, mock_api_response):
        """Test update_forward returns false on failure."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 400}}
            result = await api.update_forward("network123", "forward456", {})

            assert result is False

    async def test_update_forward_not_authenticated(self, mock_auth_api):
        """Test update_forward raises exception when not authenticated."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.update_forward("network123", "forward456", {})


class TestDeleteForward:
    """Tests for delete_forward method."""

    async def test_delete_forward_success(self, mock_auth_api, mock_api_response):
        """Test successful port forward deletion."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {"meta": {"code": 200}}
            result = await api.delete_forward("network123", "forward456")

            assert result is True
            mock_delete.assert_called_once_with(
                "networks/network123/forwards/forward456",
                auth_token="test_token",
            )

    async def test_delete_forward_failure(self, mock_auth_api, mock_api_response):
        """Test delete_forward returns false on failure."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {"meta": {"code": 404}}
            result = await api.delete_forward("network123", "forward456")

            assert result is False

    async def test_delete_forward_not_authenticated(self, mock_auth_api):
        """Test delete_forward raises exception when not authenticated."""
        api = ForwardsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.delete_forward("network123", "forward456")
