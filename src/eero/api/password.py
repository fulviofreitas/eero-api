"""Password API for Eero."""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class PasswordAPI(AuthenticatedAPI):
    """Password API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the PasswordAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_password(self, network_id: str) -> Dict[str, Any]:
        """Get network password information.

        Args:
            network_id: ID of the network to get password info for

        Returns:
            Password data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting password for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/password",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def update_password(self, network_id: str, password: str) -> bool:
        """Update network password.

        Args:
            network_id: ID of the network to update password for
            password: New password

        Returns:
            True if password update was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Updating password for network {network_id}")

        response = await self.put(
            f"networks/{network_id}/password",
            auth_token=auth_token,
            json={"password": password},
        )

        return bool(response.get("meta", {}).get("code") == 200)
