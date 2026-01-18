"""Eero devices API for Eero."""

import logging
from typing import Any, Dict, List, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class EerosAPI(AuthenticatedAPI):
    """Eero devices API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the EerosAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_eeros(self, network_id: str) -> List[Dict[str, Any]]:
        """Get list of Eero devices.

        Args:
            network_id: ID of the network to get Eeros from

        Returns:
            List of Eero device data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting eeros for network {network_id}")

        # Simplified path construction
        response = await self.get(
            f"networks/{network_id}/eeros",
            auth_token=auth_token,
        )

        # Handle different response formats
        data = response.get("data", [])
        if isinstance(data, list):
            # Data is directly a list of eeros
            eeros_data = data
        elif isinstance(data, dict) and "data" in data:
            # Data is a dictionary with a nested data field
            eeros_data = data.get("data", [])
        else:
            # Fallback to empty list
            eeros_data = []

        _LOGGER.debug(f"Found {len(eeros_data)} eeros")

        return eeros_data

    async def get_eero(self, network_id: str, eero_id: str) -> Dict[str, Any]:
        """Get information about a specific Eero device.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device to get

        Returns:
            Eero device data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting eero {eero_id}")

        # Use direct eero endpoint (not network-scoped)
        response = await self.get(
            f"eeros/{eero_id}",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def reboot_eero(self, network_id: str, eero_id: str) -> bool:
        """Reboot an Eero device.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device to reboot

        Returns:
            True if reboot was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Rebooting eero {eero_id}")

        # Use direct eero endpoint (not network-scoped)
        response = await self.post(
            f"eeros/{eero_id}/reboot",
            auth_token=auth_token,
            json={},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    # ==================== LED Control ====================

    async def get_led_status(self, network_id: str, eero_id: str) -> Dict[str, Any]:
        """Get LED status for an Eero device.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device

        Returns:
            Dictionary with LED status:
            - led_on: bool - Whether LED is on
            - led_brightness: int - LED brightness level (if available)

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting LED status for eero %s", eero_id)

        # Use direct eero endpoint (not network-scoped)
        response = await self.get(
            f"eeros/{eero_id}",
            auth_token=auth_token,
        )

        data = response.get("data", {})
        return {
            "led_on": data.get("led_on", True),
            "led_brightness": data.get("led_brightness"),
        }

    async def set_led(
        self,
        network_id: str,
        eero_id: str,
        enabled: bool,
    ) -> bool:
        """Set LED on/off for an Eero device.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device
            enabled: True to turn LED on, False to turn off

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting LED %s for eero %s", "on" if enabled else "off", eero_id)

        # Use direct eero endpoint (not network-scoped)
        response = await self.put(
            f"eeros/{eero_id}",
            auth_token=auth_token,
            json={"led_on": enabled},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def set_led_brightness(
        self,
        network_id: str,
        eero_id: str,
        brightness: int,
    ) -> bool:
        """Set LED brightness for an Eero device.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device
            brightness: Brightness level (0-100)

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        # Clamp brightness to valid range
        brightness = max(0, min(100, brightness))

        _LOGGER.debug("Setting LED brightness to %d for eero %s", brightness, eero_id)

        # Use direct eero endpoint (not network-scoped)
        response = await self.put(
            f"eeros/{eero_id}",
            auth_token=auth_token,
            json={"led_brightness": brightness},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    # ==================== Nightlight (Eero Beacon) ====================

    async def get_nightlight(self, network_id: str, eero_id: str) -> Dict[str, Any]:
        """Get nightlight settings for an Eero Beacon device.

        Note: Nightlight is only available on Eero Beacon devices.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero Beacon device

        Returns:
            Dictionary with nightlight settings:
            - enabled: bool
            - brightness: int (0-100)
            - brightness_percentage: int (0-100)
            - schedule: dict with on/off times
            - ambient_light_enabled: bool

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting nightlight settings for eero %s", eero_id)

        # Use direct eero endpoint (not network-scoped)
        response = await self.get(
            f"eeros/{eero_id}",
            auth_token=auth_token,
        )

        data = response.get("data", {})
        nightlight = data.get("nightlight", {})

        if not nightlight:
            # Device may not support nightlight
            return {
                "supported": False,
                "enabled": False,
                "brightness": 0,
                "brightness_percentage": 0,
                "schedule": None,
                "ambient_light_enabled": False,
            }

        return {
            "supported": True,
            "enabled": nightlight.get("enabled", False),
            "brightness": nightlight.get("brightness", 0),
            "brightness_percentage": nightlight.get("brightness_percentage", 0),
            "schedule": nightlight.get("schedule"),
            "ambient_light_enabled": nightlight.get("ambient_light_enabled", False),
        }

    async def set_nightlight(
        self,
        network_id: str,
        eero_id: str,
        enabled: Optional[bool] = None,
        brightness: Optional[int] = None,
        schedule_enabled: Optional[bool] = None,
        schedule_on: Optional[str] = None,
        schedule_off: Optional[str] = None,
        ambient_light_enabled: Optional[bool] = None,
    ) -> bool:
        """Set nightlight settings for an Eero Beacon device.

        Note: Nightlight is only available on Eero Beacon devices.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero Beacon device
            enabled: True to enable nightlight, False to disable
            brightness: Brightness level (0-100)
            schedule_enabled: True to enable schedule mode
            schedule_on: Time to turn on (HH:MM format, e.g., "20:00")
            schedule_off: Time to turn off (HH:MM format, e.g., "06:00")
            ambient_light_enabled: True to auto-adjust based on ambient light

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        # Build nightlight payload with only provided values
        nightlight_payload: Dict[str, Any] = {}

        if enabled is not None:
            nightlight_payload["enabled"] = enabled

        if brightness is not None:
            nightlight_payload["brightness"] = max(0, min(100, brightness))

        if ambient_light_enabled is not None:
            nightlight_payload["ambient_light_enabled"] = ambient_light_enabled

        # Build schedule if any schedule values provided
        if schedule_enabled is not None or schedule_on is not None or schedule_off is not None:
            schedule: Dict[str, Any] = {}
            if schedule_enabled is not None:
                schedule["enabled"] = schedule_enabled
            if schedule_on is not None:
                schedule["on"] = schedule_on
            if schedule_off is not None:
                schedule["off"] = schedule_off
            if schedule:
                nightlight_payload["schedule"] = schedule

        if not nightlight_payload:
            _LOGGER.warning("No nightlight settings provided")
            return False

        _LOGGER.debug("Setting nightlight for eero %s: %s", eero_id, nightlight_payload)

        # Use direct eero endpoint (not network-scoped)
        response = await self.put(
            f"eeros/{eero_id}",
            auth_token=auth_token,
            json={"nightlight": nightlight_payload},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def set_nightlight_brightness(
        self,
        network_id: str,
        eero_id: str,
        brightness: int,
    ) -> bool:
        """Set nightlight brightness for an Eero Beacon device.

        Convenience method for just setting brightness.

        Args:
            network_id: ID of the network the Eero belongs to
            eero_id: ID of the Eero Beacon device
            brightness: Brightness level (0-100)

        Returns:
            True if the operation was successful
        """
        return await self.set_nightlight(network_id, eero_id, brightness=brightness)

    async def set_nightlight_schedule(
        self,
        network_id: str,
        eero_id: str,
        enabled: bool,
        on_time: Optional[str] = None,
        off_time: Optional[str] = None,
    ) -> bool:
        """Set nightlight schedule for an Eero Beacon device.

        Convenience method for setting schedule.

        Args:
            network_id: ID of the network the Eero belongs to
            eero_id: ID of the Eero Beacon device
            enabled: True to enable schedule
            on_time: Time to turn on (HH:MM format)
            off_time: Time to turn off (HH:MM format)

        Returns:
            True if the operation was successful
        """
        return await self.set_nightlight(
            network_id,
            eero_id,
            schedule_enabled=enabled,
            schedule_on=on_time,
            schedule_off=off_time,
        )
