"""Devices API for Eero.

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


class DevicesAPI(AuthenticatedAPI):
    """Devices API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DevicesAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_devices(self, network_id: str) -> Dict[str, Any]:
        """Get list of connected devices - returns raw Eero API response.

        Args:
            network_id: ID of the network to get devices from

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting devices for network %s", network_id)
        return await self.get(f"networks/{network_id}/devices", auth_token=auth_token)

    async def get_device(self, network_id: str, device_id: str) -> Dict[str, Any]:
        """Get information about a specific device - returns raw Eero API response.

        Args:
            network_id: ID of the network the device belongs to
            device_id: ID of the device to get

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting device %s in network %s", device_id, network_id)
        return await self.get(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
        )

    async def set_device_nickname(
        self, network_id: str, device_id: str, nickname: str
    ) -> Dict[str, Any]:
        """Set a nickname for a device - returns raw Eero API response.

        Args:
            network_id: ID of the network the device belongs to
            device_id: ID of the device
            nickname: New nickname for the device

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting nickname for device %s to '%s'", device_id, nickname)

        return await self.put(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
            json={"nickname": nickname},
        )

    async def block_device(self, network_id: str, device_id: str, blocked: bool) -> Dict[str, Any]:
        """Block or unblock a device - returns raw Eero API response.

        Args:
            network_id: ID of the network the device belongs to
            device_id: ID of the device
            blocked: Whether to block or unblock the device

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("%s device %s", "Blocking" if blocked else "Unblocking", device_id)

        return await self.put(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
            json={"blocked": blocked},
        )

    async def pause_device(self, network_id: str, device_id: str, paused: bool) -> Dict[str, Any]:
        """Pause or unpause internet access for a device - returns raw Eero API response.

        This temporarily blocks internet access for the device without removing it
        from the network. The device remains connected but cannot access the internet.

        Args:
            network_id: ID of the network the device belongs to
            device_id: ID of the device
            paused: True to pause internet access, False to resume

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error

        Note:
            This is different from blocking a device:
            - Paused: Device stays connected but has no internet access
            - Blocked: Device is completely removed from the network
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("%s device %s", "Pausing" if paused else "Unpausing", device_id)

        return await self.put(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
            json={"paused": paused},
        )

    async def set_device_priority(
        self,
        network_id: str,
        device_id: str,
        prioritized: bool,
        duration_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Set priority for a device (bandwidth prioritization) - returns raw Eero API response.

        Args:
            network_id: ID of the network
            device_id: ID of the device
            prioritized: True to prioritize, False to remove priority
            duration_minutes: Duration in minutes (0 or None = indefinite)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {"prioritized": prioritized}

        if prioritized and duration_minutes is not None and duration_minutes > 0:
            payload["priority_duration"] = duration_minutes

        _LOGGER.debug(
            "%s device %s%s",
            "Prioritizing" if prioritized else "Deprioritizing",
            device_id,
            f" for {duration_minutes} minutes" if duration_minutes else "",
        )

        return await self.put(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
            json=payload,
        )
