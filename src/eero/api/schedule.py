"""Schedule API for Eero profile internet access schedules.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
from typing import Any, Dict, List, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class ScheduleAPI(AuthenticatedAPI):
    """Schedule API for Eero.

    Manages internet access schedules for profiles, including bedtime
    restrictions and custom time blocks.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ScheduleAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_profile_schedule(
        self, network_id: str, profile_id: str
    ) -> Dict[str, Any]:
        """Get internet access schedule for a profile - returns raw Eero API response.

        The schedule data is in the 'schedule' field of the response data.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting schedule for profile %s", profile_id)
        return await self.get(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
        )

    async def set_profile_schedule(
        self,
        network_id: str,
        profile_id: str,
        time_blocks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Set internet access schedule for a profile - returns raw Eero API response.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            time_blocks: List of time blocks, each containing:
                - days: list of days (e.g., ["monday", "tuesday"])
                - start: start time (HH:MM format)
                - end: end time (HH:MM format)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(
            "Setting schedule for profile %s with %d time blocks",
            profile_id,
            len(time_blocks),
        )

        return await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"schedule": time_blocks},
        )

    async def clear_profile_schedule(
        self, network_id: str, profile_id: str
    ) -> Dict[str, Any]:
        """Clear all schedules for a profile - returns raw Eero API response.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        return await self.set_profile_schedule(network_id, profile_id, [])

    async def enable_bedtime(
        self,
        network_id: str,
        profile_id: str,
        start_time: str,
        end_time: str,
        days: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Enable bedtime mode for a profile - returns raw Eero API response.

        Blocks internet access during the specified time period.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            start_time: Time to start blocking (HH:MM format, e.g., "21:00")
            end_time: Time to end blocking (HH:MM format, e.g., "07:00")
            days: Days to apply (defaults to all days)
                  Valid: "monday", "tuesday", "wednesday", "thursday",
                         "friday", "saturday", "sunday"

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        if days is None:
            days = [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]

        _LOGGER.debug(
            "Enabling bedtime for profile %s: %s - %s on %s",
            profile_id,
            start_time,
            end_time,
            days,
        )

        bedtime_block = {
            "days": days,
            "start": start_time,
            "end": end_time,
            "type": "bedtime",
        }

        return await self.set_profile_schedule(network_id, profile_id, [bedtime_block])

    async def set_weekday_bedtime(
        self,
        network_id: str,
        profile_id: str,
        start_time: str,
        end_time: str,
    ) -> Dict[str, Any]:
        """Set bedtime for weekdays only (Monday-Friday) - returns raw Eero API response.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            start_time: Time to start blocking (HH:MM format)
            end_time: Time to end blocking (HH:MM format)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        return await self.enable_bedtime(
            network_id, profile_id, start_time, end_time, weekdays
        )

    async def set_weekend_bedtime(
        self,
        network_id: str,
        profile_id: str,
        start_time: str,
        end_time: str,
    ) -> Dict[str, Any]:
        """Set bedtime for weekends only (Saturday-Sunday) - returns raw Eero API response.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            start_time: Time to start blocking (HH:MM format)
            end_time: Time to end blocking (HH:MM format)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        weekend = ["saturday", "sunday"]
        return await self.enable_bedtime(
            network_id, profile_id, start_time, end_time, weekend
        )
