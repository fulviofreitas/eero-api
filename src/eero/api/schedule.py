"""Schedule API for Eero profile internet access schedules.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

Scheduled pauses are sub-resources of a profile, not a field on the profile
itself: they live at ``networks/{id}/profiles/{profile}/schedules``, are
created with a POST to that collection, and are updated/deleted through
their own URL. This replaces the previous (incorrect) design of writing a
``schedule`` array directly onto the profile.

.. warning::
    None of the writes in this module have been verified against a live
    network. Each logs a warning via
    `eero.api._writes.warn_uncharacterised_write`. Follow the
    read-compare-skip discipline: read the current schedules first, and do
    not retry a failed write.
"""

from typing import Any, Dict, List, Mapping, Optional, Sequence

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._params import resolve_nested_url
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url, self_url

_LOGGER = get_secure_logger(__name__)

#: All seven days, used as the default scope for `enable_bedtime`.
ALL_DAYS = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")
WEEKEND = ("saturday", "sunday")


def _resolve_schedule_url(schedule: Any) -> str:
    """Resolve a scheduled pause's own URL from a URL, path, or envelope.

    Args:
        schedule: Either a bare path/absolute URL as previously returned by
            the API, or the pause's own cached envelope (full or ``data``).

    Returns:
        The absolute URL of the pause resource.

    Raises:
        EeroValidationException: If ``schedule`` is a mapping with no
            resolvable ``url`` field, or a string that isn't a valid path,
            or absolute URL, or neither a string nor a mapping.
    """
    if isinstance(schedule, Mapping):
        envelope = as_envelope(schedule)
        url = self_url(envelope) if envelope is not None else None
        if url is None:
            raise EeroValidationException("schedule", "envelope has no resolvable 'url' field")
        return url
    if isinstance(schedule, str):
        return resource_url(schedule, "{id}")
    raise EeroValidationException(
        "schedule", "must be a URL/path string or a pause envelope (mapping)"
    )


