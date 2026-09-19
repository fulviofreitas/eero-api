"""Events API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._params import resolve_network_url
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = get_secure_logger(__name__)

#: Valid values for the `band` query parameter on GET .../channel_utilization.
CHANNEL_UTILIZATION_BANDS = (
    "band_2_4GHz",
    "band_5GHz_low",
    "band_5GHz_high",
    "band_5GHz_full",
    "band_6GHz",
)


def _validate_band(value: str) -> str:
    """Validate a `band` value against the API's declared enum.

    Args:
        value: Candidate band value.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        EeroValidationException: If ``value`` is not one of
            :data:`CHANNEL_UTILIZATION_BANDS`.
    """
    if value not in CHANNEL_UTILIZATION_BANDS:
        raise EeroValidationException(
            "band",
            f"must be one of {CHANNEL_UTILIZATION_BANDS}, got {value!r}",
        )
    return value


def _validate_positive_int(field: str, value: int) -> int:
    """Validate that a query parameter is a positive integer.

    The API rejects string-typed values for these parameters, so callers
    must supply a real ``int``; ``bool`` is rejected too since it is an
    ``int`` subclass but never a meaningful value here.

    Args:
        field: The parameter name, used only for the error message.
        value: The candidate value.

    Returns:
        ``value`` unchanged, once validated.

    Raises:
        EeroValidationException: If ``value`` is not a positive ``int``.
    """
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise EeroValidationException(field, f"must be a positive integer, got {value!r}")
    return value


class EventsAPI(AuthenticatedAPI):
    """Events API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the EventsAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_app_events(
        self,
        network_id: str,
        *,
        page_size: Optional[int] = None,
        timestamp: Optional[str] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get the network's app events -- returns raw Eero API response.

        Operation: GET ``networks/{id}/app_events`` with the optional query
        parameters ``page_size`` and ``timestamp``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            page_size: Optional page size, sent as the ``page_size`` query
                parameter. Omitted from the request when ``None``.
            timestamp: Optional pagination cursor, sent as the ``timestamp``
                query parameter. Omitted from the request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one. Preferred over `network_id` to resolve the base URL
                when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{resolve_network_url(network_id, parent)}/app_events"
        params: Dict[str, str] = {}
        if page_size is not None:
            params["page_size"] = str(page_size)
        if timestamp is not None:
            params["timestamp"] = timestamp

        _LOGGER.debug("Getting app events for network %s", network_id)
        return await self.get(url, auth_token=auth_token, params=params)

    async def get_network_scan(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get the network's channel/neighbour scan -- returns raw Eero API response.

        Operation: GET ``networks/{id}/network_scan``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one. Preferred over `network_id` to resolve the base URL
                when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{resolve_network_url(network_id, parent)}/network_scan"
        _LOGGER.debug("Getting network scan for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def get_channel_utilization(
        self,
        network_id: str,
        *,
        start: str,
        end: str,
        busy_threshold: Optional[int] = None,
        eero_id: Optional[int] = None,
        band: Optional[str] = None,
        granularity: Optional[int] = None,
        gap_data_placeholder: Optional[int] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get channel utilization data -- returns raw Eero API response.

        Operation: GET ``networks/{id}/channel_utilization``. ``start`` and
        ``end`` are required; the remaining parameters follow the API's
        declared shape and were live-verified with only ``start``/``end``
        supplied.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            start: Window start, sent as the ``start`` query parameter.
            end: Window end, sent as the ``end`` query parameter.
            busy_threshold: Optional integer threshold, sent as the
                ``busy_threshold`` query parameter. Omitted when ``None``.
            eero_id: Optional integer eero node ID, sent as the ``eero_id``
                query parameter. Omitted when ``None``.
            band: Optional band, one of
                :data:`CHANNEL_UTILIZATION_BANDS`, sent as the ``band``
                query parameter. Omitted when ``None``.
            granularity: Optional integer minutes-per-sample, sent as the
                ``granularity`` query parameter. Must be a positive integer
                -- the API rejects strings. Omitted when ``None``.
            gap_data_placeholder: Optional integer, sent as the
                ``gap_data_placeholder`` query parameter. The reference
                client always sends ``-1``. Omitted when ``None``.
            parent: The network's own cached envelope, if the caller has
                one. Preferred over `network_id` to resolve the base URL
                when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``band`` is not a valid value, or
                ``granularity``/``busy_threshold`` is not a positive
                integer.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{resolve_network_url(network_id, parent)}/channel_utilization"
        params: Dict[str, str] = {"start": start, "end": end}
        if busy_threshold is not None:
            params["busy_threshold"] = str(_validate_positive_int("busy_threshold", busy_threshold))
        if eero_id is not None:
            params["eero_id"] = str(eero_id)
        if band is not None:
            params["band"] = _validate_band(band)
        if granularity is not None:
            params["granularity"] = str(_validate_positive_int("granularity", granularity))
        if gap_data_placeholder is not None:
            params["gap_data_placeholder"] = str(gap_data_placeholder)

        _LOGGER.debug("Getting channel utilization for network %s", network_id)
        return await self.get(url, auth_token=auth_token, params=params)


__all__ = ["CHANNEL_UTILIZATION_BANDS", "EventsAPI"]
