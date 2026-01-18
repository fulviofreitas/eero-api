"""Diagnostics API for Eero."""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class DiagnosticsAPI(AuthenticatedAPI):
    """Diagnostics API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DiagnosticsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_diagnostics(self, network_id: str) -> Dict[str, Any]:
        """Get network diagnostics information.

        Args:
            network_id: ID of the network to get diagnostics from

        Returns:
            Diagnostics data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting diagnostics for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/diagnostics",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def run_diagnostics(self, network_id: str) -> Dict[str, Any]:
        """Run network diagnostics.

        Args:
            network_id: ID of the network to run diagnostics on

        Returns:
            Diagnostics results

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Running diagnostics for network {network_id}")

        response = await self.post(
            f"networks/{network_id}/diagnostics",
            auth_token=auth_token,
            json={},
        )

        return response.get("data", {})
