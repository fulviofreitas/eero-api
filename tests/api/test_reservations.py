"""Tests for ReservationsAPI module."""

import logging
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
    async def test_create_reservation_warns_uncharacterised_write(
        self, reservations_api, mock_session, caplog
    ):
        """Test create_reservation logs the uncharacterised-write warning once."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING, logger="eero.api.reservations"):
            await reservations_api.create_reservation("network_123", {"ip": "192.168.1.100"})

        assert any("create reservation for network" in m for m in caplog.messages)
        assert not any("network_123" in m for m in caplog.messages)

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

    @pytest.mark.asyncio
    async def test_delete_reservation_warns_uncharacterised_write(
        self, reservations_api, mock_session, caplog
    ):
        """Test delete_reservation logs the uncharacterised-write warning once."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING, logger="eero.api.reservations"):
            await reservations_api.delete_reservation("network_123", "reservation_id")

        assert any("delete reservation for network" in m for m in caplog.messages)
        assert not any("network_123" in m for m in caplog.messages)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("delete_forwards", "expected_params"),
        [
            (True, {"delete_forwards": "true"}),
            (False, {"delete_forwards": "false"}),
            (None, None),
        ],
    )
    async def test_delete_reservation_delete_forwards_query_param(
        self, reservations_api, mock_session, delete_forwards, expected_params
    ):
        """Test the optional delete_forwards query parameter."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        await reservations_api.delete_reservation(
            "network_123", "reservation_id", delete_forwards=delete_forwards
        )

        assert mock_session.request.call_args.kwargs.get("params") == expected_params


class TestReservationsAPIUpdateReservation:
    """Tests for update_reservation method."""

    @pytest.fixture
    def reservations_api(self, mock_session):
        """Create a ReservationsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ReservationsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_update_reservation_from_path_string(self, reservations_api, mock_session):
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        await reservations_api.update_reservation(
            "/2.2/networks/network_123/reservations/r_1", {"description": "printer"}
        )

        method, url = mock_session.request.call_args.args[:2]
        assert method == "PUT"
        assert url == "https://api-user.e2ro.com/2.2/networks/network_123/reservations/r_1"
        assert mock_session.request.call_args.kwargs["json"] == {"description": "printer"}

    @pytest.mark.asyncio
    async def test_update_reservation_from_envelope(self, reservations_api, mock_session):
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response
        envelope = {"url": "/2.3/networks/network_123/reservations/r_1"}

        await reservations_api.update_reservation(envelope, {"public_static_ip": True})

        _, url = mock_session.request.call_args.args[:2]
        assert url == "https://api-user.e2ro.com/2.3/networks/network_123/reservations/r_1"

    @pytest.mark.asyncio
    async def test_update_reservation_warns_uncharacterised_write(
        self, reservations_api, mock_session, caplog
    ):
        """Test update_reservation logs the uncharacterised-write warning once."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        with caplog.at_level(logging.WARNING, logger="eero.api.reservations"):
            await reservations_api.update_reservation(
                "/2.2/networks/network_123/reservations/r_1", {"description": "printer"}
            )

        assert any("not been fully characterised" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_update_reservation_bare_id_without_network_raises(self, reservations_api):
        from eero.exceptions import EeroValidationException

        with pytest.raises(EeroValidationException):
            await reservations_api.update_reservation("r_1", {"description": "x"})

    @pytest.mark.asyncio
    async def test_update_reservation_not_authenticated(self, reservations_api):
        reservations_api._auth_api.get_auth_token = AsyncMock(return_value=None)
        with pytest.raises(EeroAuthenticationException):
            await reservations_api.update_reservation(
                "/2.2/networks/network_123/reservations/r_1", {"description": "x"}
            )
