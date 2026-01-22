"""Security Settings API for Eero.

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


class SecurityAPI(AuthenticatedAPI):
    """Security Settings API for Eero.

    Manages security-related network settings including WPA3,
    band steering, UPnP, and firewall settings.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the SecurityAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_security_settings(self, network_id: str) -> Dict[str, Any]:
        """Get security settings for a network - returns raw Eero API response.

        Security settings are included in the network data. Look for fields like:
        wpa3, band_steering, upnp, ipv6_upstream, ipv6_downstream, thread, etc.

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

        _LOGGER.debug("Getting security settings for network %s", network_id)
        return await self.get(f"networks/{network_id}", auth_token=auth_token)

    async def set_wpa3(self, network_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable WPA3 encryption - returns raw Eero API response.

        Note: This may require a network restart to take effect.
        Not all devices support WPA3 - older devices may lose connectivity.

        Args:
            network_id: ID of the network
            enabled: True to enable WPA3, False to use WPA2

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
            "%s WPA3 for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"wpa3": enabled},
        )

    async def set_band_steering(self, network_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable band steering - returns raw Eero API response.

        Band steering automatically moves devices to the optimal
        frequency band (2.4GHz or 5GHz) for better performance.

        Args:
            network_id: ID of the network
            enabled: True to enable band steering, False to disable

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
            "%s band steering for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"band_steering": enabled},
        )

    async def set_upnp(self, network_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable UPnP (Universal Plug and Play) - returns raw Eero API response.

        UPnP allows devices to automatically configure port forwarding.
        Disabling can improve security but may break some applications.

        Args:
            network_id: ID of the network
            enabled: True to enable UPnP, False to disable

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
            "%s UPnP for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"upnp": enabled},
        )

    async def set_ipv6(self, network_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable IPv6 - returns raw Eero API response.

        Args:
            network_id: ID of the network
            enabled: True to enable IPv6, False to disable

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
            "%s IPv6 for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={
                "ipv6_upstream": enabled,
                "ipv6_downstream": enabled,
            },
        )

    async def set_thread(self, network_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable Thread (for smart home devices) - returns raw Eero API response.

        Thread is a low-power mesh networking protocol used by
        smart home devices like Apple HomePod, Google Nest, etc.

        Args:
            network_id: ID of the network
            enabled: True to enable Thread, False to disable

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
            "%s Thread for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"thread": enabled},
        )

    async def configure_security(
        self,
        network_id: str,
        wpa3: Optional[bool] = None,
        band_steering: Optional[bool] = None,
        upnp: Optional[bool] = None,
        ipv6: Optional[bool] = None,
        thread: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Configure multiple security settings at once - returns raw Eero API response.

        Args:
            network_id: ID of the network
            wpa3: Enable/disable WPA3
            band_steering: Enable/disable band steering
            upnp: Enable/disable UPnP
            ipv6: Enable/disable IPv6
            thread: Enable/disable Thread

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

        if wpa3 is not None:
            payload["wpa3"] = wpa3

        if band_steering is not None:
            payload["band_steering"] = band_steering

        if upnp is not None:
            payload["upnp"] = upnp

        if ipv6 is not None:
            payload["ipv6_upstream"] = ipv6
            payload["ipv6_downstream"] = ipv6

        if thread is not None:
            payload["thread"] = thread

        if not payload:
            _LOGGER.warning("No security settings provided")
            return {"meta": {"code": 400}, "data": {}}

        _LOGGER.debug("Configuring security for network %s: %s", network_id, payload)

        return await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json=payload,
        )
