"""Thread API for Eero."""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class ThreadAPI(AuthenticatedAPI):
    """Thread API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ThreadAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_thread(self, network_id: str) -> Dict[str, Any]:
        """Get network thread information.

        Args:
            network_id: ID of the network to get thread info for

        Returns:
            Thread data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting thread for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/thread",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def update_thread(self, network_id: str, thread_config: Dict[str, Any]) -> bool:
        """Update network thread configuration.

        Args:
            network_id: ID of the network to update thread for
            thread_config: Thread configuration to update

        Returns:
            True if update was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Updating thread for network {network_id}: {thread_config}")

        response = await self.put(
            f"networks/{network_id}/thread",
            auth_token=auth_token,
            json=thread_config,
        )

        return bool(response.get("meta", {}).get("code") == 200)
