"""Transfer Stats API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ._writes import as_envelope
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url, sub_resource_url

_LOGGER = logging.getLogger(__name__)


class TransferAPI(AuthenticatedAPI):
    """Transfer Stats API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the TransferAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_transfer_stats(
        self,
        network_id: str,
        device_id: Optional[str] = None,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get transfer statistics - returns raw Eero API response.

        With no ``device_id``, GETs the network's ``transfer`` link. With a
        ``device_id``, GETs the literal per-device transfer path (not a
        published link).

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            device_id: Optional device ID to get stats for.
            parent: The network's own cached envelope, if the caller has
                one; used only when ``device_id`` is omitted, to prefer the
                network's published ``transfer`` link. Read only; never
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

        if device_id:
            _LOGGER.debug(
                "Getting transfer stats for device %s in network %s",
                device_id,
                network_id,
            )
            url = resource_url(network_id, f"networks/{{id}}/devices/{device_id}/transfer")
        else:
            _LOGGER.debug("Getting transfer stats for network %s", network_id)
            url = sub_resource_url(
                network_id,
                "networks/{id}/transfer",
                link="transfer",
                parent=as_envelope(parent),
            )

        return await self.get(url, auth_token=auth_token)
