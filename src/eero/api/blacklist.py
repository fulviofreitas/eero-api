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

    async def add_to_blacklist(self, network_id: str, mac: str) -> Dict[str, Any]:
        """Add a device to the blacklist - returns raw Eero API response.

        Args:
            network_id: ID of the network
            mac: MAC address of the device to blacklist (colon-separated, e.g. "AA:BB:CC:11:22:33")

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Adding MAC %s to blacklist for network %s", mac, network_id)
        return await self.post(
            f"networks/{network_id}/blacklist",
            auth_token=auth_token,
            json={"mac": mac},
        )

    async def remove_from_blacklist(self, network_id: str, mac_or_device_id: str) -> Dict[str, Any]:
        """Remove a device from the blacklist - returns raw Eero API response.

        Args:
            network_id: ID of the network
            mac_or_device_id: MAC address or device ID to remove from the blacklist.
                Live-verified: Eero's ``device_id`` for a blacklisted entry is the MAC
                address with colons stripped (e.g. ``"AABBCC112233"``), so both the
                raw MAC and the colon-stripped form are accepted as the URL segment.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Removing %s from blacklist for network %s", mac_or_device_id, network_id)
        return await self.delete(
            f"networks/{network_id}/blacklist/{mac_or_device_id}",
            auth_token=auth_token,
        )
