"""Unit tests for the ReservationsAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.reservations import ReservationsAPI
from eero.exceptions import EeroAuthenticationException


class TestReservationsAPIInitialization:
    """Tests for ReservationsAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test ReservationsAPI initializes with auth API."""
        api = ReservationsAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetReservations:
    """Tests for get_reservations method."""

    async def test_get_reservations_list_response(self, mock_auth_api, mock_api_response):
        """Test get_reservations with list response."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        reservations_data = [
            {
                "id": "reservation1",
                "device_id": "device1",
                "ip_address": "192.168.1.100",
                "mac": "AA:BB:CC:DD:EE:FF",
            },
            {
                "id": "reservation2",
                "device_id": "device2",
                "ip_address": "192.168.1.101",
                "mac": "11:22:33:44:55:66",
            },
        ]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(reservations_data)
            result = await api.get_reservations("network123")

            assert result == reservations_data
            mock_get.assert_called_once_with(
                "networks/network123/reservations",
                auth_token="test_token",
            )

    async def test_get_reservations_nested_data_response(self, mock_auth_api, mock_api_response):
        """Test get_reservations with nested data response."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        reservations_data = [{"id": "reservation1", "ip_address": "192.168.1.100"}]

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": {"data": reservations_data}}
            result = await api.get_reservations("network123")

            assert result == reservations_data

    async def test_get_reservations_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_reservations returns empty list for invalid response format."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {"data": "invalid"}
            result = await api.get_reservations("network123")

            assert result == []

    async def test_get_reservations_not_authenticated(self, mock_auth_api):
        """Test get_reservations raises exception when not authenticated."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_reservations("network123")


class TestCreateReservation:
    """Tests for create_reservation method."""

    async def test_create_reservation_success(self, mock_auth_api, mock_api_response):
        """Test successful DHCP reservation creation."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        reservation_data = {
            "device_id": "device1",
            "ip_address": "192.168.1.100",
        }

        created_reservation = {
            "id": "reservation123",
            **reservation_data,
            "mac": "AA:BB:CC:DD:EE:FF",
        }

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_api_response(created_reservation)
            result = await api.create_reservation("network123", reservation_data)

            assert result == created_reservation
            mock_post.assert_called_once_with(
                "networks/network123/reservations",
                auth_token="test_token",
                json=reservation_data,
            )

    async def test_create_reservation_not_authenticated(self, mock_auth_api):
        """Test create_reservation raises exception when not authenticated."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.create_reservation("network123", {"ip_address": "192.168.1.100"})


class TestUpdateReservation:
    """Tests for update_reservation method."""

    async def test_update_reservation_success(self, mock_auth_api, mock_api_response):
        """Test successful DHCP reservation update."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        reservation_data = {"ip_address": "192.168.1.150"}

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 200}}
            result = await api.update_reservation("network123", "reservation456", reservation_data)

            assert result is True
            mock_put.assert_called_once_with(
                "networks/network123/reservations/reservation456",
                auth_token="test_token",
                json=reservation_data,
            )

    async def test_update_reservation_failure(self, mock_auth_api, mock_api_response):
        """Test update_reservation returns false on failure."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "put", new_callable=AsyncMock) as mock_put:
            mock_put.return_value = {"meta": {"code": 400}}
            result = await api.update_reservation("network123", "reservation456", {})

            assert result is False

    async def test_update_reservation_not_authenticated(self, mock_auth_api):
        """Test update_reservation raises exception when not authenticated."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.update_reservation("network123", "reservation456", {})


class TestDeleteReservation:
    """Tests for delete_reservation method."""

    async def test_delete_reservation_success(self, mock_auth_api, mock_api_response):
        """Test successful DHCP reservation deletion."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {"meta": {"code": 200}}
            result = await api.delete_reservation("network123", "reservation456")

            assert result is True
            mock_delete.assert_called_once_with(
                "networks/network123/reservations/reservation456",
                auth_token="test_token",
            )

    async def test_delete_reservation_failure(self, mock_auth_api, mock_api_response):
        """Test delete_reservation returns false on failure."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.return_value = {"meta": {"code": 404}}
            result = await api.delete_reservation("network123", "reservation456")

            assert result is False

    async def test_delete_reservation_not_authenticated(self, mock_auth_api):
        """Test delete_reservation raises exception when not authenticated."""
        api = ReservationsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.delete_reservation("network123", "reservation456")
