"""High-level client for interacting with Eero networks.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
Response format: {"meta": {...}, "data": {...}}
"""

import logging
import time
from typing import Any, Dict, List, Optional

from aiohttp import ClientSession

from .api import EeroAPI
from .exceptions import EeroException

_LOGGER = logging.getLogger(__name__)


class EeroClient:
    """High-level client for interacting with Eero networks.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}

    Downstream clients must handle:
    - Data extraction from response envelopes
    - Field renaming (e.g., wan_ip → public_ip)
    - Nested data extraction (e.g., geo_ip.isp → isp_name)
    - Status normalization
    - Model validation/conversion
    """

    def __init__(
        self,
        session: Optional[ClientSession] = None,
        cookie_file: Optional[str] = None,
        use_keyring: bool = True,
        cache_timeout: int = 60,
    ) -> None:
        """Initialize the EeroClient.

        Args:
            session: Optional aiohttp ClientSession to use for requests
            cookie_file: Optional path to a file for storing authentication cookies
            use_keyring: Whether to use keyring for secure token storage
            cache_timeout: Cache timeout in seconds
        """
        self._api = EeroAPI(session=session, cookie_file=cookie_file, use_keyring=use_keyring)
        self._cache_timeout = cache_timeout
        self._cache: Dict[str, Dict] = {
            "account": {"data": None, "timestamp": 0},
            "networks": {"data": None, "timestamp": 0},
            "network": {},
            "eeros": {},
            "devices": {},
            "profiles": {},
        }

    async def __aenter__(self) -> "EeroClient":
        """Enter async context manager."""
        await self._api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        await self._api.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def is_authenticated(self) -> bool:
        """Check if the client is authenticated."""
        return self._api.is_authenticated

    def _is_cache_valid(self, cache_key: str, subkey: Optional[str] = None) -> bool:
        """Check if a cache entry is valid."""
        if cache_key not in self._cache:
            return False

        if subkey is None:
            cache_entry = self._cache[cache_key]
        else:
            if subkey not in self._cache[cache_key]:
                return False
            cache_entry = self._cache[cache_key][subkey]

        if not cache_entry or "timestamp" not in cache_entry:
            return False

        current_time = time.monotonic()
        return (current_time - cache_entry["timestamp"]) < self._cache_timeout

    def _update_cache(self, cache_key: str, subkey: Optional[str], data: Any) -> None:
        """Update a cache entry."""
        current_time = time.monotonic()

        if subkey is None:
            self._cache[cache_key] = {"data": data, "timestamp": current_time}
        else:
            if cache_key not in self._cache:
                self._cache[cache_key] = {}
            self._cache[cache_key][subkey] = {"data": data, "timestamp": current_time}

    def _get_from_cache(self, cache_key: str, subkey: Optional[str] = None) -> Any:
        """Get data from cache."""
        if cache_key not in self._cache:
            return None

        if subkey is None:
            cache_entry = self._cache[cache_key]
        else:
            if subkey not in self._cache[cache_key]:
                return None
            cache_entry = self._cache[cache_key][subkey]

        return cache_entry.get("data")

    def clear_cache(self) -> None:
        """Clear all cached data."""
        for cache_key in self._cache:
            if isinstance(self._cache[cache_key], dict) and "data" in self._cache[cache_key]:
                self._cache[cache_key]["data"] = None
            else:
                self._cache[cache_key] = {}

    async def _ensure_network_id(
        self, network_id: Optional[str], auto_discover: bool = True
    ) -> str:
        """Ensure a valid network ID is available.

        Args:
            network_id: Optional network ID provided by caller
            auto_discover: If True, attempt to discover networks when no ID available

        Returns:
            Valid network ID

        Raises:
            EeroException: If no network ID can be determined
        """
        # Use provided ID or fall back to preferred
        resolved_id = network_id or self._api.preferred_network_id
        if resolved_id:
            return resolved_id

        # Try to auto-discover if enabled
        if auto_discover:
            networks_response = await self.get_networks()
            # Extract networks from raw response
            data = networks_response.get("data", {})
            networks = []
            if isinstance(data, list):
                networks = data
            elif isinstance(data, dict):
                networks = data.get("networks", data.get("data", []))

            if networks and len(networks) > 0:
                # Extract ID from URL or id field
                first_network = networks[0]
                net_id = first_network.get("id")
                if not net_id and first_network.get("url"):
                    net_id = first_network["url"].rstrip("/").split("/")[-1]
                if net_id:
                    return net_id

        raise EeroException("No network ID provided and no preferred network set")

    # ==================== Authentication ====================

    async def login(self, user_identifier: str) -> bool:
        """Start the login process by requesting a verification code.

        Args:
            user_identifier: Email address or phone number for the Eero account

        Returns:
            True if login request was successful
        """
        return await self._api.login(user_identifier)

    async def verify(self, verification_code: str) -> bool:
        """Verify login with the code sent to the user.

        Args:
            verification_code: The verification code sent to the user

        Returns:
            True if verification was successful
        """
        result = await self._api.verify(verification_code)
        if result:
            self.clear_cache()
        return result

    async def logout(self) -> bool:
        """Log out from the Eero API.

        Returns:
            True if logout was successful
        """
        result = await self._api.logout()
        if result:
            self.clear_cache()
        return result

    # ==================== Account ====================

    async def get_account(self, refresh_cache: bool = False) -> Dict[str, Any]:
        """Get account information - returns raw Eero API response.

        Args:
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        if not refresh_cache and self._is_cache_valid("account"):
            cached = self._get_from_cache("account")
            if cached:
                return cached

        response = await self._api.auth.get(
            "/account", auth_token=await self._api.auth.get_auth_token()
        )
        self._update_cache("account", None, response)
        return response

    # ==================== Networks ====================

    async def get_networks(self, refresh_cache: bool = False) -> Dict[str, Any]:
        """Get list of networks - returns raw Eero API response.

        Args:
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        if not refresh_cache and self._is_cache_valid("networks"):
            cached = self._get_from_cache("networks")
            if cached:
                return cached

        response = await self._api.networks.get_networks()
        self._update_cache("networks", None, response)

        # Set preferred network ID if not already set
        if not self._api.preferred_network_id:
            data = response.get("data", {})
            networks = []
            if isinstance(data, list):
                networks = data
            elif isinstance(data, dict):
                networks = data.get("networks", data.get("data", []))

            if networks and len(networks) > 0:
                first_network = networks[0]
                net_id = first_network.get("id")
                if not net_id and first_network.get("url"):
                    net_id = first_network["url"].rstrip("/").split("/")[-1]
                if net_id:
                    self._api.set_preferred_network(net_id)

        return response

    async def get_network(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> Dict[str, Any]:
        """Get network information - returns raw Eero API response.

        Args:
            network_id: ID of the network to get (uses preferred network if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        if not refresh_cache and self._is_cache_valid("network", network_id):
            cached = self._get_from_cache("network", network_id)
            if cached:
                return cached

        response = await self._api.networks.get_network(network_id)
        self._update_cache("network", network_id, response)
        return response

    # ==================== Eeros ====================

    async def get_eeros(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> Dict[str, Any]:
        """Get list of Eero devices - returns raw Eero API response.

        Args:
            network_id: ID of the network to get Eeros from (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_eeros"
        if not refresh_cache and self._is_cache_valid("eeros", cache_key):
            cached = self._get_from_cache("eeros", cache_key)
            if cached:
                return cached

        response = await self._api.eeros.get_eeros(network_id)
        self._update_cache("eeros", cache_key, response)
        return response

    async def get_eero(
        self,
        eero_id: str,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Dict[str, Any]:
        """Get information about a specific Eero device - returns raw Eero API response.

        Args:
            eero_id: ID of the Eero device to get
            network_id: ID of the network (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)
        return await self._api.eeros.get_eero(network_id, eero_id)

    async def reboot_eero(self, eero_id: str, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Reboot an Eero device - returns raw Eero API response.

        Args:
            eero_id: ID of the Eero device to reboot
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.eeros.reboot_eero(network_id, eero_id)

        # Clear cache for eeros
        cache_key = f"{network_id}_eeros"
        if cache_key in self._cache.get("eeros", {}):
            del self._cache["eeros"][cache_key]

        return response

    # ==================== Devices ====================

    async def get_devices(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> Dict[str, Any]:
        """Get list of connected devices - returns raw Eero API response.

        Args:
            network_id: ID of the network to get devices from (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_devices"
        if not refresh_cache and self._is_cache_valid("devices", cache_key):
            cached = self._get_from_cache("devices", cache_key)
            if cached:
                return cached

        response = await self._api.devices.get_devices(network_id)
        self._update_cache("devices", cache_key, response)
        return response

    async def get_device(
        self,
        device_id: str,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Dict[str, Any]:
        """Get information about a specific device - returns raw Eero API response.

        Args:
            device_id: ID of the device to get
            network_id: ID of the network (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_{device_id}"
        if not refresh_cache and self._is_cache_valid("devices", cache_key):
            cached = self._get_from_cache("devices", cache_key)
            if cached:
                return cached

        response = await self._api.devices.get_device(network_id, device_id)
        self._update_cache("devices", cache_key, response)
        return response

    async def set_device_nickname(
        self, device_id: str, nickname: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set a nickname for a device - returns raw Eero API response.

        Args:
            device_id: ID of the device
            nickname: New nickname for the device
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.devices.set_device_nickname(network_id, device_id, nickname)

        # Clear device cache
        self._invalidate_device_cache(network_id, device_id)

        return response

    async def block_device(
        self, device_id: str, blocked: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Block or unblock a device - returns raw Eero API response.

        Args:
            device_id: ID of the device
            blocked: Whether to block or unblock the device
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.devices.block_device(network_id, device_id, blocked)

        # Clear device cache
        self._invalidate_device_cache(network_id, device_id)

        return response

    async def pause_device(
        self, device_id: str, paused: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pause or unpause internet access for a device - returns raw Eero API response.

        Args:
            device_id: ID of the device
            paused: True to pause internet access, False to resume
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.devices.pause_device(network_id, device_id, paused)

        # Clear device cache
        self._invalidate_device_cache(network_id, device_id)

        return response

    def _invalidate_device_cache(self, network_id: str, device_id: str) -> None:
        """Invalidate device-related cache entries."""
        cache_key = f"{network_id}_{device_id}"
        if cache_key in self._cache.get("devices", {}):
            del self._cache["devices"][cache_key]

        cache_key = f"{network_id}_devices"
        if cache_key in self._cache.get("devices", {}):
            del self._cache["devices"][cache_key]

    # ==================== Profiles ====================

    async def get_profiles(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> Dict[str, Any]:
        """Get list of profiles - returns raw Eero API response.

        Args:
            network_id: ID of the network to get profiles from (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_profiles"
        if not refresh_cache and self._is_cache_valid("profiles", cache_key):
            cached = self._get_from_cache("profiles", cache_key)
            if cached:
                return cached

        response = await self._api.profiles.get_profiles(network_id)
        self._update_cache("profiles", cache_key, response)
        return response

    async def get_profile(
        self,
        profile_id: str,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Dict[str, Any]:
        """Get information about a specific profile - returns raw Eero API response.

        Args:
            profile_id: ID of the profile to get
            network_id: ID of the network (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_{profile_id}"
        if not refresh_cache and self._is_cache_valid("profiles", cache_key):
            cached = self._get_from_cache("profiles", cache_key)
            if cached:
                return cached

        response = await self._api.profiles.get_profile(network_id, profile_id)
        self._update_cache("profiles", cache_key, response)
        return response

    async def pause_profile(
        self, profile_id: str, paused: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pause or unpause internet access for a profile - returns raw Eero API response.

        Args:
            profile_id: ID of the profile
            paused: Whether to pause or unpause the profile
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.profiles.pause_profile(network_id, profile_id, paused)

        # Clear profile cache
        self._invalidate_profile_cache(network_id, profile_id)

        return response

    def _invalidate_profile_cache(self, network_id: str, profile_id: str) -> None:
        """Invalidate profile-related cache entries."""
        cache_key = f"{network_id}_{profile_id}"
        if cache_key in self._cache.get("profiles", {}):
            del self._cache["profiles"][cache_key]

        cache_key = f"{network_id}_profiles"
        if cache_key in self._cache.get("profiles", {}):
            del self._cache["profiles"][cache_key]

    # ==================== Guest Network ====================

    async def set_guest_network(
        self,
        enabled: bool,
        name: Optional[str] = None,
        password: Optional[str] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enable or disable the guest network - returns raw Eero API response.

        Args:
            enabled: Whether to enable or disable the guest network
            name: Optional new name for the guest network
            password: Optional new password for the guest network
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.networks.set_guest_network(network_id, enabled, name, password)

        # Clear network cache
        if network_id in self._cache.get("network", {}):
            del self._cache["network"][network_id]

        return response

    # ==================== Speed Test ====================

    async def run_speed_test(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Run a speed test on the network - returns raw Eero API response.

        Args:
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.networks.run_speed_test(network_id)

        # Clear network cache
        if network_id in self._cache.get("network", {}):
            del self._cache["network"][network_id]

        return response

    # ==================== Network Settings ====================

    def set_preferred_network(self, network_id: str) -> None:
        """Set the preferred network ID to use for requests.

        Args:
            network_id: ID of the network to use
        """
        self._api.set_preferred_network(network_id)

    @property
    def preferred_network_id(self) -> Optional[str]:
        """Get the preferred network ID."""
        return self._api.preferred_network_id

    # ==================== Diagnostics & Settings ====================

    async def get_diagnostics(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get network diagnostics - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.diagnostics.get_diagnostics(network_id)

    async def run_diagnostics(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Run network diagnostics - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.diagnostics.run_diagnostics(network_id)

    async def get_settings(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get network settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.settings.get_settings(network_id)

    async def get_insights(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get network insights - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.insights.get_insights(network_id)

    async def get_routing(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get network routing - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.routing.get_routing(network_id)

    async def get_thread(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get Thread status - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.thread.get_thread(network_id)

    async def get_support(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get support info - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.support.get_support(network_id)

    async def get_blacklist(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get device blacklist - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.blacklist.get_blacklist(network_id)

    async def get_reservations(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get DHCP reservations - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.reservations.get_reservations(network_id)

    async def get_forwards(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get port forwards - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.forwards.get_forwards(network_id)

    async def get_transfer_stats(
        self, network_id: Optional[str] = None, device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get transfer statistics - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.transfer.get_transfer_stats(network_id, device_id)

    async def get_burst_reporters(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get burst reporters - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.burst_reporters.get_burst_reporters(network_id)

    async def get_ac_compat(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get AC compatibility - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.ac_compat.get_ac_compat(network_id)

    async def get_ouicheck(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get OUI check - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.ouicheck.get_ouicheck(network_id)

    async def get_password(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get password info - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.password.get_password(network_id)

    async def get_updates(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get update info - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.updates.get_updates(network_id)

    # ==================== Activity (Eero Plus) ====================

    async def get_activity(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get network activity - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity(network_id)

    async def get_activity_clients(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get per-client activity - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity_clients(network_id)

    async def get_activity_for_device(
        self, device_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get activity for a device - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity_for_device(network_id, device_id)

    async def get_activity_history(
        self, network_id: Optional[str] = None, period: str = "day"
    ) -> Dict[str, Any]:
        """Get activity history - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity_history(network_id, period)

    async def get_activity_categories(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get activity categories - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity_categories(network_id)

    async def get_premium_status(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get premium status - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.networks.get_premium_status(network_id)

    async def set_network_name(self, name: str, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Set network name - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.networks.set_network_name(network_id, name)

        if network_id in self._cache.get("network", {}):
            del self._cache["network"][network_id]

        return response

    # ==================== LED & Nightlight ====================

    async def get_led_status(
        self, eero_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get LED status - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.get_led_status(network_id, eero_id)

    async def set_led(
        self, eero_id: str, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set LED on/off - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.eeros.set_led(network_id, eero_id, enabled)

        cache_key = f"{network_id}_eeros"
        if cache_key in self._cache.get("eeros", {}):
            del self._cache["eeros"][cache_key]

        return response

    async def set_led_brightness(
        self, eero_id: str, brightness: int, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set LED brightness - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.set_led_brightness(network_id, eero_id, brightness)

    async def get_nightlight(
        self, eero_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get nightlight settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.get_nightlight(network_id, eero_id)

    async def set_nightlight(
        self,
        eero_id: str,
        enabled: Optional[bool] = None,
        brightness: Optional[int] = None,
        schedule_enabled: Optional[bool] = None,
        schedule_on: Optional[str] = None,
        schedule_off: Optional[str] = None,
        ambient_light_enabled: Optional[bool] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set nightlight settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.eeros.set_nightlight(
            network_id,
            eero_id,
            enabled=enabled,
            brightness=brightness,
            schedule_enabled=schedule_enabled,
            schedule_on=schedule_on,
            schedule_off=schedule_off,
            ambient_light_enabled=ambient_light_enabled,
        )

        cache_key = f"{network_id}_eeros"
        if cache_key in self._cache.get("eeros", {}):
            del self._cache["eeros"][cache_key]

        return response

    # ==================== Backup Network ====================

    async def get_backup_network(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get backup network config - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.get_backup_network(network_id)

    async def get_backup_status(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get backup status - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.get_backup_status(network_id)

    async def set_backup_network(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable/disable backup network - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.set_backup_network(network_id, enabled)

    async def configure_backup_network(
        self,
        enabled: Optional[bool] = None,
        phone_number: Optional[str] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Configure backup network - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.configure_backup_network(
            network_id, enabled=enabled, phone_number=phone_number
        )

    # ==================== Schedule ====================

    async def get_profile_schedule(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get profile schedule - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.get_profile_schedule(network_id, profile_id)

    async def set_profile_schedule(
        self,
        profile_id: str,
        time_blocks: List[Dict],
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set profile schedule - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.schedule.set_profile_schedule(
            network_id, profile_id, time_blocks
        )
        self._invalidate_profile_cache(network_id, profile_id)
        return response

    async def enable_bedtime(
        self,
        profile_id: str,
        start_time: str,
        end_time: str,
        days: Optional[List[str]] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enable bedtime - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.enable_bedtime(
            network_id, profile_id, start_time, end_time, days
        )

    async def clear_profile_schedule(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Clear profile schedule - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.clear_profile_schedule(network_id, profile_id)

    # ==================== DNS ====================

    async def get_dns_settings(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get DNS settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns.get_dns_settings(network_id)

    async def set_dns_caching(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set DNS caching - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns.set_dns_caching(network_id, enabled)

    async def set_custom_dns(
        self, dns_servers: List[str], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set custom DNS - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns.set_custom_dns(network_id, dns_servers)

    async def set_dns_mode(
        self,
        mode: str,
        custom_servers: Optional[List[str]] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set DNS mode - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns.set_dns_mode(network_id, mode, custom_servers)

    # ==================== SQM ====================

    async def get_sqm_settings(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get SQM settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.sqm.get_sqm_settings(network_id)

    async def set_sqm_enabled(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable/disable SQM - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.sqm.set_sqm_enabled(network_id, enabled)

    async def configure_sqm(
        self,
        enabled: bool,
        upload_mbps: Optional[int] = None,
        download_mbps: Optional[int] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Configure SQM - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.sqm.configure_sqm(network_id, enabled, upload_mbps, download_mbps)

    # ==================== Device Priority ====================

    async def get_device_priority(
        self, device_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get device priority - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.devices.get_device(network_id, device_id)

    async def set_device_priority(
        self,
        device_id: str,
        prioritized: bool,
        duration_minutes: Optional[int] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set device priority - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.devices.set_device_priority(
            network_id, device_id, prioritized, duration_minutes
        )
        self._invalidate_device_cache(network_id, device_id)
        return response

    # ==================== Security ====================

    async def get_security_settings(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get security settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.get_security_settings(network_id)

    async def set_wpa3(self, enabled: bool, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Set WPA3 - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_wpa3(network_id, enabled)

    async def set_band_steering(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set band steering - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_band_steering(network_id, enabled)

    async def set_upnp(self, enabled: bool, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Set UPnP - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_upnp(network_id, enabled)

    async def set_ipv6(self, enabled: bool, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Set IPv6 - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_ipv6(network_id, enabled)

    async def set_thread_enabled(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set Thread - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_thread(network_id, enabled)

    async def configure_security(
        self,
        wpa3: Optional[bool] = None,
        band_steering: Optional[bool] = None,
        upnp: Optional[bool] = None,
        ipv6: Optional[bool] = None,
        thread: Optional[bool] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Configure security - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.configure_security(
            network_id,
            wpa3=wpa3,
            band_steering=band_steering,
            upnp=upnp,
            ipv6=ipv6,
            thread=thread,
        )

    # ==================== Blocked Applications ====================

    async def get_blocked_applications(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get blocked applications - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.profiles.get_blocked_applications(network_id, profile_id)

    async def set_blocked_applications(
        self,
        profile_id: str,
        applications: List[str],
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set blocked applications - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.profiles.set_blocked_applications(
            network_id, profile_id, applications
        )
        self._invalidate_profile_cache(network_id, profile_id)
        return response

    # ==================== Profile Devices ====================

    async def get_profile_devices(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get profile devices - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id)
        return await self._api.profiles.get_profile_devices(network_id, profile_id)

    async def set_profile_devices(
        self,
        profile_id: str,
        device_urls: List[str],
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set profile devices - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id)
        response = await self._api.profiles.set_profile_devices(network_id, profile_id, device_urls)
        self._invalidate_profile_cache(network_id, profile_id)
        return response
