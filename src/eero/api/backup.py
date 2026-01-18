"""Backup Network API for Eero (Eero Plus feature)."""

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
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BackupAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_backup_network(self, network_id: str) -> Dict[str, Any]:
        """Get backup network configuration.

        Args:
            network_id: ID of the network

        Returns:
            Dictionary containing backup network settings:
            - enabled: bool - Whether backup is enabled
            - status: str - Current status (active, standby, disabled)
            - phone_number: str - Associated phone number (if any)
            - last_used: str - When backup was last used
            - data_used: int - Data used in bytes

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting backup network settings for network %s", network_id)

        response = await self.get(
            f"networks/{network_id}/backup",
            auth_token=auth_token,
        )

        data = response.get("data", {})

        return {
            "enabled": data.get("enabled", False),
            "status": data.get("status", "disabled"),
            "phone_number": data.get("phone_number"),
            "last_used": data.get("last_used"),
            "data_used": data.get("data_used", 0),
            "connection_type": data.get("connection_type"),
            "provider": data.get("provider"),
        }

    async def get_backup_status(self, network_id: str) -> Dict[str, Any]:
        """Get current backup network status.

        Args:
            network_id: ID of the network

        Returns:
            Dictionary containing current backup status:
            - active: bool - Whether backup is currently active
            - connected: bool - Whether backup connection is established
            - signal_strength: int - Signal strength (if available)
            - connection_type: str - Type of backup connection

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting backup status for network %s", network_id)

        response = await self.get(
            f"networks/{network_id}/backup/status",
            auth_token=auth_token,
        )

        data = response.get("data", {})

        return {
            "active": data.get("active", False),
            "connected": data.get("connected", False),
            "signal_strength": data.get("signal_strength"),
            "connection_type": data.get("connection_type"),
            "using_backup": data.get("using_backup", False),
        }

    async def set_backup_network(
        self,
        network_id: str,
        enabled: bool,
    ) -> bool:
        """Enable or disable backup network.

        Args:
            network_id: ID of the network
            enabled: True to enable, False to disable

        Returns:
            True if the operation was successful

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

        response = await self.put(
            f"networks/{network_id}/backup",
            auth_token=auth_token,
            json={"enabled": enabled},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def configure_backup_network(
        self,
        network_id: str,
        enabled: Optional[bool] = None,
        phone_number: Optional[str] = None,
    ) -> bool:
        """Configure backup network settings.

        Args:
            network_id: ID of the network
            enabled: True to enable, False to disable
            phone_number: Phone number to use for backup connection

        Returns:
            True if the operation was successful

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
            return False

        _LOGGER.debug("Configuring backup network for network %s: %s", network_id, payload)

        response = await self.put(
            f"networks/{network_id}/backup",
            auth_token=auth_token,
            json=payload,
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def is_using_backup(self, network_id: str) -> bool:
        """Check if the network is currently using backup connection.

        Args:
            network_id: ID of the network

        Returns:
            True if backup connection is currently active

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        status = await self.get_backup_status(network_id)
        return status.get("using_backup", False) or status.get("active", False)
