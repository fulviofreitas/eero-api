"""Schedule API for Eero profile internet access schedules."""

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
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ScheduleAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_profile_schedule(self, network_id: str, profile_id: str) -> Dict[str, Any]:
        """Get internet access schedule for a profile.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile

        Returns:
            Dictionary containing schedule configuration:
            - enabled: bool - Whether schedule is active
            - schedule_type: str - Type of schedule (bedtime, custom)
            - time_blocks: list - List of blocked time periods
            - days: list - Days the schedule applies to

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting schedule for profile %s", profile_id)

        response = await self.get(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
        )

        data = response.get("data", {})
        schedule = data.get("schedule", [])

        # Parse schedule data
        result = {
            "enabled": len(schedule) > 0 if isinstance(schedule, list) else bool(schedule),
            "schedule_type": "custom",
            "time_blocks": [],
            "paused": data.get("paused", False),
        }

        # Extract bedtime/schedule info from various formats
        if isinstance(schedule, list) and schedule:
            result["time_blocks"] = schedule
        elif isinstance(schedule, dict):
            result["enabled"] = schedule.get("enabled", False)
            result["time_blocks"] = schedule.get("blocks", [])
            result["schedule_type"] = schedule.get("type", "custom")

        # Check for bedtime in state
        state = data.get("state", {})
        if isinstance(state, dict) and state.get("schedule"):
            result["bedtime_active"] = True

        return result

    async def set_profile_schedule(
        self,
        network_id: str,
        profile_id: str,
        time_blocks: List[Dict[str, Any]],
    ) -> bool:
        """Set internet access schedule for a profile.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            time_blocks: List of time blocks, each containing:
                - days: list of days (e.g., ["monday", "tuesday"])
                - start: start time (HH:MM format)
                - end: end time (HH:MM format)

        Returns:
            True if the operation was successful

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

        response = await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"schedule": time_blocks},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def clear_profile_schedule(self, network_id: str, profile_id: str) -> bool:
        """Clear all schedules for a profile.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile

        Returns:
            True if the operation was successful
        """
        return await self.set_profile_schedule(network_id, profile_id, [])

    async def enable_bedtime(
        self,
        network_id: str,
        profile_id: str,
        start_time: str,
        end_time: str,
        days: Optional[List[str]] = None,
    ) -> bool:
        """Enable bedtime mode for a profile.

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
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        if days is None:
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

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
    ) -> bool:
        """Set bedtime for weekdays only (Monday-Friday).

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            start_time: Time to start blocking (HH:MM format)
            end_time: Time to end blocking (HH:MM format)

        Returns:
            True if the operation was successful
        """
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday"]
        return await self.enable_bedtime(network_id, profile_id, start_time, end_time, weekdays)

    async def set_weekend_bedtime(
        self,
        network_id: str,
        profile_id: str,
        start_time: str,
        end_time: str,
    ) -> bool:
        """Set bedtime for weekends only (Saturday-Sunday).

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            start_time: Time to start blocking (HH:MM format)
            end_time: Time to end blocking (HH:MM format)

        Returns:
            True if the operation was successful
        """
        weekend = ["saturday", "sunday"]
        return await self.enable_bedtime(network_id, profile_id, start_time, end_time, weekend)

    async def add_time_off(
        self,
        network_id: str,
        profile_id: str,
        start_time: str,
        end_time: str,
        days: List[str],
        name: Optional[str] = None,
    ) -> bool:
        """Add a time-off period when internet is blocked.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            start_time: Time to start blocking (HH:MM format)
            end_time: Time to end blocking (HH:MM format)
            days: Days to apply
            name: Optional name for this time block

        Returns:
            True if the operation was successful
        """
        # Get current schedule
        current = await self.get_profile_schedule(network_id, profile_id)
        current_blocks = current.get("time_blocks", [])

        # Add new block
        new_block: Dict[str, Any] = {
            "days": days,
            "start": start_time,
            "end": end_time,
        }
        if name:
            new_block["name"] = name

        current_blocks.append(new_block)

        return await self.set_profile_schedule(network_id, profile_id, current_blocks)
