"""Eero devices API for Eero.

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


class EerosAPI(AuthenticatedAPI):
    """Eero devices API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the EerosAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_eeros(self, network_id: str) -> Dict[str, Any]:
        """Get list of Eero devices - returns raw Eero API response.

        Args:
            network_id: ID of the network to get Eeros from

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting eeros for network %s", network_id)
        return await self.get(f"networks/{network_id}/eeros", auth_token=auth_token)

    async def get_eero(self, network_id: str, eero_id: str) -> Dict[str, Any]:
        """Get information about a specific Eero device - returns raw Eero API response.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device to get

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting eero %s", eero_id)
        return await self.get(f"eeros/{eero_id}", auth_token=auth_token)

    async def reboot_eero(self, network_id: str, eero_id: str) -> Dict[str, Any]:
        """Reboot an Eero device - returns raw Eero API response.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device to reboot

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Rebooting eero %s", eero_id)
        return await self.post(f"eeros/{eero_id}/reboot", auth_token=auth_token, json={})

    async def get_led_status(self, network_id: str, eero_id: str) -> Dict[str, Any]:
        """Get LED status for an Eero device - returns raw Eero API response.

        The raw response includes led_on and led_brightness in the data field.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting LED status for eero %s", eero_id)
        return await self.get(f"eeros/{eero_id}", auth_token=auth_token)

    async def set_led(
        self,
        network_id: str,
        eero_id: str,
        enabled: bool,
    ) -> Dict[str, Any]:
        """Set LED on/off for an Eero device - returns raw Eero API response.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device
            enabled: True to turn LED on, False to turn off

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting LED %s for eero %s", "on" if enabled else "off", eero_id)

        return await self.put(
            f"eeros/{eero_id}",
            auth_token=auth_token,
            json={"led_on": enabled},
        )

    async def set_led_brightness(
        self,
        network_id: str,
        eero_id: str,
        brightness: int,
    ) -> Dict[str, Any]:
        """Set LED brightness for an Eero device - returns raw Eero API response.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero device
            brightness: Brightness level (0-100)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

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

        return await self.put(
            f"eeros/{eero_id}",
            auth_token=auth_token,
            json={"led_brightness": brightness},
        )

    async def get_nightlight(self, network_id: str, eero_id: str) -> Dict[str, Any]:
        """Get nightlight settings for an Eero Beacon device - returns raw Eero API response.

        Note: Nightlight is only available on Eero Beacon devices.
        The raw response includes a 'nightlight' object in the data field if supported.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: ID of the Eero Beacon device

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting nightlight settings for eero %s", eero_id)
        return await self.get(f"eeros/{eero_id}", auth_token=auth_token)

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
    ) -> Dict[str, Any]:
        """Set nightlight settings for an Eero Beacon device - returns raw Eero API response.

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
            Raw API response: {"meta": {...}, "data": {...}}

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
            # Return empty response format - downstream can handle this
            return {"meta": {"code": 400}, "data": {}}

        _LOGGER.debug("Setting nightlight for eero %s: %s", eero_id, nightlight_payload)

        return await self.put(
            f"eeros/{eero_id}",
            auth_token=auth_token,
            json={"nightlight": nightlight_payload},
        )

    async def set_nightlight_brightness(
        self,
        network_id: str,
        eero_id: str,
        brightness: int,
    ) -> Dict[str, Any]:
        """Set nightlight brightness for an Eero Beacon device - returns raw Eero API response.

        Convenience method for just setting brightness.

        Args:
            network_id: ID of the network the Eero belongs to
            eero_id: ID of the Eero Beacon device
            brightness: Brightness level (0-100)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        return await self.set_nightlight(network_id, eero_id, brightness=brightness)

    async def set_nightlight_schedule(
        self,
        network_id: str,
        eero_id: str,
        enabled: bool,
        on_time: Optional[str] = None,
        off_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set nightlight schedule for an Eero Beacon device - returns raw Eero API response.

        Convenience method for setting schedule.

        Args:
            network_id: ID of the network the Eero belongs to
            eero_id: ID of the Eero Beacon device
            enabled: True to enable schedule
            on_time: Time to turn on (HH:MM format)
            off_time: Time to turn off (HH:MM format)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        return await self.set_nightlight(
            network_id,
            eero_id,
            schedule_enabled=enabled,
            schedule_on=on_time,
            schedule_off=off_time,
        )
