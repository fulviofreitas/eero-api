"""Device Blacklist API for Eero."""

import logging
from typing import Any, Dict, List

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class BlacklistAPI(AuthenticatedAPI):
    """Device Blacklist API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BlacklistAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_blacklist(self, network_id: str) -> List[Dict[str, Any]]:
        """Get blacklisted devices.

        Args:
            network_id: ID of the network to get blacklist from

        Returns:
            List of blacklisted devices

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting blacklist for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/blacklist",
            auth_token=auth_token,
        )

        # Handle different response formats
        data = response.get("data", [])
        if isinstance(data, list):
            # Data is directly a list of blacklisted devices
            blacklist_data = data
        elif isinstance(data, dict) and "data" in data:
            # Data is a dictionary with a nested data field
            blacklist_data = data.get("data", [])
        else:
            # Fallback to empty list
            blacklist_data = []

        return blacklist_data

    async def add_to_blacklist(self, network_id: str, device_id: str) -> bool:
        """Add a device to the blacklist.

        Args:
            network_id: ID of the network
            device_id: ID of the device to blacklist

        Returns:
            True if device was added to blacklist successfully

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Adding device {device_id} to blacklist for network {network_id}")

        response = await self.post(
            f"networks/{network_id}/blacklist",
            auth_token=auth_token,
            json={"device_id": device_id},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def remove_from_blacklist(self, network_id: str, device_id: str) -> bool:
        """Remove a device from the blacklist.

        Args:
            network_id: ID of the network
            device_id: ID of the device to remove from blacklist

        Returns:
            True if device was removed from blacklist successfully

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Removing device {device_id} from blacklist for network {network_id}")

        response = await self.delete(
            f"networks/{network_id}/blacklist/{device_id}",
            auth_token=auth_token,
        )

        return bool(response.get("meta", {}).get("code") == 200)
