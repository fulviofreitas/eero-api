"""OUI Check API for Eero."""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class OUICheckAPI(AuthenticatedAPI):
    """OUI Check API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the OUICheckAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_ouicheck(self, network_id: str) -> Dict[str, Any]:
        """Get OUI check information.

        Args:
            network_id: ID of the network to get OUI check info for

        Returns:
            OUI check data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting OUI check for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/ouicheck",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def check_oui(self, network_id: str, mac_address: str) -> Dict[str, Any]:
        """Check OUI for a specific MAC address.

        Args:
            network_id: ID of the network
            mac_address: MAC address to check

        Returns:
            OUI check result

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Checking OUI for MAC {mac_address} in network {network_id}")

        response = await self.post(
            f"networks/{network_id}/ouicheck",
            auth_token=auth_token,
            json={"mac_address": mac_address},
        )

        return response.get("data", {})
