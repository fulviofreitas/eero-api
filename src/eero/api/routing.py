"""Routing API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import sub_resource_url

_LOGGER = get_secure_logger(__name__)


class RoutingAPI(AuthenticatedAPI):
    """Routing API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the RoutingAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_routing(
        self, network: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get routing information - returns raw Eero API response.

        Args:
            network: ID of the network to get routing info from.
            parent: The cached network envelope, if the caller has one.
                Preferred over ``network`` to resolve the ``routing`` link
                when supplied -- the API serves this link on version 2.3,
                distinct from the 2.2 template fallback. Never mutated.

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
            "networks/{id}/routing",
            link="routing",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        _LOGGER.debug("Getting routing for network %s", network)
        return await self.get(url, auth_token=auth_token)
