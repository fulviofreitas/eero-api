"""Transfer Stats API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
from typing import Any, Dict, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class TransferAPI(AuthenticatedAPI):
    """Transfer Stats API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the TransferAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_transfer_stats(
        self, network_id: str, device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get transfer statistics - returns raw Eero API response.

        Args:
            network_id: ID of the network to get stats from
            device_id: Optional device ID to get stats for

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        if device_id:
            _LOGGER.debug(
                "Getting transfer stats for device %s in network %s",
                device_id,
                network_id,
            )
            path = f"networks/{network_id}/devices/{device_id}/transfer"
        else:
            _LOGGER.debug("Getting transfer stats for network %s", network_id)
            path = f"networks/{network_id}/transfer"

        return await self.get(path, auth_token=auth_token)
