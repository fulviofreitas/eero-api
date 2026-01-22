"""Support API for Eero.

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


class SupportAPI(AuthenticatedAPI):
    """Support API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the SupportAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_support(self, network_id: str) -> Dict[str, Any]:
        """Get support information - returns raw Eero API response.

        Args:
            network_id: ID of the network to get support info from

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting support info for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/support",
            auth_token=auth_token,
        )

    async def request_support(
        self, network_id: str, request_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Request support - returns raw Eero API response.

        Args:
            network_id: ID of the network
            request_data: Support request data

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Requesting support for network %s", network_id)
        return await self.post(
            f"networks/{network_id}/support",
            auth_token=auth_token,
            json=request_data,
        )
