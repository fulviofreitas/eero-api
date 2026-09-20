"""Dynamic DNS (DDNS) enable/disable API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.

Both operations are parameterless PUTs: the API declares no request body
for either endpoint, so neither method sends one -- no JSON, form, or
empty-JSON-string carrier. See `eero.api.base.RequestEncoding.NONE`.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import sub_resource_url

_LOGGER = get_secure_logger(__name__)


class DdnsAPI(AuthenticatedAPI):
    """Dynamic DNS (DDNS) enable/disable API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DdnsAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def enable(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enable dynamic DNS for a network - returns raw Eero API response.

        Issues a PUT with no request body to the network's ``ddns/enable``
        sub-resource -- the API declares no fields for this endpoint.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read the network envelope's
            ``ddns`` field (`eero.api.networks.NetworksAPI.get_network`)
            first, and skip the write when DDNS is already enabled. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``ddns/enable`` link is
                used instead of the default template. Read only; never
                mutated.

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
            network_id,
            "networks/{id}/ddns/enable",
            link="ddns_enable",
            parent=as_envelope(parent),
        )
        warn_uncharacterised_write(_LOGGER, "enable DDNS for network")
        return await self.put(url, auth_token=auth_token)

    async def disable(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Disable dynamic DNS for a network - returns raw Eero API response.

        Issues a PUT with no request body to the network's ``ddns/disable``
        sub-resource -- the API declares no fields for this endpoint.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read the network envelope's
            ``ddns`` field (`eero.api.networks.NetworksAPI.get_network`)
            first, and skip the write when DDNS is already disabled. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``ddns/disable`` link is
                used instead of the default template. Read only; never
                mutated.

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
            network_id,
            "networks/{id}/ddns/disable",
            link="ddns_disable",
            parent=as_envelope(parent),
        )
        warn_uncharacterised_write(_LOGGER, "disable DDNS for network")
        return await self.put(url, auth_token=auth_token)
