"""Power-saving settings and schedules API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._params import resolve_nested_url
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)


class PowerSavingAPI(AuthenticatedAPI):
    """Power-saving settings and schedules API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the PowerSavingAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def set_power_saving(
        self,
        network_id: str,
        *,
        enable: Optional[bool] = None,
        power_saving_schedule_enabled: Optional[bool] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set power-saving settings for a network - returns raw Eero API response.

        Issues a JSON PUT to the network's ``power_saving`` sub-resource
        with exactly the fields supplied among ``enable`` and
        ``power_saving_schedule_enabled``.

        .. warning::
            This write has not been confirmed against a live network.
            Follow the read-compare-skip discipline: read `get_schedules`
            (or the network envelope's ``power_saving`` fields) first, and
            only issue this write when the stored settings differ from the
            desired ones. Never retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enable: Whether to enable power saving. Omitted from the request
                when ``None``.
            power_saving_schedule_enabled: Whether the power-saving schedule
                is enabled. Omitted from the request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``power_saving`` link is
                used instead of the default template. Read only; never
                mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If neither field is supplied
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {}
        if enable is not None:
            payload["enable"] = enable
        if power_saving_schedule_enabled is not None:
            payload["power_saving_schedule_enabled"] = power_saving_schedule_enabled

        if not payload:
            raise EeroValidationException(
                "power_saving",
                "at least one of enable, power_saving_schedule_enabled must be supplied",
            )

        url = sub_resource_url(
            network_id,
            "networks/{id}/power_saving",
            link="power_saving",
            parent=as_envelope(parent),
        )
        warn_uncharacterised_write(_LOGGER, "set power saving for network")
        return await self.put(url, auth_token=auth_token, json=payload)

    async def get_schedules(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get power-saving schedules for a network - returns raw Eero API response.

        GETs the network's ``power_saving/schedules`` sub-resource. This is
        a verified read.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/power_saving/schedules")
        _LOGGER.debug("Getting power saving schedules for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def create_schedule(
        self,
        network_id: str,
        *,
        name: str,
        days: Any,
        start_time: str,
        end_time: str,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """Create a power-saving schedule - returns raw Eero API response.

        Issues a JSON POST to the network's ``power_saving/schedules``
        sub-resource with ``name``, ``days``, ``start_time``, ``end_time``,
        and ``enabled``.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            name: The schedule's name.
            days: The days the schedule applies to, forwarded to the API
                unchanged.
            start_time: The schedule's start time.
            end_time: The schedule's end time.
            enabled: Whether the schedule is enabled. Defaults to True.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/power_saving/schedules")
        payload = {
            "name": name,
            "days": days,
            "start_time": start_time,
            "end_time": end_time,
            "enabled": enabled,
        }
        warn_uncharacterised_write(_LOGGER, "create power saving schedule for network")
        return await self.post(url, auth_token=auth_token, json=payload)

    async def update_schedule(
        self,
        network_id: str,
        schedule_id: str,
        *,
        name: Optional[str] = None,
        days: Optional[Any] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a power-saving schedule - returns raw Eero API response.

        Issues a JSON PUT to the network's
        ``power_saving/schedules/{schedule_id}`` sub-resource with exactly
        the fields supplied among ``name``, ``days``, ``start_time``,
        ``end_time``, and ``enabled``.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_schedules` first,
            and only issue this write when the stored schedule differs from
            the desired one. Never retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            schedule_id: The schedule's bare ID.
            name: The schedule's name. Omitted from the request when
                ``None``.
            days: The days the schedule applies to, forwarded to the API
                unchanged. Omitted from the request when ``None``.
            start_time: The schedule's start time. Omitted from the request
                when ``None``.
            end_time: The schedule's end time. Omitted from the request
                when ``None``.
            enabled: Whether the schedule is enabled. Omitted from the
                request when ``None``.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If no field is supplied
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
        if start_time is not None:
            payload["start_time"] = start_time
        if end_time is not None:
            payload["end_time"] = end_time
        if enabled is not None:
            payload["enabled"] = enabled

        if not payload:
            raise EeroValidationException(
                "schedule",
                "at least one of name, days, start_time, end_time, enabled must be supplied",
            )

        url = resolve_nested_url(network_id, schedule_id, prefix="power_saving/schedules")
        warn_uncharacterised_write(
            _LOGGER,
            "update power saving schedule for network",
        )
        return await self.put(url, auth_token=auth_token, json=payload)

    async def delete_schedule(self, network_id: str, schedule_id: str) -> Dict[str, Any]:
        """Delete a power-saving schedule - returns raw Eero API response.

        Issues a DELETE to the network's
        ``power_saving/schedules/{schedule_id}`` sub-resource.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            schedule_id: The schedule's bare ID.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resolve_nested_url(network_id, schedule_id, prefix="power_saving/schedules")
        warn_uncharacterised_write(
            _LOGGER,
            "delete power saving schedule for network",
        )
        return await self.delete(url, auth_token=auth_token)
