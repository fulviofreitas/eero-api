"""SQM/QoS API for Eero (Smart Queue Management).

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


class SqmAPI(AuthenticatedAPI):
    """SQM/QoS API for Eero.

    Manages Smart Queue Management (SQM) settings for traffic
    optimization and Quality of Service (QoS) configuration.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the SqmAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_sqm_settings(self, network_id: str) -> Dict[str, Any]:
        """Get SQM/QoS settings for a network - returns raw Eero API response.

        SQM settings are included in the network data. Look for fields like:
        sqm, bandwidth_control, qos, etc.

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

        _LOGGER.debug("Getting SQM settings for network %s", network_id)
        return await self.get(f"networks/{network_id}", auth_token=auth_token)

    async def set_sqm_enabled(self, network_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable SQM (Smart Queue Management) - returns raw Eero API response.

        Args:
            network_id: ID of the network
            enabled: True to enable SQM, False to disable

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
            "%s SQM for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"sqm": {"enabled": enabled}},
        )

    async def set_sqm_bandwidth(
        self,
        network_id: str,
        upload_mbps: Optional[int] = None,
        download_mbps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Set SQM bandwidth limits - returns raw Eero API response.

        Args:
            network_id: ID of the network
            upload_mbps: Upload bandwidth limit in Mbps
            download_mbps: Download bandwidth limit in Mbps

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        sqm_payload: Dict[str, Any] = {"enabled": True}

        if upload_mbps is not None:
            sqm_payload["upload_bandwidth"] = upload_mbps

        if download_mbps is not None:
            sqm_payload["download_bandwidth"] = download_mbps

        _LOGGER.debug(
            "Setting SQM bandwidth for network %s: up=%s, down=%s",
            network_id,
            upload_mbps,
            download_mbps,
        )

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"sqm": sqm_payload},
        )

    async def configure_sqm(
        self,
        network_id: str,
        enabled: bool,
        upload_mbps: Optional[int] = None,
        download_mbps: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Configure SQM settings in one call - returns raw Eero API response.

        Args:
            network_id: ID of the network
            enabled: True to enable SQM, False to disable
            upload_mbps: Upload bandwidth limit in Mbps
            download_mbps: Download bandwidth limit in Mbps

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        sqm_payload: Dict[str, Any] = {"enabled": enabled}

        if enabled:
            if upload_mbps is not None:
                sqm_payload["upload_bandwidth"] = upload_mbps
            if download_mbps is not None:
                sqm_payload["download_bandwidth"] = download_mbps

        _LOGGER.debug("Configuring SQM for network %s: %s", network_id, sqm_payload)

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"sqm": sqm_payload},
        )

    async def set_sqm_auto(self, network_id: str) -> Dict[str, Any]:
        """Set SQM to automatic mode (auto-detect bandwidth) - returns raw Eero API response.

        Args:
            network_id: ID of the network

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting SQM to auto mode for network %s", network_id)

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"sqm": {"enabled": True, "mode": "auto"}},
        )
