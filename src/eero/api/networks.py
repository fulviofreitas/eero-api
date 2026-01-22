"""Networks API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
from typing import Any, Dict, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class NetworksAPI(AuthenticatedAPI):
    """Networks API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the NetworksAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_networks(self) -> Dict[str, Any]:
        """Get list of networks - returns raw Eero API response.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
            The data field may contain "networks" list or other formats.

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting networks")
        return await self.get("networks", auth_token=auth_token)

    async def get_network(self, network_id: str) -> Dict[str, Any]:
        """Get network information - returns raw Eero API response.

        Args:
            network_id: ID of the network to get

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting network %s", network_id)
        return await self.get(f"networks/{network_id}", auth_token=auth_token)

    async def set_guest_network(
        self,
        network_id: str,
        enabled: bool,
        name: Optional[str] = None,
        password: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enable or disable the guest network - returns raw Eero API response.

        Args:
            network_id: ID of the network
            enabled: Whether to enable or disable the guest network
            name: Optional new name for the guest network
            password: Optional new password for the guest network

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {"enabled": enabled}

        if name is not None:
            payload["name"] = name

        if password is not None:
            payload["password"] = password

        return await self.put(
            f"networks/{network_id}/guest_network",
            auth_token=auth_token,
            json=payload,
        )

    async def run_speed_test(self, network_id: str) -> Dict[str, Any]:
        """Run a speed test on the network - returns raw Eero API response.

        Args:
            network_id: ID of the network to run the speed test on

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        return await self.post(
            f"networks/{network_id}/speedtest",
            auth_token=auth_token,
            json={},
        )

    async def reboot_network(self, network_id: str) -> Dict[str, Any]:
        """Reboot the entire network - returns raw Eero API response.

        Args:
            network_id: ID of the network to reboot

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Rebooting network %s", network_id)

        return await self.post(
            f"networks/{network_id}/reboot",
            auth_token=auth_token,
            json={},
        )

    async def get_premium_status(self, network_id: str) -> Dict[str, Any]:
        """Get Eero Plus/Eero Secure subscription status - returns raw Eero API response.

        This returns the full network data which includes premium status information.
        Downstream clients should extract premium_status, eero_plus, or premium_dns fields.

        Args:
            network_id: ID of the network to check

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting premium status for network %s", network_id)
        return await self.get(f"networks/{network_id}", auth_token=auth_token)

    async def set_network_name(self, network_id: str, name: str) -> Dict[str, Any]:
        """Set the network name (SSID) - returns raw Eero API response.

        Note: This may require a network restart to take effect.

        Args:
            network_id: ID of the network
            name: New network name

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting network name for %s to '%s'", network_id, name)

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"name": name},
        )
