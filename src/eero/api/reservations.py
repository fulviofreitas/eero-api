"""DHCP Reservations API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

A reservation's body has exactly four fields: ``description``, ``ip``,
``mac``, ``public_static_ip`` (plus its own ``url``). This module passes
bodies through unchanged -- it does not validate or default any of these
fields.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._writes import as_envelope
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url, self_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Template for a single reservation resource on the default API version.
_RESERVATION_TEMPLATE = "networks/{network}/reservations/{{id}}"


def _resolve_reservation_url(reservation: Any, network: Optional[str] = None) -> str:
    """Resolve a reservation's own URL from a URL, path, bare ID, or envelope.

    Args:
        reservation: Either the reservation's bare ID (requires
            ``network``), a path/absolute URL as previously returned by the
            API, or the reservation's own cached envelope (full or
            ``data``).
        network: ID of the network the reservation belongs to. Required
            only when ``reservation`` is a bare ID.

    Returns:
        The absolute URL of the reservation resource.

    Raises:
        EeroValidationException: If ``reservation`` is a mapping with no
            resolvable ``url`` field, a bare ID given without ``network``,
            or neither a string nor a mapping.
    """
    if isinstance(reservation, Mapping):
        envelope = as_envelope(reservation)
        url = self_url(envelope) if envelope is not None else None
        if url is None:
            raise EeroValidationException("reservation", "envelope has no resolvable 'url' field")
        return url
    if isinstance(reservation, str):
        if reservation.startswith(("http://", "https://", "/")):
            return resource_url(reservation, "{id}")
        if network is None:
            raise EeroValidationException(
                "network", "required when 'reservation' is a bare ID rather than a path/URL"
            )
        return resource_url(reservation, _RESERVATION_TEMPLATE.format(network=network))
    raise EeroValidationException(
        "reservation",
        "must be a bare ID, a URL/path string, or a reservation envelope (mapping)",
    )


class ReservationsAPI(AuthenticatedAPI):
    """DHCP Reservations API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ReservationsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_reservations(
        self, network: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get DHCP reservations - returns raw Eero API response.

        Args:
            network: ID of the network to get reservations from.
            parent: The cached network envelope, if the caller has one.
                Preferred over ``network`` to resolve the ``reservations``
                link when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network,
            "networks/{id}/reservations",
            link="reservations",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        _LOGGER.debug("Getting reservations for network %s", network)
        return await self.get(url, auth_token=auth_token)

    async def create_reservation(
        self,
        network: str,
        reservation_data: Dict[str, Any],
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a DHCP reservation - returns raw Eero API response.

        Args:
            network: ID of the network.
            reservation_data: Reservation body, passed through unchanged.
                The API's declared fields are ``description``, ``ip``,
                ``mac``, ``public_static_ip``.
            parent: The cached network envelope, if the caller has one.
                Preferred over ``network`` to resolve the ``reservations``
                link when supplied.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network,
            "networks/{id}/reservations",
            link="reservations",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        _LOGGER.debug("Creating reservation for network %s: %s", network, sorted(reservation_data))
        return await self.post(url, auth_token=auth_token, json=reservation_data)

    async def update_reservation(
        self,
        reservation: Any,
        data: Dict[str, Any],
        *,
        network: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a DHCP reservation via its own URL - returns raw Eero API response.

        Args:
            reservation: The reservation's bare ID (requires ``network``),
                its own path/absolute URL, or its cached envelope.
            data: Reservation body, passed through unchanged.
            network: ID of the network the reservation belongs to. Required
                only when ``reservation`` is a bare ID.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``reservation`` cannot be resolved to a URL
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = _resolve_reservation_url(reservation, network)
        _LOGGER.debug("Updating reservation at %s: %s", url, sorted(data))
        return await self.put(url, auth_token=auth_token, json=data)

    async def delete_reservation(
        self,
        network: str,
        reservation: str,
        *,
        delete_forwards: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Delete a DHCP reservation - returns raw Eero API response.

        Args:
            network: ID of the network.
            reservation: The reservation's bare ID, path, or absolute URL.
            delete_forwards: When supplied, sent as the query parameter
                ``delete_forwards=true``/``false`` to control whether port
                forwards referencing this reservation's IP are also
                deleted. Omitted from the request when ``None``.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(reservation, _RESERVATION_TEMPLATE.format(network=network))
        params: Optional[Dict[str, str]] = None
        if delete_forwards is not None:
            params = {"delete_forwards": "true" if delete_forwards else "false"}

        _LOGGER.debug("Deleting reservation %s for network %s", reservation, network)
        return await self.delete(url, auth_token=auth_token, params=params)