class ScheduleAPI(AuthenticatedAPI):
    """Schedule API for Eero.

    Manages internet access schedules (scheduled pauses) for profiles,
    including bedtime restrictions and custom time blocks.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ScheduleAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    def _schedules_url(
        self, network: str, profile: str, parent: Optional[Mapping[str, Any]]
    ) -> str:
        """Resolve the schedules collection URL for a profile.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            parent: The profile's own cached envelope, if the caller has
                one; its ``schedules`` link is preferred when present.

        Returns:
            The absolute schedules-collection URL.

        Raises:
            EeroValidationException: If ``profile`` is not a non-empty
                string, or ``network``/``profile`` cannot be resolved to a
                valid URL.
        """
        return resolve_nested_url(
            network,
            profile,
            prefix="profiles",
            suffix="/schedules",
            link="schedules",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )

    async def get_schedules(
        self,
        network: str,
        profile: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get the scheduled pauses for a profile - returns raw Eero API response.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = self._schedules_url(network, profile, parent)
        _LOGGER.debug("Getting schedules for profile %s", profile)
        return await self.get(url, auth_token=auth_token)

    async def create_schedule(
        self,
        network: str,
        profile: str,
        *,
        name: str,
        days: Sequence[str],
        start: str,
        end: str,
        enabled: bool = True,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a scheduled pause for a profile - returns raw Eero API response.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            name: Name of the schedule.
            days: Days the pause applies to, e.g. ``["monday", "tuesday"]``.
            start: Start time (``HH:MM``).
            end: End time (``HH:MM``).
            enabled: Whether the schedule is active. Defaults to ``True``.
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = self._schedules_url(network, profile, parent)
        payload = {"name": name, "days": days, "start": start, "end": end, "enabled": enabled}

        warn_uncharacterised_write(_LOGGER, "create_schedule")
        _LOGGER.debug("Creating schedule '%s' for profile %s", name, profile)
        return await self.post(url, auth_token=auth_token, json=payload)

    async def update_schedule(
        self,
        schedule: Any,
        *,
        name: Optional[str] = None,
        days: Optional[List[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a scheduled pause via its own URL - returns raw Eero API response.

        Args:
            schedule: The pause's own path/absolute URL (as returned by
                `get_schedules`/`create_schedule`), or its cached envelope.
            name: New name, or ``None`` to omit.
            days: New days list, or ``None`` to omit.
            start: New start time, or ``None`` to omit.
            end: New end time, or ``None`` to omit.
            enabled: New enabled state, or ``None`` to omit.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``schedule`` cannot be resolved to a URL
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if days is not None:
            payload["days"] = days
        if start is not None:
            payload["start"] = start
        if end is not None:
            payload["end"] = end
        if enabled is not None:
            payload["enabled"] = enabled

        if not payload:
            raise EeroValidationException(
                "schedule",
                "at least one of name, days, start, end, enabled must be supplied",
            )

        url = _resolve_schedule_url(schedule)
        warn_uncharacterised_write(_LOGGER, "update_schedule")
        _LOGGER.debug("Updating schedule at %s: %s", url, sorted(payload))
        return await self.put(url, auth_token=auth_token, json=payload)

    async def delete_schedule(self, schedule: Any) -> Dict[str, Any]:
        """Delete a scheduled pause via its own URL - returns raw Eero API response.

        Args:
            schedule: The pause's own path/absolute URL, or its cached
                envelope.

        Returns:
            Raw API response: {"meta": {...}, ...}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``schedule`` cannot be resolved to a URL
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = _resolve_schedule_url(schedule)
        warn_uncharacterised_write(_LOGGER, "delete_schedule")
        _LOGGER.debug("Deleting schedule at %s", url)
        return await self.delete(url, auth_token=auth_token)

    async def clear_profile_schedule(
        self,
        network: str,
        profile: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Delete every scheduled pause currently set on a profile.

        Issues one read (`get_schedules`) followed by one DELETE per
        existing pause -- N deletes for N pauses. This is never retried;
        a pause that fails to delete is left in place and its response
        (or the raised exception) is not swallowed.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            A list of the raw API responses from each DELETE, in the order
            the pauses were read.

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error for the read, or
                for any individual delete (raised immediately, aborting any
                remaining deletes).
        """
        schedules_response = await self.get_schedules(network, profile, parent=parent)
        data = schedules_response.get("data", schedules_response)
        pauses = data if isinstance(data, list) else []

        _LOGGER.debug(
            "Clearing %d schedule(s) for profile %s (%d individual deletes)",
            len(pauses),
            profile,
            len(pauses),
        )

        results: List[Dict[str, Any]] = []
        for pause in pauses:
            results.append(await self.delete_schedule(pause))
        return results

    async def enable_bedtime(
        self,
        network: str,
        profile: str,
        start_time: str,
        end_time: str,
        days: Optional[List[str]] = None,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a single bedtime scheduled pause for a profile.

        Built on `create_schedule` (one pause), rather than writing a
        ``schedule`` array onto the profile.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            start_time: Time to start blocking (``HH:MM``, e.g. ``"21:00"``).
            end_time: Time to end blocking (``HH:MM``, e.g. ``"07:00"``).
            days: Days to apply. Defaults to all seven days.
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        resolved_days = list(days) if days is not None else list(ALL_DAYS)

        _LOGGER.debug(
            "Enabling bedtime for profile %s: %s - %s on %s",
            profile,
            start_time,
            end_time,
            resolved_days,
        )

        return await self.create_schedule(
            network,
            profile,
            name="Bedtime",
            days=resolved_days,
            start=start_time,
            end=end_time,
            enabled=True,
            parent=parent,
        )

    async def set_weekday_bedtime(
        self,
        network: str,
        profile: str,
        start_time: str,
        end_time: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set bedtime for weekdays only (Monday-Friday).

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            start_time: Time to start blocking (``HH:MM``).
            end_time: Time to end blocking (``HH:MM``).
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        return await self.enable_bedtime(
            network, profile, start_time, end_time, list(WEEKDAYS), parent=parent
        )

    async def set_weekend_bedtime(
        self,
        network: str,
        profile: str,
        start_time: str,
        end_time: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set bedtime for weekends only (Saturday-Sunday).

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            start_time: Time to start blocking (``HH:MM``).
            end_time: Time to end blocking (``HH:MM``).
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        return await self.enable_bedtime(
            network, profile, start_time, end_time, list(WEEKEND), parent=parent
        )
