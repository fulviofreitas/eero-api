"""Burst Reporters API for Eero.

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


class BurstReportersAPI(AuthenticatedAPI):
    """Burst Reporters API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BurstReportersAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def create_burst_reporter(
        self,
        network_id: str,
        reporter_data: Dict[str, Any],
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a burst reporter - returns raw Eero API response.

        POSTs to the network's ``burst_reporters`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            reporter_data: Burst reporter data, forwarded to the API
                unchanged.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``burst_reporters`` link
                is used instead of the default template. Read only; never
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
            "networks/{id}/burst_reporters",
            link="burst_reporters",
            parent=as_envelope(parent),
        )
        _LOGGER.debug("Creating burst reporter for network %s: %s", network_id, reporter_data)
        return await self.post(
            url,
            auth_token=auth_token,
            json=reporter_data,
        )
