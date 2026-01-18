"""Settings API for Eero."""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class SettingsAPI(AuthenticatedAPI):
    """Settings API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the SettingsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_settings(self, network_id: str) -> Dict[str, Any]:
        """Get network settings.

        Args:
            network_id: ID of the network to get settings from

        Returns:
            Settings data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting settings for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/settings",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def update_settings(self, network_id: str, settings: Dict[str, Any]) -> bool:
        """Update network settings.

        Args:
            network_id: ID of the network to update settings for
            settings: Settings to update

        Returns:
            True if update was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Updating settings for network {network_id}: {settings}")

        response = await self.put(
            f"networks/{network_id}/settings",
            auth_token=auth_token,
            json=settings,
        )

        return bool(response.get("meta", {}).get("code") == 200)
