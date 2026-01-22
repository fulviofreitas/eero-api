"""DHCP Reservations API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class ReservationsAPI(AuthenticatedAPI):
    """DHCP Reservations API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ReservationsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_reservations(self, network_id: str) -> Dict[str, Any]:
        """Get DHCP reservations - returns raw Eero API response.

        Args:
            network_id: ID of the network to get reservations from

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting reservations for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/reservations",
            auth_token=auth_token,
        )

    async def create_reservation(
        self, network_id: str, reservation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a DHCP reservation - returns raw Eero API response.

        Args:
            network_id: ID of the network
            reservation_data: Reservation data (device_id, ip_address, etc.)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(
            "Creating reservation for network %s: %s", network_id, reservation_data
        )
        return await self.post(
            f"networks/{network_id}/reservations",
            auth_token=auth_token,
            json=reservation_data,
        )

    async def update_reservation(
        self, network_id: str, reservation_id: str, reservation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a DHCP reservation - returns raw Eero API response.

        Args:
            network_id: ID of the network
            reservation_id: ID of the reservation to update
            reservation_data: Updated reservation data

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(
            "Updating reservation %s for network %s: %s",
            reservation_id,
            network_id,
            reservation_data,
        )
        return await self.put(
            f"networks/{network_id}/reservations/{reservation_id}",
            auth_token=auth_token,
            json=reservation_data,
        )

    async def delete_reservation(
        self, network_id: str, reservation_id: str
    ) -> Dict[str, Any]:
        """Delete a DHCP reservation - returns raw Eero API response.

        Args:
            network_id: ID of the network
            reservation_id: ID of the reservation to delete

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(
            "Deleting reservation %s for network %s", reservation_id, network_id
        )
        return await self.delete(
            f"networks/{network_id}/reservations/{reservation_id}",
            auth_token=auth_token,
        )
