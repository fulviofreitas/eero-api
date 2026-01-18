"""Burst Reporters API for Eero."""

import logging
from typing import Any, Dict, List

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class BurstReportersAPI(AuthenticatedAPI):
    """Burst Reporters API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BurstReportersAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_burst_reporters(self, network_id: str) -> List[Dict[str, Any]]:
        """Get burst reporters.

        Args:
            network_id: ID of the network to get burst reporters from

        Returns:
            List of burst reporters

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting burst reporters for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/burst_reporters",
            auth_token=auth_token,
        )

        # Handle different response formats
        data = response.get("data", [])
        if isinstance(data, list):
            # Data is directly a list of burst reporters
            reporters_data = data
        elif isinstance(data, dict) and "data" in data:
            # Data is a dictionary with a nested data field
            reporters_data = data.get("data", [])
        else:
            # Fallback to empty list
            reporters_data = []

        return reporters_data

    async def get_burst_reporter(self, network_id: str, reporter_id: str) -> Dict[str, Any]:
        """Get a specific burst reporter.

        Args:
            network_id: ID of the network
            reporter_id: ID of the burst reporter to get

        Returns:
            Burst reporter data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting burst reporter {reporter_id} for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/burst_reporters/{reporter_id}",
            auth_token=auth_token,
        )

        return response.get("data", {})
