"""DNS Settings API for Eero."""

import logging
from typing import Any, Dict, List, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class DnsAPI(AuthenticatedAPI):
    """DNS Settings API for Eero.

    Manages DNS configuration including custom DNS servers,
    DNS caching, and DNS mode settings.
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DnsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_dns_settings(self, network_id: str) -> Dict[str, Any]:
        """Get DNS configuration for a network.

        Args:
            network_id: ID of the network

        Returns:
            Dictionary containing DNS settings:
            - dns_caching: bool - Whether DNS caching is enabled
            - dns_mode: str - DNS mode (auto, custom, cloudflare, etc.)
            - custom_dns: list - Custom DNS server IPs
            - ipv6_dns: bool - Whether IPv6 DNS is enabled

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting DNS settings for network %s", network_id)

        response = await self.get(
            f"networks/{network_id}",
            auth_token=auth_token,
        )

        data = response.get("data", {})

        # Extract DNS settings from various possible locations
        dns_settings = {
            "dns_caching": data.get("dns_caching", False),
            "dns_mode": "auto",
            "custom_dns": [],
            "ipv6_dns": data.get("ipv6_upstream", False),
        }

        # Check for DNS settings in different formats
        if "dns" in data:
            dns_data = data["dns"]
            if isinstance(dns_data, dict):
                dns_settings["dns_mode"] = dns_data.get("mode", "auto")
                dns_settings["custom_dns"] = dns_data.get("servers", [])
                dns_settings["dns_caching"] = dns_data.get("caching", dns_settings["dns_caching"])

        # Check for custom_dns directly in data
        if "custom_dns" in data:
            custom_dns = data["custom_dns"]
            if isinstance(custom_dns, list) and custom_dns:
                dns_settings["custom_dns"] = custom_dns
                dns_settings["dns_mode"] = "custom"

        # Check for dns_servers
        if "dns_servers" in data:
            dns_settings["custom_dns"] = data["dns_servers"]

        return dns_settings

    async def set_dns_caching(self, network_id: str, enabled: bool) -> bool:
        """Enable or disable DNS caching.

        Args:
            network_id: ID of the network
            enabled: True to enable DNS caching, False to disable

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
            "%s DNS caching for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        response = await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"dns_caching": enabled},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def set_custom_dns(
        self,
        network_id: str,
        dns_servers: List[str],
    ) -> bool:
        """Set custom DNS servers.

        Args:
            network_id: ID of the network
            dns_servers: List of DNS server IPs (max 2)
                        e.g., ["8.8.8.8", "8.8.4.4"] for Google DNS
                        e.g., ["1.1.1.1", "1.0.0.1"] for Cloudflare

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        # Limit to 2 DNS servers
        if len(dns_servers) > 2:
            _LOGGER.warning("Only first 2 DNS servers will be used")
            dns_servers = dns_servers[:2]

        _LOGGER.debug("Setting custom DNS for network %s: %s", network_id, dns_servers)

        response = await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"custom_dns": dns_servers},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def clear_custom_dns(self, network_id: str) -> bool:
        """Clear custom DNS servers and use automatic DNS.

        Args:
            network_id: ID of the network

        Returns:
            True if the operation was successful
        """
        return await self.set_custom_dns(network_id, [])

    async def set_dns_mode(
        self,
        network_id: str,
        mode: str,
        custom_servers: Optional[List[str]] = None,
    ) -> bool:
        """Set DNS mode for the network.

        Args:
            network_id: ID of the network
            mode: DNS mode - "auto", "custom", "cloudflare", "google", "opendns"
            custom_servers: Custom DNS servers (required if mode is "custom")

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

        # Handle preset modes
        if mode == "cloudflare":
            payload["custom_dns"] = ["1.1.1.1", "1.0.0.1"]
        elif mode == "google":
            payload["custom_dns"] = ["8.8.8.8", "8.8.4.4"]
        elif mode == "opendns":
            payload["custom_dns"] = ["208.67.222.222", "208.67.220.220"]
        elif mode == "custom" and custom_servers:
            payload["custom_dns"] = custom_servers[:2]
        elif mode == "auto":
            payload["custom_dns"] = []
        else:
            _LOGGER.warning("Invalid DNS mode: %s", mode)
            return False

        _LOGGER.debug("Setting DNS mode to %s for network %s", mode, network_id)

        response = await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json=payload,
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def set_ipv6_dns(self, network_id: str, enabled: bool) -> bool:
        """Enable or disable IPv6 DNS.

        Args:
            network_id: ID of the network
            enabled: True to enable IPv6 DNS, False to disable

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
            "%s IPv6 DNS for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        response = await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"ipv6_upstream": enabled},
        )

        return bool(response.get("meta", {}).get("code") == 200)
