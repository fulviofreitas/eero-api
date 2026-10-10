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

from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlsplit

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._params import resolve_nested_url
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import require_family_path, resource_url, self_url

_LOGGER = get_secure_logger(__name__)

#: The shape of a scheduled pause's own path, after the version segment.
_SCHEDULE_FAMILY = "networks/{id}/profiles/{id}/schedules/{id}"

#: All seven days, used as the default scope for `enable_bedtime`.
ALL_DAYS = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
WEEKEND = ("Saturday", "Sunday")


def _schedule_days(days: List[str]) -> List[str]:
    if not isinstance(days, list) or not days:
        raise EeroValidationException("days", "must be a non-empty list of full day names")
    result = []
    for day in days:
        if not isinstance(day, str) or day.capitalize() not in ALL_DAYS:
            raise EeroValidationException("days", "must contain full day names")
        result.append(day.capitalize())
    return result


def _resolve_schedule_url(schedule: Any) -> str:
    """Resolve a scheduled pause's own URL from a path, URL, or envelope.

    Args:
        schedule: Either a path/absolute URL as previously returned by the
            API, or the pause's own cached envelope (full or ``data``).

    Returns:
        The absolute URL of the pause resource.

    Raises:
        EeroValidationException: If ``schedule`` is a mapping with no
            resolvable ``url`` field, a bare identifier, a path/URL that is
            not a scheduled pause
            (``/<version>/networks/{id}/profiles/{id}/schedules/{id}``), or
            neither a string nor a mapping.

    A path or URL a caller supplies is confined to that shape, so a write
    cannot be redirected to another resource on the API host. A link the API
    published in an envelope is trusted as published and not confined. A bare
    identifier is refused: a pause lives under a network and a profile that
    the update and delete methods are not given, so the id alone cannot be
    resolved, and placing it under the version root would address whatever
    one-segment endpoint shares its name.
    """
    if isinstance(schedule, Mapping):
        envelope = as_envelope(schedule)
        url = self_url(envelope) if envelope is not None else None
        if url is None:
            raise EeroValidationException("schedule", "envelope has no resolvable 'url' field")
        return url
    if isinstance(schedule, str):
        if not (schedule.startswith("/") or schedule.lower().startswith(("http://", "https://"))):
            raise EeroValidationException(
                "schedule",
                "must be the schedule's path, absolute URL or envelope; "
                "a bare id cannot be resolved",
            )
        url = resource_url(schedule, "{id}")
        require_family_path(url, _SCHEDULE_FAMILY, field="schedule")
        return url
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
        """Get scheduled pauses from a fresh profile read.

        The schedules collection GET returns 404. For compatibility this method
        returns the profile response meta with its raw schedule list as data;
        individual schedule objects are not transformed.

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

        envelope = as_envelope(parent)
        url = self_url(envelope) if envelope is not None else None
        if url is None:
            url = resolve_nested_url(network, profile, prefix="profiles")
        response = await self.get(url, auth_token=auth_token)
        data = response.get("data", {})
        schedules = data.get("schedule", []) if isinstance(data, dict) else []
        return {
            "meta": response.get("meta", {}),
            "data": schedules if isinstance(schedules, list) else [],
        }

    async def create_schedule(
        self,
        network: str,
        profile: str,
        *,
        name: str,
        days: List[str],
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
            days: Days the pause applies to, e.g. ``["Monday", "Tuesday"]``.
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
        payload = {
            "name": name,
            "days": _schedule_days(days),
            "start": start,
            "end": end,
            "enabled": enabled,
        }

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

        Omitted fields are read from the current profile and sent in the complete
        replacement, including enabled. Read-modify-write is not atomic; a
        concurrent edit can be overwritten. Supply every field to avoid the read.

        Args:
            schedule: The pause's own path or absolute URL (as returned by
                `get_schedules`/`create_schedule`), or its cached envelope.
                A bare id is rejected because network/profile context is absent.
            name: New name, or ``None`` to preserve.
            days: New days list, or ``None`` to preserve.
            start: New start time, or ``None`` to preserve.
            end: New end time, or ``None`` to preserve.
            enabled: New enabled state, or ``None`` to preserve.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``schedule`` is a bare id, or cannot
                be resolved to a scheduled pause's URL
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
        fields = {"name", "days", "start", "end", "enabled"}
        if not fields <= payload.keys():
            parts = urlsplit(url).path.strip("/").split("/")
            if (
                len(parts) != 7
                or parts[1] != "networks"
                or parts[3] != "profiles"
                or parts[5] != "schedules"
            ):
                raise EeroValidationException("schedule", "must identify a profile schedule")
            response = await self.get_schedules(
                f"/{parts[0]}/networks/{parts[2]}",
                f"/{parts[0]}/networks/{parts[2]}/profiles/{parts[4]}",
            )
            current = next(
                (
                    item
                    for item in response["data"]
                    if isinstance(item, dict)
                    and isinstance(item.get("url"), str)
                    and urlsplit(item["url"]).path.strip("/").split("/")[1:] == parts[1:]
                ),
                None,
            )
            if current is None or not (fields - payload.keys()) <= current.keys():
                raise EeroValidationException(
                    "schedule",
                    "current schedule is missing or incomplete; supply every replacement field",
                )
            for field in fields:
                payload.setdefault(field, current[field])
        payload["days"] = _schedule_days(payload["days"])
        warn_uncharacterised_write(_LOGGER, "update_schedule")
        _LOGGER.debug("Updating schedule at %s: %s", url, sorted(payload))
        return await self.put(url, auth_token=auth_token, json=payload)

    async def delete_schedule(self, schedule: Any) -> Dict[str, Any]:
        """Delete a scheduled pause via its own URL - returns raw Eero API response.

        Args:
            schedule: The pause's own path or absolute URL, or its cached
                envelope. A bare id is rejected: this method is not given
                the network and profile the pause lives under.

        Returns:
            Raw API response: {"meta": {...}, ...}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``schedule`` is a bare id, or cannot
                be resolved to a scheduled pause's URL
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
        resolved_days: List[str] = list(days) if days is not None else list(ALL_DAYS)

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
