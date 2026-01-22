"""Backup Network API for Eero (Eero Plus feature).

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
from typing import Any, Dict, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class BackupAPI(AuthenticatedAPI):
    """Backup Network API for Eero.

    Note: Backup network features require an active Eero Plus/Eero Secure subscription.
    This allows using a mobile phone as a backup internet connection when the
    primary connection fails.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BackupAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_backup_network(self, network_id: str) -> Dict[str, Any]:
        """Get backup network configuration - returns raw Eero API response.

        Args:
            network_id: ID of the network

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting backup network settings for network %s", network_id)
        return await self.get(f"networks/{network_id}/backup", auth_token=auth_token)

    async def get_backup_status(self, network_id: str) -> Dict[str, Any]:
        """Get current backup network status - returns raw Eero API response.

        Args:
            network_id: ID of the network

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting backup status for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/backup/status",
            auth_token=auth_token,
        )

    async def set_backup_network(
        self,
        network_id: str,
        enabled: bool,
    ) -> Dict[str, Any]:
        """Enable or disable backup network - returns raw Eero API response.

        Args:
            network_id: ID of the network
            enabled: True to enable, False to disable

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(
            "%s backup network for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        return await self.put(
            f"networks/{network_id}/backup",
            auth_token=auth_token,
            json={"enabled": enabled},
        )

    async def configure_backup_network(
        self,
        network_id: str,
        enabled: Optional[bool] = None,
        phone_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Configure backup network settings - returns raw Eero API response.

        Args:
            network_id: ID of the network
            enabled: True to enable, False to disable
            phone_number: Phone number to use for backup connection

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {}

        if enabled is not None:
            payload["enabled"] = enabled

        if phone_number is not None:
            payload["phone_number"] = phone_number

        if not payload:
            _LOGGER.warning("No backup network settings provided")
            return {"meta": {"code": 400}, "data": {}}

        _LOGGER.debug("Configuring backup network for network %s: %s", network_id, payload)

        return await self.put(
            f"networks/{network_id}/backup",
            auth_token=auth_token,
            json=payload,
        )
