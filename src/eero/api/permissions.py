"""Permissions API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._params import resolve_network_url
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = get_secure_logger(__name__)


class PermissionsAPI(AuthenticatedAPI):
    """Permissions API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the PermissionsAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_permissions(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get the caller's permissions on a network -- returns raw Eero API response.

        Operation: GET ``networks/{id}/permissions``. Returns
        ``permissions`` (a per-capability mapping) and ``role``.

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

        url = f"{resolve_network_url(network_id, parent)}/permissions"
        _LOGGER.debug("Getting permissions for network %s", network_id)
        return await self.get(url, auth_token=auth_token)


__all__ = ["PermissionsAPI"]
