"""Port Forwards API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

A forward's body has exactly six fields: ``client_port``, ``description``,
``enabled``, ``gateway_port``, ``ip``, ``protocol`` (plus its own ``url``).
This module passes bodies through unchanged -- it does not validate or
default any of these fields.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url, self_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Template for a single forward resource on the default API version.
_FORWARD_TEMPLATE = "networks/{network}/forwards/{{id}}"


def _resolve_forward_url(forward: Any, network: Optional[str] = None) -> str:
    """Resolve a forward's own URL from a URL, path, bare ID, or envelope.

    Args:
        forward: Either the forward's bare ID (requires ``network``), a
            path/absolute URL as previously returned by the API, or the
            forward's own cached envelope (full or ``data``).
        network: ID of the network the forward belongs to. Required only
            when ``forward`` is a bare ID rather than a path/URL/envelope.

    Returns:
        The absolute URL of the forward resource.

    Raises:
        EeroValidationException: If ``forward`` is a mapping with no
            resolvable ``url`` field, a bare ID given without ``network``,
            or neither a string nor a mapping.
    """
    if isinstance(forward, Mapping):
        envelope = as_envelope(forward)
        url = self_url(envelope) if envelope is not None else None
        if url is None:
            raise EeroValidationException("forward", "envelope has no resolvable 'url' field")
        return url
    if isinstance(forward, str):
        if forward.startswith(("http://", "https://", "/")):
            return resource_url(forward, "{id}")
        if network is None:
            raise EeroValidationException(
                "network", "required when 'forward' is a bare ID rather than a path/URL"
            )
        return resource_url(forward, _FORWARD_TEMPLATE.format(network=network))
    raise EeroValidationException(
        "forward", "must be a bare ID, a URL/path string, or a forward envelope (mapping)"
    )


class ForwardsAPI(AuthenticatedAPI):
    """Port Forwards API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ForwardsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_forwards(
        self, network: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get port forwards - returns raw Eero API response.

        Args:
            network: ID of the network to get forwards from.
            parent: The cached network envelope, if the caller has one.
                Preferred over ``network`` to resolve the ``forwards`` link
                when supplied -- the link may point at a newer API version
                than the template fallback. Never mutated.

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
            "networks/{id}/forwards",
            link="forwards",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        _LOGGER.debug("Getting forwards for network %s", network)
        return await self.get(url, auth_token=auth_token)

    async def create_forward(
        self,
        network: str,
        forward_data: Dict[str, Any],
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a port forward - returns raw Eero API response.

        Args:
            network: ID of the network.
            forward_data: Forward body, passed through unchanged. The API's
                declared fields are ``client_port``, ``description``,
                ``enabled``, ``gateway_port``, ``ip``, ``protocol``.
            parent: The cached network envelope, if the caller has one.
                Preferred over ``network`` to resolve the ``forwards`` link
                when supplied.

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
            "networks/{id}/forwards",
            link="forwards",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        warn_uncharacterised_write(_LOGGER, "create forward for network")
        _LOGGER.debug("Creating forward for network %s: %s", network, sorted(forward_data))
        return await self.post(url, auth_token=auth_token, json=forward_data)

    async def update_forward(
        self,
        forward: Any,
        data: Dict[str, Any],
        *,
        network: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a port forward via its own URL - returns raw Eero API response.

        Args:
            forward: The forward's bare ID (requires ``network``), its own
                path/absolute URL, or its cached envelope.
            data: Forward body, passed through unchanged.
            network: ID of the network the forward belongs to. Required
                only when ``forward`` is a bare ID.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``forward`` cannot be resolved to a URL
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = _resolve_forward_url(forward, network)
        warn_uncharacterised_write(_LOGGER, "update_forward")
        _LOGGER.debug("Updating forward at %s: %s", url, sorted(data))
        return await self.put(url, auth_token=auth_token, json=data)

    async def delete_forward(self, network: str, forward: str) -> Dict[str, Any]:
        """Delete a port forward - returns raw Eero API response.

        Args:
            network: ID of the network.
            forward: The forward's bare ID, path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(forward, _FORWARD_TEMPLATE.format(network=network))
        warn_uncharacterised_write(_LOGGER, "delete forward for network")
        _LOGGER.debug("Deleting forward %s for network %s", forward, network)
        return await self.delete(url, auth_token=auth_token)
