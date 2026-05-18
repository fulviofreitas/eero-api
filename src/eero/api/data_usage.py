"""Data Usage API for Eero.

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


class DataUsageAPI(AuthenticatedAPI):
    """Data Usage API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DataUsageAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_data_usage(
        self, network_id: str, payload: Dict[str, Any], resource: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get data usage statistics - returns raw Eero API response.

        Args:
            network_id: ID of the network to get usage from
            payload: JSON payload to send with the GET request
            resource: Optional resource type (e.g., "devices", "eeros")

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        path = f"networks/{network_id}/data_usage"
        if resource:
            path = f"{path}/{resource}"

        _LOGGER.debug("Getting data usage for network %s (resource=%s)", network_id, resource)

        return await self.get(path, auth_token=auth_token, json=payload)
