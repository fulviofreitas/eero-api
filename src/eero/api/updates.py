"""Updates API for Eero."""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class UpdatesAPI(AuthenticatedAPI):
    """Updates API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the UpdatesAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_updates(self, network_id: str) -> Dict[str, Any]:
        """Get available updates for the network.

        Args:
            network_id: ID of the network to get updates for

        Returns:
            Updates data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting updates for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/updates",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def install_updates(self, network_id: str) -> bool:
        """Install available updates for the network.

        Args:
            network_id: ID of the network to install updates for

        Returns:
            True if update installation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Installing updates for network {network_id}")

        response = await self.post(
            f"networks/{network_id}/updates",
            auth_token=auth_token,
            json={},
        )

        return bool(response.get("meta", {}).get("code") == 200)
