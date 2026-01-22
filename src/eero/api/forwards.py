"""Port Forwards API for Eero.

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


class ForwardsAPI(AuthenticatedAPI):
    """Port Forwards API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ForwardsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_forwards(self, network_id: str) -> Dict[str, Any]:
        """Get port forwards - returns raw Eero API response.

        Args:
            network_id: ID of the network to get forwards from

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting forwards for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/forwards",
            auth_token=auth_token,
        )

    async def create_forward(self, network_id: str, forward_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a port forward - returns raw Eero API response.

        Args:
            network_id: ID of the network
            forward_data: Port forward data

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Creating forward for network %s: %s", network_id, forward_data)
        return await self.post(
            f"networks/{network_id}/forwards",
            auth_token=auth_token,
            json=forward_data,
        )

    async def delete_forward(self, network_id: str, forward_id: str) -> Dict[str, Any]:
        """Delete a port forward - returns raw Eero API response.

        Args:
            network_id: ID of the network
            forward_id: ID of the forward to delete

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Deleting forward %s for network %s", forward_id, network_id)
        return await self.delete(
            f"networks/{network_id}/forwards/{forward_id}",
            auth_token=auth_token,
        )
