"""Devices API for Eero."""

import logging
from typing import Any, Dict, List, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class DevicesAPI(AuthenticatedAPI):
    """Devices API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DevicesAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_devices(self, network_id: str) -> List[Dict[str, Any]]:
        """Get list of connected devices.

        Args:
            network_id: ID of the network to get devices from

        Returns:
            List of device data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting devices for network {network_id}")

        # Simplified path construction
        response = await self.get(
            f"networks/{network_id}/devices",
            auth_token=auth_token,
        )

        # Handle different response formats
        data = response.get("data", [])
        if isinstance(data, list):
            # Data is directly a list of devices
            devices_data = data
        elif isinstance(data, dict) and "data" in data:
            # Data is a dictionary with a nested data field
            devices_data = data.get("data", [])
        else:
            # Fallback to empty list
            devices_data = []

        _LOGGER.debug(f"Found {len(devices_data)} devices")

        return devices_data

    async def get_device(self, network_id: str, device_id: str) -> Dict[str, Any]:
        """Get information about a specific device.

        Args:
            network_id: ID of the network the device belongs to
            device_id: ID of the device to get

        Returns:
            Device data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting device {device_id} in network {network_id}")

        # Simplified path construction
        response = await self.get(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def set_device_nickname(self, network_id: str, device_id: str, nickname: str) -> bool:
        """Set a nickname for a device.

        Args:
            network_id: ID of the network the device belongs to
            device_id: ID of the device
            nickname: New nickname for the device

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Setting nickname for device {device_id} to '{nickname}'")

        # Simplified path construction
        response = await self.put(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
            json={"nickname": nickname},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def block_device(self, network_id: str, device_id: str, blocked: bool) -> bool:
        """Block or unblock a device.

        Args:
            network_id: ID of the network the device belongs to
            device_id: ID of the device
            blocked: Whether to block or unblock the device

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"{'Blocking' if blocked else 'Unblocking'} device {device_id}")

        # Simplified path construction
        response = await self.put(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
            json={"blocked": blocked},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    # ==================== Device Pause ====================

    async def pause_device(self, network_id: str, device_id: str, paused: bool) -> bool:
        """Pause or unpause internet access for a device.

        This temporarily blocks internet access for the device without removing it
        from the network. The device remains connected but cannot access the internet.

        Args:
            network_id: ID of the network the device belongs to
            device_id: ID of the device
            paused: True to pause internet access, False to resume

        Returns:
            True if the operation was successful

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

        _LOGGER.debug(f"{'Pausing' if paused else 'Unpausing'} device {device_id}")

        response = await self.put(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
            json={"paused": paused},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def get_paused_devices(self, network_id: str) -> List[Dict[str, Any]]:
        """Get list of paused devices.

        Args:
            network_id: ID of the network

        Returns:
            List of paused devices

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting paused devices for network %s", network_id)

        # Get all devices
        devices = await self.get_devices(network_id)

        # Filter to only paused devices
        paused = [device for device in devices if device.get("paused", False)]

        _LOGGER.debug("Found %d paused devices", len(paused))

        return paused

    # ==================== Device Priority ====================

    async def get_device_priority(self, network_id: str, device_id: str) -> Dict[str, Any]:
        """Get priority settings for a device.

        Args:
            network_id: ID of the network
            device_id: ID of the device

        Returns:
            Dictionary with priority settings:
            - prioritized: bool - Whether device is prioritized
            - duration: int - Priority duration in minutes (0 = indefinite)
            - expires_at: str - When priority expires (if set)

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting priority for device %s", device_id)

        response = await self.get(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
        )

        data = response.get("data", {})

        return {
            "prioritized": data.get("prioritized", False),
            "priority": data.get("priority", False),
            "duration": data.get("priority_duration", 0),
            "expires_at": data.get("priority_expires_at"),
        }

    async def set_device_priority(
        self,
        network_id: str,
        device_id: str,
        prioritized: bool,
        duration_minutes: Optional[int] = None,
    ) -> bool:
        """Set priority for a device (bandwidth prioritization).

        Args:
            network_id: ID of the network
            device_id: ID of the device
            prioritized: True to prioritize, False to remove priority
            duration_minutes: Duration in minutes (0 or None = indefinite)

        Returns:
            True if the operation was successful

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

        response = await self.put(
            f"networks/{network_id}/devices/{device_id}",
            auth_token=auth_token,
            json=payload,
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def prioritize_device(
        self,
        network_id: str,
        device_id: str,
        duration_minutes: int = 0,
    ) -> bool:
        """Prioritize a device for bandwidth.

        Convenience method to prioritize a device.

        Args:
            network_id: ID of the network
            device_id: ID of the device
            duration_minutes: Duration in minutes (0 = indefinite)

        Returns:
            True if the operation was successful
        """
        return await self.set_device_priority(network_id, device_id, True, duration_minutes)

    async def deprioritize_device(self, network_id: str, device_id: str) -> bool:
        """Remove priority from a device.

        Convenience method to remove device priority.

        Args:
            network_id: ID of the network
            device_id: ID of the device

        Returns:
            True if the operation was successful
        """
        return await self.set_device_priority(network_id, device_id, False)

    async def get_prioritized_devices(self, network_id: str) -> List[Dict[str, Any]]:
        """Get list of prioritized devices.

        Args:
            network_id: ID of the network

        Returns:
            List of prioritized devices with their priority settings

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting prioritized devices for network %s", network_id)

        # Get all devices
        devices = await self.get_devices(network_id)

        # Filter to only prioritized devices
        prioritized = [
            device
            for device in devices
            if device.get("prioritized", False) or device.get("priority", False)
        ]

        _LOGGER.debug("Found %d prioritized devices", len(prioritized))

        return prioritized
