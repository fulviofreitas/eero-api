"""Routing API for Eero."""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class RoutingAPI(AuthenticatedAPI):
    """Routing API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the RoutingAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_routing(self, network_id: str) -> Dict[str, Any]:
        """Get network routing information.

        Args:
            network_id: ID of the network to get routing info for

        Returns:
            Routing data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting routing for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/routing",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def update_routing(self, network_id: str, routing_config: Dict[str, Any]) -> bool:
        """Update network routing configuration.

        Args:
            network_id: ID of the network to update routing for
            routing_config: Routing configuration to update

        Returns:
            True if update was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Updating routing for network {network_id}: {routing_config}")

        response = await self.put(
            f"networks/{network_id}/routing",
            auth_token=auth_token,
            json=routing_config,
        )

        return bool(response.get("meta", {}).get("code") == 200)
