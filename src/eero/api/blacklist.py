"""Device Blacklist API for Eero.

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


class BlacklistAPI(AuthenticatedAPI):
    """Device Blacklist API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BlacklistAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_blacklist(self, network_id: str) -> Dict[str, Any]:
        """Get blacklisted devices - returns raw Eero API response.

        Args:
            network_id: ID of the network to get blacklist from

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting blacklist for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/blacklist",
            auth_token=auth_token,
        )

    async def add_to_blacklist(self, network_id: str, device_id: str) -> Dict[str, Any]:
        """Add a device to the blacklist - returns raw Eero API response.

        Args:
            network_id: ID of the network
            device_id: ID of the device to blacklist

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Adding device %s to blacklist for network %s", device_id, network_id)
        return await self.post(
            f"networks/{network_id}/blacklist",
            auth_token=auth_token,
            json={"device_id": device_id},
        )

    async def remove_from_blacklist(self, network_id: str, device_id: str) -> Dict[str, Any]:
        """Remove a device from the blacklist - returns raw Eero API response.

        Args:
            network_id: ID of the network
            device_id: ID of the device to remove from blacklist

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Removing device %s from blacklist for network %s", device_id, network_id)
        return await self.delete(
            f"networks/{network_id}/blacklist/{device_id}",
            auth_token=auth_token,
        )
