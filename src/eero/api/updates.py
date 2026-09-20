"""Updates API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI, RequestEncoding
from .links import sub_resource_url

_LOGGER = get_secure_logger(__name__)


class UpdatesAPI(AuthenticatedAPI):
    """Updates API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the UpdatesAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_updates(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get update information - returns raw Eero API response.

        GETs the network's ``updates`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``updates`` link is used
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
            network_id, "networks/{id}/updates", link="updates", parent=as_envelope(parent)
        )
        _LOGGER.debug("Getting updates for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def apply_update(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Apply a pending update - returns raw Eero API response.

        Issues a POST with the two-character body ``""`` to the network's
        ``updates`` link.

        .. warning::
            This is a reboot-class write: applying an update reboots every
            node on the network, and its request/response shape has not
            been confirmed against a live network. Follow the
            read-compare-skip discipline: read `get_updates` first, and only
            issue this write when an update is actually pending. Never
            retry on failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``updates`` link is used
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
            network_id, "networks/{id}/updates", link="updates", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(_LOGGER, "apply update for network — reboots every node")
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )
