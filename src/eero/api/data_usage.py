"""Data Usage API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

Every read in this family is a GET on ``networks/{network_id}/data_usage...`` that
accepts query parameters only -- ``start``, ``end`` (ISO-8601 timestamps), an
optional ``timezone``, and, on most of the family, a ``cadence`` selecting the
bucket size of the returned series (``"daily"`` or ``"hourly"``). None of these
endpoints accept a request body; the API rejects a body-bearing GET with a 400.
"""

from typing import Any, Dict, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = get_secure_logger(__name__)

#: Valid values for the `cadence` query parameter across the data-usage family.
DATA_USAGE_CADENCES = ("daily", "hourly")

#: Valid values for the `cadence` field in the data-usage report settings body.
REPORT_SETTINGS_CADENCES = ("daily", "hourly")


def _validate_cadence(cadence: Optional[str]) -> str:
    """Validate a `cadence` value against the API's two accepted buckets.

    Args:
        cadence: Candidate cadence value. ``None`` is rejected -- callers for
            whom cadence is optional must not reach this function with
            ``None``.

    Returns:
        The validated cadence, unchanged.

    Raises:
        EeroValidationException: If ``cadence`` is not ``"daily"`` or ``"hourly"``.
    """
    if cadence not in DATA_USAGE_CADENCES:
        raise EeroValidationException(
            "cadence",
            f"must be one of {DATA_USAGE_CADENCES}, got {cadence!r}",
        )
    return cadence


