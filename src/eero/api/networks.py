"""Networks API for Eero."""

import logging
from typing import Any, Dict, List, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAPIException, EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class NetworksAPI(AuthenticatedAPI):
    """Networks API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the NetworksAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_networks(self) -> List[Dict[str, Any]]:
        """Get list of networks with improved response handling.

        Returns:
            List of network data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting networks")

        # Use simple "networks" path
        response = await self.get(
            "networks",
            auth_token=auth_token,
        )

        _LOGGER.debug(f"Network response meta: {response.get('meta', {})}")

        # First try the new format (networks list directly in data)
        networks_data = []

        # Option 1: Try new format - directly in data.networks (API v2.2)
        if (
            "data" in response
            and "networks" in response["data"]
            and isinstance(response["data"]["networks"], list)
        ):
            networks_data = response["data"]["networks"]
            _LOGGER.debug(f"Found networks in data.networks: {len(networks_data)} networks")

        # Option 2: Try old format - networks in data.data array
        elif (
            "data" in response
            and "data" in response["data"]
            and isinstance(response["data"]["data"], list)
        ):
            networks_data = response["data"]["data"]
            _LOGGER.debug(f"Found networks in data.data: {len(networks_data)} networks")

        # Option 3: Try alternative format - networks directly in data array
        elif "data" in response and isinstance(response["data"], list):
            networks_data = response["data"]
            _LOGGER.debug(f"Found networks directly in data: {len(networks_data)} networks")

        _LOGGER.debug(f"Found {len(networks_data)} networks")

        # If still empty but we have a preferred network ID, try to construct a network entry
        if not networks_data and self._auth_api.preferred_network_id:
            _LOGGER.debug(
                f"No networks returned but have preferred network ID: {self._auth_api.preferred_network_id}"
            )

            # Try to get details for the preferred network
            try:
                network_details = await self.get_network(self._auth_api.preferred_network_id)
                if network_details:
                    _LOGGER.debug(
                        f"Successfully retrieved network details for ID: {self._auth_api.preferred_network_id}"
                    )
                    # Construct a complete network entry with all available fields
                    network_entry = {
                        "id": self._auth_api.preferred_network_id,
                        "url": f"/2.2/networks/{self._auth_api.preferred_network_id}",
                        "name": network_details.get("name", "Eero Network"),
                        "status": network_details.get("status", "connected"),
                    }

                    # Add additional fields if available
                    if "public_ip" in network_details:
                        network_entry["public_ip"] = network_details["public_ip"]
                    if "isp_name" in network_details:
                        network_entry["isp_name"] = network_details["isp_name"]
                    if "created_at" in network_details:
                        network_entry["created_at"] = network_details["created_at"]

                    networks_data = [network_entry]
                    _LOGGER.debug(f"Constructed network entry: {networks_data}")
            except Exception as e:
                _LOGGER.warning(f"Failed to get details for preferred network: {e}")

        return networks_data

    async def get_network(self, network_id: str) -> Dict[str, Any]:
        """Get network information with enhanced data extraction.

        Args:
            network_id: ID of the network to get

        Returns:
            Network data with additional fields extracted

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting network {network_id}")

        try:
            response = await self.get(
                f"networks/{network_id}",
                auth_token=auth_token,
            )

            # Extract the actual network data from the response
            network_data = {}

            if "data" in response:
                # API response format might vary, extract what we can
                data = response.get("data", {})

                # Copy all data fields from top level
                if isinstance(data, dict):
                    network_data = data.copy()

                    # Make sure we have the ID
                    if "id" not in network_data:
                        network_data["id"] = network_id

                    # Add status if not present
                    if "status" not in network_data:
                        network_data["status"] = data.get("status", "connected")

                    # Extract additional fields from the response structure

                    # Public IP (from wan_ip)
                    if "wan_ip" in data:
                        network_data["public_ip"] = data["wan_ip"]

                    # ISP name (from geo_ip.isp)
                    if "geo_ip" in data and isinstance(data["geo_ip"], dict):
                        geo_ip = data["geo_ip"]
                        if "isp" in geo_ip:
                            network_data["isp_name"] = geo_ip["isp"]

                    # Created date (from eeros data if available)
                    if (
                        "eeros" in data
                        and isinstance(data["eeros"], dict)
                        and "data" in data["eeros"]
                    ):
                        eeros_data = data["eeros"]["data"]
                        if isinstance(eeros_data, list) and len(eeros_data) > 0:
                            for eero in eeros_data:
                                if "network" in eero and isinstance(eero["network"], dict):
                                    network = eero["network"]
                                    if "created" in network:
                                        network_data["created_at"] = network["created"]
                                        break

                    # Guest network info
                    if "guest_network" in data and isinstance(data["guest_network"], dict):
                        guest_network = data["guest_network"]
                        network_data["guest_network_enabled"] = guest_network.get("enabled", False)
                        network_data["guest_network_name"] = guest_network.get("name")
                        network_data["guest_network_password"] = guest_network.get("password")

                    # DHCP data (custom structure needs transformation)
                    if "dhcp" in data and isinstance(data["dhcp"], dict):
                        dhcp_data = data["dhcp"]

                        # Get custom DHCP data
                        if "custom" in dhcp_data and isinstance(dhcp_data["custom"], dict):
                            custom = dhcp_data["custom"]
                            network_data["dhcp"] = {
                                "lease_time_seconds": 86400,  # Default to 24 hours
                                "subnet_mask": custom.get("subnet_mask"),
                                "starting_address": custom.get("start_ip"),
                                "ending_address": custom.get("end_ip"),
                                "dns_server": None,  # Default to None
                            }

                    # Settings
                    settings = {}
                    for setting in [
                        "ipv6_upstream",
                        "band_steering",
                        "thread",
                        "upnp",
                        "wpa3",
                        "dns_caching",
                        "ipv6_downstream",
                    ]:
                        if setting in data:
                            settings[setting if setting != "thread" else "thread_enabled"] = (
                                data.get(setting, False)
                            )
                        elif setting + "_enabled" in data:
                            settings[setting if setting != "thread" else "thread_enabled"] = (
                                data.get(setting + "_enabled", False)
                            )

                    if settings:
                        network_data["settings"] = settings

                    # Speed test data
                    if "speed" in data and isinstance(data["speed"], dict):
                        network_data["speed_test"] = data["speed"]

            # If we got an empty response but have a network ID, construct minimal data
            if not network_data and network_id:
                _LOGGER.debug(f"Empty network data for ID {network_id}, constructing minimal data")
                network_data = {
                    "id": network_id,
                    "url": f"/2.2/networks/{network_id}",
                    "name": "Eero Network",
                    "status": "connected",  # Default to "connected" since we can access it
                }

            _LOGGER.debug(f"Extracted network data: {network_data}")
            return network_data
        except EeroAPIException as e:
            if getattr(e, "status_code", 0) == 404:
                # Network not found, log and return minimal data
                _LOGGER.warning(f"Network {network_id} not found, returning minimal data")
                return {
                    "id": network_id,
                    "url": f"/2.2/networks/{network_id}",
                    "name": "Eero Network",
                    "status": "unknown",
                }
            raise

    async def set_guest_network(
        self,
        network_id: str,
        enabled: bool,
        name: Optional[str] = None,
        password: Optional[str] = None,
    ) -> bool:
        """Enable or disable the guest network.

        Args:
            network_id: ID of the network
            enabled: Whether to enable or disable the guest network
            name: Optional new name for the guest network
            password: Optional new password for the guest network

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {"enabled": enabled}

        if name is not None:
            payload["name"] = name

        if password is not None:
            payload["password"] = password

        # Simplified path construction
        response = await self.put(
            f"networks/{network_id}/guest_network",
            auth_token=auth_token,
            json=payload,
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def run_speed_test(self, network_id: str) -> Dict[str, Any]:
        """Run a speed test on the network.

        Args:
            network_id: ID of the network to run the speed test on

        Returns:
            Speed test results

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        # Simplified path construction
        response = await self.post(
            f"networks/{network_id}/speedtest",
            auth_token=auth_token,
            json={},
        )

        return response.get("data", {})

    async def reboot_network(self, network_id: str) -> bool:
        """Reboot the entire network.

        Args:
            network_id: ID of the network to reboot

        Returns:
            True if reboot was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Rebooting network {network_id}")

        response = await self.post(
            f"networks/{network_id}/reboot",
            auth_token=auth_token,
            json={},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def get_premium_status(self, network_id: str) -> Dict[str, Any]:
        """Get Eero Plus/Eero Secure subscription status.

        Args:
            network_id: ID of the network to check

        Returns:
            Dictionary containing premium status information:
            - premium_enabled: bool - Whether premium features are active
            - premium_status: str - Status string
            - features: list - Available premium features
            - expires_at: str - Expiration date (if available)

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting premium status for network %s", network_id)

        # Get network data which includes premium info
        response = await self.get(
            f"networks/{network_id}",
            auth_token=auth_token,
        )

        data = response.get("data", {})

        # Extract premium status from various possible locations
        premium_info: Dict[str, Any] = {
            "premium_enabled": False,
            "premium_status": "inactive",
            "features": [],
            "expires_at": None,
        }

        # Check premium_status field
        if "premium_status" in data:
            premium_status = data["premium_status"]
            if isinstance(premium_status, dict):
                premium_info["premium_enabled"] = premium_status.get("active", False)
                premium_info["premium_status"] = (
                    "active" if premium_info["premium_enabled"] else "inactive"
                )
                premium_info["expires_at"] = premium_status.get("expiration")
                premium_info["features"] = premium_status.get("features", [])
            elif isinstance(premium_status, str):
                premium_info["premium_enabled"] = premium_status.lower() == "active"
                premium_info["premium_status"] = premium_status

        # Check eero_plus or eero_secure fields
        if "eero_plus" in data:
            eero_plus = data["eero_plus"]
            if isinstance(eero_plus, dict):
                premium_info["premium_enabled"] = eero_plus.get("enabled", False)
                premium_info["features"] = eero_plus.get("features", [])
            elif isinstance(eero_plus, bool):
                premium_info["premium_enabled"] = eero_plus

        # Check for premium DNS settings as indicator
        if "premium_dns" in data and data["premium_dns"]:
            premium_info["premium_enabled"] = True

        # Update status string based on enabled flag
        if premium_info["premium_enabled"]:
            premium_info["premium_status"] = "active"

        return premium_info

    async def is_premium(self, network_id: str) -> bool:
        """Check if the network has an active Eero Plus subscription.

        Args:
            network_id: ID of the network to check

        Returns:
            True if Eero Plus is active, False otherwise

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        premium_status = await self.get_premium_status(network_id)
        return premium_status.get("premium_enabled", False)

    async def set_network_name(self, network_id: str, name: str) -> bool:
        """Set the network name (SSID).

        Note: This may require a network restart to take effect.

        Args:
            network_id: ID of the network
            name: New network name

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting network name for %s to '%s'", network_id, name)

        response = await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"name": name},
        )

        return bool(response.get("meta", {}).get("code") == 200)
