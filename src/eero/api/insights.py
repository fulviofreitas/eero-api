"""Insights API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

In addition to the network-level `get_insights`, the API serves insights
series scoped to a single device or profile (and their collections) at
``networks/{id}/insights/devices``, ``.../insights/devices/{mac}``,
``.../insights/profiles``, ``.../insights/profiles/{profile}``, and
``.../insights/profiles/{profile}/devices``. All are live-verified reads
that take ``start``, ``end``, ``cadence`` (``daily``/``hourly``), and
``insight_type`` as query parameters.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._params import resolve_nested_url, resolve_network_url, validate_cadence
from ._writes import as_envelope
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import sub_resource_url

_LOGGER = get_secure_logger(__name__)

# Valid values for the `cadence` query parameter on GET /insights: the API
# accepts the same two buckets as every other insights and data-usage read.
INSIGHTS_CADENCES = ("hourly", "daily")


def _insights_params(*, start: str, end: str, cadence: str, insight_type: str) -> Dict[str, str]:
    """Build the common query-parameter set for a device/profile insights read.

    Args:
        start: Window start, ISO 8601 timestamp.
        end: Window end, ISO 8601 timestamp.
        cadence: Bucket size, validated as ``"daily"`` or ``"hourly"``.
        insight_type: Category to query, forwarded unchanged.

    Returns:
        The query-parameter dict.

    Raises:
        EeroValidationException: If ``cadence`` is not ``"daily"`` or
            ``"hourly"``.
    """
    return {
        "start": start,
        "end": end,
        "cadence": validate_cadence(cadence),
        "insight_type": insight_type,
    }


class InsightsAPI(AuthenticatedAPI):
    """Insights API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the InsightsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_insights(
        self,
        network_id: str,
        *,
        start: str,
        end: str,
        insight_type: str,
        cadence: str = "daily",
    ) -> Dict[str, Any]:
        """Query insights time-series data — returns raw Eero API response.

        The Eero cloud API requires four query parameters on this endpoint;
        omitting any of ``start``, ``end``, ``insight_type``, or ``cadence``
        yields a 400 "error.form.errors" response. The SDK forwards the values
        as-is and returns the raw JSON envelope unchanged.

        Response shape (envelope):

        ::

            {
              "meta": {...},
              "data": {
                "network_id": <int>,
                "start": <iso8601>,
                "end": <iso8601>,
                "limit": <iso8601>,
                "series": [
                  {"insight_type": <str>, "sum": <int>, "values": [{"time": ..., "value": ...}, ...]},
                  ...
                ]
              }
            }

        Args:
            network_id: ID of the network to query.
            start: Window start, ISO 8601 timestamp (e.g. ``"2026-07-21T00:00:00Z"``).
            end: Window end, ISO 8601 timestamp.
            insight_type: Category to query. Live-observed valid inputs:
                ``"adblock"``, ``"blocked"``, ``"inspected"``. The server may
                emit additional types (e.g. ``"malware"``, ``"botnet"``) inside
                the response ``series`` array when ``insight_type="blocked"``.
            cadence: Bucket size for the returned series. One of
                ``"hourly"`` or ``"daily"`` (the API requires it). Defaults
                to ``"daily"``. This is the only parameter with an
                SDK-supplied default; it controls display bucketing, not
                data scope.

        Returns:
            Raw API response: ``{"meta": {...}, "data": {...}}``.

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not one of
                :data:`INSIGHTS_CADENCES`.
            EeroAPIException: If the API returns an error (400 on invalid
                params, 403 on insufficient subscription, etc.).
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        params = {
            "start": start,
            "end": end,
            "cadence": validate_cadence(cadence, allowed=INSIGHTS_CADENCES),
            "insight_type": insight_type,
        }
        _LOGGER.debug(
            "Getting insights for network %s: insight_type=%s cadence=%s window=%s..%s",
            network_id,
            insight_type,
            cadence,
            start,
            end,
        )
        url = resolve_network_url(network_id)
        return await self.get(
            f"{url}/insights",
            auth_token=auth_token,
            params=params,
        )

    async def get_devices_insights(
        self,
        network: str,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Query insights series for every device on a network — raw response.

        Args:
            network: ID of the network to query.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size, ``"daily"`` or ``"hourly"``.
            insight_type: Category to query, forwarded unchanged.
            parent: The cached network envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network,
            "networks/{id}/insights/devices",
            link="insights_devices",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        params = _insights_params(start=start, end=end, cadence=cadence, insight_type=insight_type)
        _LOGGER.debug("Getting devices insights for network %s", network)
        return await self.get(url, auth_token=auth_token, params=params)

    async def get_device_insights(
        self,
        network: str,
        mac: str,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
    ) -> Dict[str, Any]:
        """Query the insights series for a single device — raw response.

        Args:
            network: ID of the network the device belongs to.
            mac: The device's bare MAC, path, or absolute URL.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size, ``"daily"`` or ``"hourly"``.
            insight_type: Category to query, forwarded unchanged.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resolve_nested_url(network, mac, prefix="insights/devices")
        params = _insights_params(start=start, end=end, cadence=cadence, insight_type=insight_type)
        _LOGGER.debug("Getting insights for device %s in network %s", mac, network)
        return await self.get(url, auth_token=auth_token, params=params)

    async def get_profiles_insights(
        self,
        network: str,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Query insights series for every profile on a network — raw response.

        Args:
            network: ID of the network to query.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size, ``"daily"`` or ``"hourly"``.
            insight_type: Category to query, forwarded unchanged.
            parent: The cached network envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network,
            "networks/{id}/insights/profiles",
            link="insights_profiles",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        params = _insights_params(start=start, end=end, cadence=cadence, insight_type=insight_type)
        _LOGGER.debug("Getting profiles insights for network %s", network)
        return await self.get(url, auth_token=auth_token, params=params)

    async def get_profile_insights(
        self,
        network: str,
        profile: str,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
    ) -> Dict[str, Any]:
        """Query the insights series for a single profile — raw response.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size, ``"daily"`` or ``"hourly"``.
            insight_type: Category to query, forwarded unchanged.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resolve_nested_url(network, profile, prefix="insights/profiles")
        params = _insights_params(start=start, end=end, cadence=cadence, insight_type=insight_type)
        _LOGGER.debug("Getting insights for profile %s in network %s", profile, network)
        return await self.get(url, auth_token=auth_token, params=params)

    async def get_profile_devices_insights(
        self,
        network: str,
        profile: str,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
    ) -> Dict[str, Any]:
        """Query insights series for the devices assigned to a profile — raw response.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size, ``"daily"`` or ``"hourly"``.
            insight_type: Category to query, forwarded unchanged.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``cadence`` is not a valid value.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resolve_nested_url(network, profile, prefix="insights/profiles", suffix="/devices")
        params = _insights_params(start=start, end=end, cadence=cadence, insight_type=insight_type)
        _LOGGER.debug("Getting devices insights for profile %s in network %s", profile, network)
        return await self.get(url, auth_token=auth_token, params=params)