class DataUsageAPI(AuthenticatedAPI):
    """Data Usage API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DataUsageAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def _get_usage(
        self,
        path: str,
        network_id: str,
        *,
        start: str,
        end: str,
        cadence: Optional[str],
        timezone: Optional[str],
        extra_params: Optional[Dict[str, str]] = None,
        cadence_required: bool = False,
    ) -> Dict[str, Any]:
        """Issue a single data-usage GET, shared by every read in this module.

        Args:
            path: The endpoint path segment appended after ``data_usage``
                (empty string for the top-level resource).
            network_id: ID of the network to query.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size, one of ``"daily"``/``"hourly"``, or ``None``
                to omit the parameter entirely (unless ``cadence_required``).
            timezone: Optional IANA timezone name, or ``None`` to omit.
            extra_params: Additional query parameters specific to the caller
                (e.g. ``profile_id``), merged in after the common ones.
            cadence_required: When True, the API requires ``cadence`` on this
                endpoint -- a ``None`` value is rejected rather than omitted.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is missing when required,
                or supplied and invalid.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        params: Dict[str, str] = {"start": start, "end": end}
        if cadence is not None or cadence_required:
            params["cadence"] = _validate_cadence(cadence)
        if timezone is not None:
            params["timezone"] = timezone
        if extra_params:
            params.update(extra_params)

        url = (
            f"networks/{network_id}/data_usage/{path}"
            if path
            else f"networks/{network_id}/data_usage"
        )
        _LOGGER.debug("Getting data usage (%s) for network %s", path or "root", network_id)
        return await self.get(url, auth_token=auth_token, params=params)

    async def get_data_usage(
        self,
        network_id: str,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get network-level data usage - returns raw Eero API response.

        The API requires ``start``, ``end``, and ``cadence`` as query
        parameters on this endpoint; omitting any of them yields an error
        response. ``timezone`` is optional.

        Args:
            network_id: ID of the network to get usage from.
            start: Window start, ISO 8601 timestamp (e.g. ``"2026-07-21T00:00:00Z"``).
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size for the returned series, ``"daily"`` or
                ``"hourly"``.
            timezone: Optional IANA timezone name applied to the bucketing.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        return await self._get_usage(
            "",
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            timezone=timezone,
            cadence_required=True,
        )

    async def get_breakdown(
        self,
        network_id: str,
        *,
        start: str,
        end: str,
        cadence: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a data usage breakdown - returns raw Eero API response.

        Args:
            network_id: ID of the network to get usage from.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Optional bucket size, ``"daily"`` or ``"hourly"``.
                Omitted from the request when ``None``.
            timezone: Optional IANA timezone name.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is supplied and invalid.
            EeroAPIException: If the API returns an error.
        """
        return await self._get_usage(
            "breakdown", network_id, start=start, end=end, cadence=cadence, timezone=timezone
        )

    async def get_devices_usage(
        self,
        network_id: str,
        *,
        start: str,
        end: str,
        cadence: Optional[str] = None,
        timezone: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get per-device data usage - returns raw Eero API response.

        Args:
            network_id: ID of the network to get usage from.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Optional bucket size, ``"daily"`` or ``"hourly"``.
                Omitted from the request when ``None``.
            timezone: Optional IANA timezone name.
            profile_id: Optional profile ID to scope the results to devices
                on a single profile. Omitted from the request when ``None``.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is supplied and invalid.
            EeroAPIException: If the API returns an error.
        """
        extra_params = {"profile_id": profile_id} if profile_id is not None else None
        return await self._get_usage(
            "devices",
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            timezone=timezone,
            extra_params=extra_params,
        )

    async def get_device_usage(
        self,
        network_id: str,
        device_mac: str,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data usage for a single device - returns raw Eero API response.

        The API requires ``start``, ``end``, and ``cadence`` as query
        parameters on this endpoint.

        Args:
            network_id: ID of the network to get usage from.
            device_mac: MAC address of the device to query.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size for the returned series, ``"daily"`` or
                ``"hourly"``.
            timezone: Optional IANA timezone name.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        return await self._get_usage(
            f"devices/{device_mac}",
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            timezone=timezone,
            cadence_required=True,
        )

    async def get_eeros_summary(
        self,
        network_id: str,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a summary of data usage across all Eero devices - returns raw Eero API response.

        The API requires ``start``, ``end``, and ``cadence`` as query
        parameters on this endpoint.

        Args:
            network_id: ID of the network to get usage from.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size for the returned series, ``"daily"`` or
                ``"hourly"``.
            timezone: Optional IANA timezone name.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        return await self._get_usage(
            "eeros/summary",
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            timezone=timezone,
            cadence_required=True,
        )

    async def get_eero_usage(
        self,
        network_id: str,
        eero_id: str,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data usage for a single Eero device - returns raw Eero API response.

        The API requires ``start``, ``end``, and ``cadence`` as query
        parameters on this endpoint.

        Args:
            network_id: ID of the network to get usage from.
            eero_id: ID of the Eero device to query.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size for the returned series, ``"daily"`` or
                ``"hourly"``.
            timezone: Optional IANA timezone name.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        return await self._get_usage(
            f"eeros/{eero_id}",
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            timezone=timezone,
            cadence_required=True,
        )

    async def get_profile_usage(
        self,
        network_id: str,
        profile_id: str,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data usage for a single profile - returns raw Eero API response.

        The API requires ``start``, ``end``, and ``cadence`` as query
        parameters on this endpoint.

        Args:
            network_id: ID of the network to get usage from.
            profile_id: ID of the profile to query.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size for the returned series, ``"daily"`` or
                ``"hourly"``.
            timezone: Optional IANA timezone name.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        return await self._get_usage(
            f"profiles/{profile_id}",
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            timezone=timezone,
            cadence_required=True,
        )

    async def get_unprofiled_devices(
        self,
        network_id: str,
        *,
        start: str,
        end: str,
        cadence: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data usage for devices not assigned to a profile - returns raw Eero API response.

        Args:
            network_id: ID of the network to get usage from.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Optional bucket size, ``"daily"`` or ``"hourly"``.
                Omitted from the request when ``None``.
            timezone: Optional IANA timezone name.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is supplied and invalid.
            EeroAPIException: If the API returns an error.
        """
        return await self._get_usage(
            "unprofiled/devices",
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            timezone=timezone,
        )

    async def get_unprofiled_summary(
        self,
        network_id: str,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a summary of data usage for unprofiled devices - returns raw Eero API response.

        The API requires ``start``, ``end``, and ``cadence`` as query
        parameters on this endpoint.

        Args:
            network_id: ID of the network to get usage from.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size for the returned series, ``"daily"`` or
                ``"hourly"``.
            timezone: Optional IANA timezone name.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        return await self._get_usage(
            "unprofiled/summary",
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            timezone=timezone,
            cadence_required=True,
        )

    async def get_report_settings(self, network_id: str) -> Dict[str, Any]:
        """Get the data usage report settings for a network - returns raw Eero API response.

        Args:
            network_id: ID of the network.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting data usage report settings for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/data_usage/report_settings",
            auth_token=auth_token,
        )

    async def set_report_settings(
        self,
        network_id: str,
        *,
        cadence: str,
        notification_day: str,
    ) -> Dict[str, Any]:
        """Set the data usage report settings for a network - returns raw Eero API response.

        .. warning::
            This write has not been verified against a live network: its
            side effects beyond the documented request/response shape are
            uncharacterised. Follow the read-compare-skip discipline used
            for every other write in this SDK -- call `get_report_settings`
            first and only issue this write when the stored configuration
            differs from the desired one. Do not retry on failure; a retry
            of an unverified write compounds the uncertainty rather than
            resolving it.

        Args:
            network_id: ID of the network.
            cadence: Report cadence, ``"daily"`` or ``"hourly"``.
            notification_day: Day value for the report notification, as
                accepted by the API (forwarded unchanged; the SDK does not
                interpret or validate its format).

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        _validate_cadence(cadence)

        _LOGGER.warning(
            "Writing data usage report settings for network %s — this write's "
            "side effects have not been characterised against a live network; "
            "verify with get_report_settings before and after",
            network_id,
        )

        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload = {"cadence": cadence, "notification_day": notification_day}
        return await self.put(
            f"networks/{network_id}/data_usage/report_settings",
            auth_token=auth_token,
            json=payload,
        )
