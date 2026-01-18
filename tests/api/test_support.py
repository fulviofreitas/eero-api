"""Unit tests for the SupportAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.support import SupportAPI
from eero.exceptions import EeroAuthenticationException


class TestSupportAPIInitialization:
    """Tests for SupportAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test SupportAPI initializes with auth API."""
        api = SupportAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetSupport:
    """Tests for get_support method."""

    async def test_get_support_success(self, mock_auth_api, mock_api_response):
        """Test successful support info retrieval."""
        api = SupportAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        support_data = {
            "support_enabled": True,
            "remote_access": True,
            "contact_email": "support@eero.com",
            "phone_number": "+1-800-555-1234",
            "support_hours": "24/7",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(support_data)
            result = await api.get_support("network123")

            assert result == support_data
            mock_get.assert_called_once_with(
                "networks/network123/support",
                auth_token="test_token",
            )

    async def test_get_support_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_support returns empty dict for missing data."""
        api = SupportAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_support("network123")

            assert result == {}

    async def test_get_support_not_authenticated(self, mock_auth_api):
        """Test get_support raises exception when not authenticated."""
        api = SupportAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_support("network123")


class TestCreateSupportTicket:
    """Tests for create_support_ticket method."""

    async def test_create_support_ticket_success(self, mock_auth_api, mock_api_response):
        """Test successful support ticket creation."""
        api = SupportAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        ticket_data = {
            "subject": "Network connectivity issue",
            "description": "My network keeps disconnecting",
            "category": "connectivity",
        }

        created_ticket = {
            "id": "ticket123",
            "status": "open",
            **ticket_data,
        }

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_api_response(created_ticket)
            result = await api.create_support_ticket("network123", ticket_data)

            assert result == created_ticket
            mock_post.assert_called_once_with(
                "networks/network123/support",
                auth_token="test_token",
                json=ticket_data,
            )

    async def test_create_support_ticket_empty_response(self, mock_auth_api, mock_api_response):
        """Test create_support_ticket returns empty dict on error."""
        api = SupportAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = {}
            result = await api.create_support_ticket("network123", {})

            assert result == {}

    async def test_create_support_ticket_not_authenticated(self, mock_auth_api):
        """Test create_support_ticket raises exception when not authenticated."""
        api = SupportAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.create_support_ticket("network123", {"subject": "Test"})
