"""Transfer API for Eero."""

import logging
from typing import Any, Dict, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class TransferAPI(AuthenticatedAPI):
    """Transfer API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the TransferAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_transfer(self, network_id: str) -> Dict[str, Any]:
        """Get network transfer information.

        Args:
            network_id: ID of the network to get transfer info for

        Returns:
            Transfer data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting transfer for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/transfer",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def get_transfer_stats(
        self, network_id: str, device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get transfer statistics.

        Args:
            network_id: ID of the network
            device_id: Optional device ID to get stats for

        Returns:
            Transfer statistics

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"networks/{network_id}/transfer"
        if device_id:
            url += f"/{device_id}"

        _LOGGER.debug(f"Getting transfer stats for {url}")

        response = await self.get(
            url,
            auth_token=auth_token,
        )

        return response.get("data", {})
