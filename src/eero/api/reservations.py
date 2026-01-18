"""DHCP Reservations API for Eero."""

import logging
from typing import Any, Dict, List

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class ReservationsAPI(AuthenticatedAPI):
    """DHCP Reservations API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ReservationsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_reservations(self, network_id: str) -> List[Dict[str, Any]]:
        """Get DHCP reservations.

        Args:
            network_id: ID of the network to get reservations from

        Returns:
            List of DHCP reservations

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting reservations for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/reservations",
            auth_token=auth_token,
        )

        # Handle different response formats
        data = response.get("data", [])
        if isinstance(data, list):
            # Data is directly a list of reservations
            reservations_data = data
        elif isinstance(data, dict) and "data" in data:
            # Data is a dictionary with a nested data field
            reservations_data = data.get("data", [])
        else:
            # Fallback to empty list
            reservations_data = []

        return reservations_data

    async def create_reservation(
        self, network_id: str, reservation_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a DHCP reservation.

        Args:
            network_id: ID of the network
            reservation_data: Reservation data (device_id, ip_address, etc.)

        Returns:
            Created reservation data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Creating reservation for network {network_id}: {reservation_data}")

        response = await self.post(
            f"networks/{network_id}/reservations",
            auth_token=auth_token,
            json=reservation_data,
        )

        return response.get("data", {})

    async def update_reservation(
        self, network_id: str, reservation_id: str, reservation_data: Dict[str, Any]
    ) -> bool:
        """Update a DHCP reservation.

        Args:
            network_id: ID of the network
            reservation_id: ID of the reservation to update
            reservation_data: Updated reservation data

        Returns:
            True if update was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(
            f"Updating reservation {reservation_id} for network {network_id}: {reservation_data}"
        )

        response = await self.put(
            f"networks/{network_id}/reservations/{reservation_id}",
            auth_token=auth_token,
            json=reservation_data,
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def delete_reservation(self, network_id: str, reservation_id: str) -> bool:
        """Delete a DHCP reservation.

        Args:
            network_id: ID of the network
            reservation_id: ID of the reservation to delete

        Returns:
            True if deletion was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Deleting reservation {reservation_id} for network {network_id}")

        response = await self.delete(
            f"networks/{network_id}/reservations/{reservation_id}",
            auth_token=auth_token,
        )

        return bool(response.get("meta", {}).get("code") == 200)
