"""Support API for Eero.

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
from .links import sub_resource_url

_LOGGER = logging.getLogger(__name__)


class SupportAPI(AuthenticatedAPI):
    """Support API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the SupportAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_support(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get support information - returns raw Eero API response.

        GETs the network's ``support`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``support`` link is used
                instead of the default template. Read only; never mutated.

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
            network_id, "networks/{id}/support", link="support", parent=as_envelope(parent)
        )
        _LOGGER.debug("Getting support info for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def request_support(
        self,
        network_id: str,
        request_data: Dict[str, Any],
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Request support - returns raw Eero API response.

        POSTs to the network's ``support`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            request_data: Support request data, forwarded to the API
                unchanged.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``support`` link is used
                instead of the default template. Read only; never mutated.

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
            network_id, "networks/{id}/support", link="support", parent=as_envelope(parent)
        )
        _LOGGER.debug("Requesting support for network %s", network_id)
        return await self.post(
            url,
            auth_token=auth_token,
            json=request_data,
        )
