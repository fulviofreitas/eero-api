"""Activity API for Eero (Eero Plus feature).

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


class ActivityAPI(AuthenticatedAPI):
    """Activity API for Eero.

    Note: Activity data requires an active Eero Plus/Eero Secure subscription.
    API calls may return empty data or errors for non-premium accounts.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ActivityAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_activity(self, network_id: str) -> Dict[str, Any]:
        """Get network activity summary - returns raw Eero API response.

        Args:
            network_id: ID of the network to get activity from

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error (may occur for non-premium)
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting activity for network %s", network_id)
        return await self.get(f"networks/{network_id}/activity", auth_token=auth_token)

    async def get_activity_clients(self, network_id: str) -> Dict[str, Any]:
        """Get per-client activity data - returns raw Eero API response.

        Args:
            network_id: ID of the network to get client activity from

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting client activity for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/activity/clients",
            auth_token=auth_token,
        )

    async def get_activity_for_device(
        self, network_id: str, device_id: str
    ) -> Dict[str, Any]:
        """Get activity data for a specific device - returns raw Eero API response.

        Args:
            network_id: ID of the network
            device_id: ID of the device to get activity for

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting activity for device %s in network %s", device_id, network_id)
        return await self.get(
            f"networks/{network_id}/activity/{device_id}",
            auth_token=auth_token,
        )

    async def get_activity_history(
        self,
        network_id: str,
        period: str = "day",
    ) -> Dict[str, Any]:
        """Get historical activity data - returns raw Eero API response.

        Args:
            network_id: ID of the network
            period: Time period - "hour", "day", "week", or "month"

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        valid_periods = ["hour", "day", "week", "month"]
        if period not in valid_periods:
            _LOGGER.warning("Invalid period '%s', defaulting to 'day'", period)
            period = "day"

        _LOGGER.debug(
            "Getting activity history for network %s (period: %s)", network_id, period
        )
        return await self.get(
            f"networks/{network_id}/activity/history",
            auth_token=auth_token,
            params={"period": period},
        )

    async def get_activity_categories(self, network_id: str) -> Dict[str, Any]:
        """Get activity data grouped by category - returns raw Eero API response.

        Args:
            network_id: ID of the network

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting activity categories for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/activity/categories",
            auth_token=auth_token,
        )
