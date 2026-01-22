"""Tests for ReservationsAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.reservations import ReservationsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestReservationsAPIInit:
    """Tests for ReservationsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = ReservationsAPI(auth_api)
        assert api._auth_api is auth_api


class TestReservationsAPIGetReservations:
    """Tests for get_reservations method."""

    @pytest.fixture
    def reservations_api(self, mock_session):
        """Create a ReservationsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ReservationsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_reservations_returns_raw_response(self, reservations_api, mock_session):
        """Test get_reservations returns raw response."""
        reservations_data = [{"ip": "192.168.1.100", "mac": "AA:BB:CC:DD:EE:FF"}]
        mock_response = create_mock_response(200, api_success_response(reservations_data))
        mock_session.request.return_value = mock_response

        result = await reservations_api.get_reservations("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_reservations_not_authenticated(self, reservations_api):
        """Test get_reservations raises when not authenticated."""
        reservations_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await reservations_api.get_reservations("network_123")


class TestReservationsAPICreateReservation:
    """Tests for create_reservation method."""

    @pytest.fixture
    def reservations_api(self, mock_session):
        """Create a ReservationsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ReservationsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_create_reservation_returns_raw_response(self, reservations_api, mock_session):
        """Test create_reservation returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        reservation_data = {"ip": "192.168.1.100", "mac": "AA:BB:CC:DD:EE:FF"}
        result = await reservations_api.create_reservation("network_123", reservation_data)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_create_reservation_not_authenticated(self, reservations_api):
        """Test create_reservation raises when not authenticated."""
        reservations_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await reservations_api.create_reservation("network_123", {})


class TestReservationsAPIDeleteReservation:
    """Tests for delete_reservation method."""

    @pytest.fixture
    def reservations_api(self, mock_session):
        """Create a ReservationsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ReservationsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_delete_reservation_returns_raw_response(self, reservations_api, mock_session):
        """Test delete_reservation returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await reservations_api.delete_reservation("network_123", "reservation_id")

        assert "meta" in result
