"""Backup Internet API for Eero (Eero Plus feature).

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

Note: Backup internet features require an active Eero Plus/Eero Secure
subscription. This allows using a mobile phone as a backup internet
connection when the primary connection fails. The paths below are literal
-- they are not published as links on the network envelope -- so they are
built directly via `eero.api.links.resource_url`.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url

_LOGGER = get_secure_logger(__name__)


class BackupAPI(AuthenticatedAPI):
    """Backup Internet API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BackupAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_backup_internet(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get backup internet configuration - returns raw Eero API response.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: Unused; accepted for signature consistency with the rest
                of this family. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/backupinternet")
        _LOGGER.debug("Getting backup internet settings for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def set_backup_internet(
        self,
        network_id: str,
        enabled: bool,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Enable or disable backup internet - returns raw Eero API response.

        Issues a JSON PUT (``{"backup_internet_enabled": bool}``) to the
        literal backup internet path.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_backup_internet`
            first, and only issue this write when the stored value differs
            from the desired one.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable, False to disable.
            parent: Unused; accepted for signature consistency with the rest
                of this family. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/backupinternet")
        warn_uncharacterised_write(_LOGGER, "set backup internet for network")
        return await self.put(url, auth_token=auth_token, json={"backup_internet_enabled": enabled})

    async def get_cellular_backup_usage(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get cellular backup data usage - returns raw Eero API response.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: Unused; accepted for signature consistency with the rest
                of this family. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/cellular_backup_usage")
        _LOGGER.debug("Getting cellular backup usage for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def get_cellular_backup_events(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get cellular backup events - returns raw Eero API response.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: Unused; accepted for signature consistency with the rest
                of this family. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/cellular_backup_events")
        _LOGGER.debug("Getting cellular backup events for network %s", network_id)
        return await self.get(url, auth_token=auth_token)
