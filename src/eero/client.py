"""High-level client for interacting with Eero networks."""

import logging
import time
from typing import Any, Dict, List, Optional

from aiohttp import ClientSession

from .api import EeroAPI
from .exceptions import EeroAuthenticationException, EeroException
from .models.account import Account
from .models.device import Device
from .models.eero import Eero
from .models.network import Network
from .models.profile import Profile

_LOGGER = logging.getLogger(__name__)


class EeroClient:
    """High-level client for interacting with Eero networks."""

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
        """Check if a cache entry is valid.

        Args:
            cache_key: Main cache key
            subkey: Optional subkey

        Returns:
            True if cache is valid, False otherwise
        """
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
        """Update a cache entry.

        Args:
            cache_key: Main cache key
            subkey: Optional subkey
            data: Data to cache
        """
        current_time = time.monotonic()

        if subkey is None:
            self._cache[cache_key] = {"data": data, "timestamp": current_time}
        else:
            if cache_key not in self._cache:
                self._cache[cache_key] = {}
            self._cache[cache_key][subkey] = {"data": data, "timestamp": current_time}

    def _get_from_cache(self, cache_key: str, subkey: Optional[str] = None) -> Any:
        """Get data from cache.

        Args:
            cache_key: Main cache key
            subkey: Optional subkey

        Returns:
            Cached data or None if not in cache
        """
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
            networks = await self.get_networks()
            if networks:
                return networks[0].id

        raise EeroException("No network ID provided and no preferred network set")

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
            # Clear cache on successful login
            self.clear_cache()
        return result

    async def logout(self) -> bool:
        """Log out from the Eero API.

        Returns:
            True if logout was successful
        """
        result = await self._api.logout()
        if result:
            # Clear cache on successful logout
            self.clear_cache()
        return result

    async def get_account(self, refresh_cache: bool = False) -> Account:
        """Get account information.

        Args:
            refresh_cache: Whether to refresh the cache

        Returns:
            Account object
        """
        if not refresh_cache and self._is_cache_valid("account"):
            account_data = self._get_from_cache("account")
            if account_data:
                return Account.model_validate(account_data)

        account_data = await self._api.auth.get(
            "/account", auth_token=await self._api.auth.get_auth_token()
        )
        account_data = account_data.get("data", {})
        self._update_cache("account", None, account_data)

        return Account.model_validate(account_data)

    async def get_networks(self, refresh_cache: bool = False) -> List[Network]:
        """Get list of networks.

        Args:
            refresh_cache: Whether to refresh the cache

        Returns:
            List of Network objects
        """
        if not refresh_cache and self._is_cache_valid("networks"):
            networks_data = self._get_from_cache("networks")
            if networks_data:
                return [Network.model_validate(net) for net in networks_data]

        networks_data = await self._api.networks.get_networks()
        self._update_cache("networks", None, networks_data)

        # Set preferred network ID if not already set and we have networks
        if not self._api.preferred_network_id and networks_data:
            first_network_id = networks_data[0].get("id")
            if first_network_id:
                self._api.set_preferred_network(first_network_id)

        return [Network.model_validate(net) for net in networks_data]

    async def get_network(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> Network:
        """Get network information with improved error handling.

        Args:
            network_id: ID of the network to get (uses preferred network if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Network object

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        if not refresh_cache and self._is_cache_valid("network", network_id):
            network_data = self._get_from_cache("network", network_id)
            if network_data:
                try:
                    _LOGGER.debug(f"Using cached network data for network {network_id}")
                    return Network.model_validate(network_data)
                except Exception as e:
                    _LOGGER.warning(f"Error validating cached network data: {e}")
                    # Fall through to fetch fresh data

        try:
            _LOGGER.debug(f"Fetching network data for network {network_id}")
            network_data = await self._api.networks.get_network(network_id)

            # Ensure we have the minimum required fields
            if "id" not in network_data:
                network_data["id"] = network_id

            if "name" not in network_data:
                network_data["name"] = "Eero Network"

            if "status" not in network_data:
                # Default to "connected" since we can access it
                network_data["status"] = "connected"

            # Fix DHCP data if present but incomplete
            if "dhcp" in network_data and isinstance(network_data["dhcp"], dict):
                dhcp_data = network_data["dhcp"]

                # If it has a mode but not the required fields, remove it
                if "mode" in dhcp_data and "custom" in dhcp_data:
                    custom_data = dhcp_data.get("custom", {})
                    # Create proper DHCP structure
                    if all(k in custom_data for k in ["subnet_mask", "start_ip", "end_ip"]):
                        network_data["dhcp"] = {
                            "lease_time_seconds": 86400,  # Default 24 hours
                            "subnet_mask": custom_data.get("subnet_mask"),
                            "starting_address": custom_data.get("start_ip"),
                            "ending_address": custom_data.get("end_ip"),
                            "dns_server": None,
                        }
                    else:
                        # Remove problematic DHCP data
                        network_data.pop("dhcp")

            self._update_cache("network", network_id, network_data)

            try:
                return Network.model_validate(network_data)
            except Exception as e:
                _LOGGER.error(f"Error creating Network model: {e}")
                # Create a basic network object as fallback
                fallback_data = {
                    "id": network_id,
                    "name": network_data.get("name", "Eero Network"),
                    "status": "connected",  # Default to "connected" since we can access it
                    "url": network_data.get("url", f"/2.2/networks/{network_id}"),
                }
                return Network.model_validate(fallback_data)
        except EeroAuthenticationException:
            # Re-raise authentication errors - don't mask them with fallback data
            raise
        except Exception as e:
            _LOGGER.error(f"Error getting network details: {e}")
            # Create a minimal network object as fallback
            fallback_data = {
                "id": network_id,
                "name": "Eero Network",
                "status": "connected",  # Default to "connected" since we're authenticated
                "url": f"/2.2/networks/{network_id}",
            }
            return Network.model_validate(fallback_data)

    async def get_eeros(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> List[Eero]:
        """Get list of Eero devices.

        Args:
            network_id: ID of the network to get Eeros from (uses preferred network if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            List of Eero objects

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_eeros"
        if not refresh_cache and self._is_cache_valid("eeros", cache_key):
            eeros_data = self._get_from_cache("eeros", cache_key)
            if eeros_data:
                return [Eero.model_validate(eero) for eero in eeros_data]

        eeros_data = await self._api.eeros.get_eeros(network_id)
        self._update_cache("eeros", cache_key, eeros_data)
        return [Eero.model_validate(eero) for eero in eeros_data]

    async def get_eero(
        self,
        eero_id: str,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Eero:
        """Get information about a specific Eero device.

        Args:
            eero_id: ID or name of the Eero device to get
            network_id: ID of the network the Eero belongs to (uses preferred network if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Eero object

        Raises:
            EeroException: If no network ID is available or Eero not found
        """
        network_id = await self._ensure_network_id(network_id)

        # Get all eeros and find the specific one
        eeros = await self.get_eeros(network_id, refresh_cache)

        # Try to find by ID first (extract ID from URL if needed)
        for eero in eeros:
            # Check if the eero_id matches the ID in the URL
            if eero.url and eero_id in eero.url:
                return eero
            # Check if it matches the serial number
            if eero.serial == eero_id:
                return eero
            # Check if it matches the location (name)
            if eero.location == eero_id:
                return eero
            # Check if it matches the MAC address
            if eero.mac_address == eero_id:
                return eero

        raise EeroException(f"Eero device '{eero_id}' not found")

    async def get_devices(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> List[Device]:
        """Get list of connected devices.

        Args:
            network_id: ID of the network to get devices from (uses preferred network if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            List of Device objects

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_devices"
        if not refresh_cache and self._is_cache_valid("devices", cache_key):
            devices_data = self._get_from_cache("devices", cache_key)
            if devices_data:
                return [Device.model_validate(device) for device in devices_data]

        devices_data = await self._api.devices.get_devices(network_id)
        self._update_cache("devices", cache_key, devices_data)
        return [Device.model_validate(device) for device in devices_data]

    async def get_device(
        self,
        device_id: str,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Device:
        """Get information about a specific device.

        Args:
            device_id: ID of the device to get
            network_id: ID of the network the device belongs to (uses preferred network if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Device object

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_{device_id}"
        if not refresh_cache and self._is_cache_valid("devices", cache_key):
            device_data = self._get_from_cache("devices", cache_key)
            if device_data:
                return Device.model_validate(device_data)

        device_data = await self._api.devices.get_device(network_id, device_id)
        self._update_cache("devices", cache_key, device_data)
        return Device.model_validate(device_data)

    async def get_profiles(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> List[Profile]:
        """Get list of profiles.

        Args:
            network_id: ID of the network to get profiles from (uses preferred network if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            List of Profile objects

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_profiles"
        if not refresh_cache and self._is_cache_valid("profiles", cache_key):
            profiles_data = self._get_from_cache("profiles", cache_key)
            if profiles_data:
                return [Profile.model_validate(profile) for profile in profiles_data]

        profiles_data = await self._api.profiles.get_profiles(network_id)
        self._update_cache("profiles", cache_key, profiles_data)
        return [Profile.model_validate(profile) for profile in profiles_data]

    async def get_profile(
        self,
        profile_id: str,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Profile:
        """Get information about a specific profile.

        Args:
            profile_id: ID of the profile to get
            network_id: ID of the network the profile belongs to (uses preferred network if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Profile object

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_{profile_id}"
        if not refresh_cache and self._is_cache_valid("profiles", cache_key):
            profile_data = self._get_from_cache("profiles", cache_key)
            if profile_data:
                return Profile.model_validate(profile_data)

        profile_data = await self._api.profiles.get_profile(network_id, profile_id)
        self._update_cache("profiles", cache_key, profile_data)
        return Profile.model_validate(profile_data)

    async def reboot_eero(self, eero_id: str, network_id: Optional[str] = None) -> bool:
        """Reboot an Eero device.

        Args:
            eero_id: ID of the Eero device to reboot
            network_id: ID of the network the Eero belongs to (uses preferred network if None)

        Returns:
            True if reboot was successful

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.eeros.reboot_eero(network_id, eero_id)

        # Clear cache for this eero
        if result:
            cache_key = f"{network_id}_{eero_id}"
            if cache_key in self._cache.get("eeros", {}):
                del self._cache["eeros"][cache_key]

        return result

    async def set_guest_network(
        self,
        enabled: bool,
        name: Optional[str] = None,
        password: Optional[str] = None,
        network_id: Optional[str] = None,
    ) -> bool:
        """Enable or disable the guest network.

        Args:
            enabled: Whether to enable or disable the guest network
            name: Optional new name for the guest network
            password: Optional new password for the guest network
            network_id: ID of the network (uses preferred network if None)

        Returns:
            True if the operation was successful

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.networks.set_guest_network(network_id, enabled, name, password)

        # Clear network cache on success
        if result and network_id in self._cache.get("network", {}):
            del self._cache["network"][network_id]

        return result

    async def set_device_nickname(
        self, device_id: str, nickname: str, network_id: Optional[str] = None
    ) -> bool:
        """Set a nickname for a device.

        Args:
            device_id: ID of the device
            nickname: New nickname for the device
            network_id: ID of the network the device belongs to (uses preferred network if None)

        Returns:
            True if the operation was successful

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.devices.set_device_nickname(network_id, device_id, nickname)

        # Clear device cache on success
        if result:
            cache_key = f"{network_id}_{device_id}"
            if cache_key in self._cache.get("devices", {}):
                del self._cache["devices"][cache_key]

            # Also clear devices list cache
            cache_key = f"{network_id}_devices"
            if cache_key in self._cache.get("devices", {}):
                del self._cache["devices"][cache_key]

        return result

    async def block_device(
        self, device_id: str, blocked: bool, network_id: Optional[str] = None
    ) -> bool:
        """Block or unblock a device.

        Args:
            device_id: ID of the device
            blocked: Whether to block or unblock the device
            network_id: ID of the network the device belongs to (uses preferred network if None)

        Returns:
            True if the operation was successful

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.devices.block_device(network_id, device_id, blocked)

        # Clear device cache on success
        if result:
            cache_key = f"{network_id}_{device_id}"
            if cache_key in self._cache.get("devices", {}):
                del self._cache["devices"][cache_key]

            # Also clear devices list cache
            cache_key = f"{network_id}_devices"
            if cache_key in self._cache.get("devices", {}):
                del self._cache["devices"][cache_key]

        return result

    async def pause_device(
        self, device_id: str, paused: bool, network_id: Optional[str] = None
    ) -> bool:
        """Pause or unpause internet access for a device.

        This temporarily blocks internet access for the device without removing it
        from the network. The device remains connected but cannot access the internet.

        Args:
            device_id: ID of the device
            paused: True to pause internet access, False to resume
            network_id: ID of the network the device belongs to (uses preferred network if None)

        Returns:
            True if the operation was successful

        Raises:
            EeroException: If no network ID is available

        Note:
            This is different from blocking a device:
            - Paused: Device stays connected but has no internet access
            - Blocked: Device is completely removed from the network
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.devices.pause_device(network_id, device_id, paused)

        # Clear device cache on success
        if result:
            cache_key = f"{network_id}_{device_id}"
            if cache_key in self._cache.get("devices", {}):
                del self._cache["devices"][cache_key]

            # Also clear devices list cache
            cache_key = f"{network_id}_devices"
            if cache_key in self._cache.get("devices", {}):
                del self._cache["devices"][cache_key]

        return result

    async def get_paused_devices(self, network_id: Optional[str] = None) -> List[Dict]:
        """Get list of paused devices.

        Args:
            network_id: ID of the network (uses preferred network if None)

        Returns:
            List of paused devices

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)
        return await self._api.devices.get_paused_devices(network_id)

    async def pause_profile(
        self, profile_id: str, paused: bool, network_id: Optional[str] = None
    ) -> bool:
        """Pause or unpause internet access for a profile.

        Args:
            profile_id: ID of the profile
            paused: Whether to pause or unpause the profile
            network_id: ID of the network the profile belongs to (uses preferred network if None)

        Returns:
            True if the operation was successful

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.profiles.pause_profile(network_id, profile_id, paused)

        # Clear profile cache on success
        if result:
            cache_key = f"{network_id}_{profile_id}"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

            # Also clear profiles list cache
            cache_key = f"{network_id}_profiles"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

        return result

    # ==================== Profile Device Management ====================

    async def get_profile_devices(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> List[Dict]:
        """Get devices assigned to a profile.

        Args:
            profile_id: ID of the profile
            network_id: ID of the network (uses preferred network if None)

        Returns:
            List of device data dictionaries

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)
        return await self._api.profiles.get_profile_devices(network_id, profile_id)

    async def set_profile_devices(
        self,
        profile_id: str,
        device_urls: List[str],
        network_id: Optional[str] = None,
    ) -> bool:
        """Set the devices assigned to a profile.

        This replaces all existing device assignments with the provided list.

        Args:
            profile_id: ID of the profile
            device_urls: List of device URLs to assign to the profile.
                        URLs should be in format: "/2.2/networks/{net_id}/devices/{dev_id}"
            network_id: ID of the network (uses preferred network if None)

        Returns:
            True if the operation was successful

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.profiles.set_profile_devices(network_id, profile_id, device_urls)

        # Clear profile cache on success
        if result:
            cache_key = f"{network_id}_{profile_id}"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

            # Also clear profiles list cache
            cache_key = f"{network_id}_profiles"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

        return result

    async def add_device_to_profile(
        self,
        profile_id: str,
        device_id: str,
        network_id: Optional[str] = None,
    ) -> bool:
        """Add a device to a profile.

        Args:
            profile_id: ID of the profile
            device_id: ID of the device to add
            network_id: ID of the network (uses preferred network if None)

        Returns:
            True if the operation was successful

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.profiles.add_device_to_profile(network_id, profile_id, device_id)

        # Clear profile cache on success
        if result:
            cache_key = f"{network_id}_{profile_id}"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

            cache_key = f"{network_id}_profiles"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

        return result

    async def remove_device_from_profile(
        self,
        profile_id: str,
        device_id: str,
        network_id: Optional[str] = None,
    ) -> bool:
        """Remove a device from a profile.

        Args:
            profile_id: ID of the profile
            device_id: ID of the device to remove
            network_id: ID of the network (uses preferred network if None)

        Returns:
            True if the operation was successful

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.profiles.remove_device_from_profile(
            network_id, profile_id, device_id
        )

        # Clear profile cache on success
        if result:
            cache_key = f"{network_id}_{profile_id}"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

            cache_key = f"{network_id}_profiles"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

        return result

    async def run_speed_test(self, network_id: Optional[str] = None) -> Dict:
        """Run a speed test on the network.

        Args:
            network_id: ID of the network to run the speed test on (uses preferred network if None)

        Returns:
            Speed test results

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        result = await self._api.networks.run_speed_test(network_id)

        # Clear network cache
        if network_id in self._cache.get("network", {}):
            del self._cache["network"][network_id]

        return result

    def set_preferred_network(self, network_id: str) -> None:
        """Set the preferred network ID to use for requests.

        Args:
            network_id: ID of the network to use
        """
        self._api.set_preferred_network(network_id)

    @property
    def preferred_network_id(self) -> Optional[str]:
        """Get the preferred network ID.

        Returns:
            Preferred network ID or None
        """
        return self._api.preferred_network_id

    # Additional API methods
    async def get_diagnostics(self, network_id: Optional[str] = None) -> Dict:
        """Get network diagnostics information.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Diagnostics data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.diagnostics.get_diagnostics(target_network_id)

    async def run_diagnostics(self, network_id: Optional[str] = None) -> Dict:
        """Run network diagnostics.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Diagnostics results
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.diagnostics.run_diagnostics(target_network_id)

    async def get_settings(self, network_id: Optional[str] = None) -> Dict:
        """Get network settings.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Settings data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.settings.get_settings(target_network_id)

    async def get_insights(self, network_id: Optional[str] = None) -> Dict:
        """Get network insights.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Insights data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.insights.get_insights(target_network_id)

    async def get_routing(self, network_id: Optional[str] = None) -> Dict:
        """Get network routing information.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Routing data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.routing.get_routing(target_network_id)

    async def get_thread(self, network_id: Optional[str] = None) -> Dict:
        """Get network thread information.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Thread data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.thread.get_thread(target_network_id)

    async def get_support(self, network_id: Optional[str] = None) -> Dict:
        """Get network support information.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Support data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.support.get_support(target_network_id)

    async def get_blacklist(self, network_id: Optional[str] = None) -> List[Dict]:
        """Get device blacklist.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            List of blacklisted devices
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.blacklist.get_blacklist(target_network_id)

    async def get_reservations(self, network_id: Optional[str] = None) -> List[Dict]:
        """Get DHCP reservations.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            List of DHCP reservations
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.reservations.get_reservations(target_network_id)

    async def get_forwards(self, network_id: Optional[str] = None) -> List[Dict]:
        """Get port forwards.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            List of port forwards
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.forwards.get_forwards(target_network_id)

    async def get_transfer_stats(
        self, network_id: Optional[str] = None, device_id: Optional[str] = None
    ) -> Dict:
        """Get transfer statistics.

        Args:
            network_id: ID of the network (uses preferred network if not specified)
            device_id: Optional device ID to get stats for

        Returns:
            Transfer statistics
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.transfer.get_transfer_stats(target_network_id, device_id)

    async def get_burst_reporters(self, network_id: Optional[str] = None) -> List[Dict]:
        """Get burst reporters.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            List of burst reporters
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.burst_reporters.get_burst_reporters(target_network_id)

    async def get_ac_compat(self, network_id: Optional[str] = None) -> Dict:
        """Get AC compatibility information.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            AC compatibility data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.ac_compat.get_ac_compat(target_network_id)

    async def get_ouicheck(self, network_id: Optional[str] = None) -> Dict:
        """Get OUI check information.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            OUI check data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.ouicheck.get_ouicheck(target_network_id)

    async def get_password(self, network_id: Optional[str] = None) -> Dict:
        """Get password information.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Password data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.password.get_password(target_network_id)

    async def get_updates(self, network_id: Optional[str] = None) -> Dict:
        """Get update information.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Update data
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.updates.get_updates(target_network_id)

    # ==================== Phase 1: Premium Features ====================

    async def get_activity(self, network_id: Optional[str] = None) -> Dict:
        """Get network activity summary (Eero Plus feature).

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Activity summary data

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity(target_network_id)

    async def get_activity_clients(self, network_id: Optional[str] = None) -> List[Dict]:
        """Get per-client activity data (Eero Plus feature).

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            List of clients with their activity data

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity_clients(target_network_id)

    async def get_activity_for_device(
        self, device_id: str, network_id: Optional[str] = None
    ) -> Dict:
        """Get activity data for a specific device (Eero Plus feature).

        Args:
            device_id: ID of the device
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Activity data for the device

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity_for_device(target_network_id, device_id)

    async def get_activity_history(
        self, network_id: Optional[str] = None, period: str = "day"
    ) -> Dict:
        """Get historical activity data (Eero Plus feature).

        Args:
            network_id: ID of the network (uses preferred network if not specified)
            period: Time period - "hour", "day", "week", or "month"

        Returns:
            Historical activity data

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity_history(target_network_id, period)

    async def get_activity_categories(self, network_id: Optional[str] = None) -> List[Dict]:
        """Get activity data grouped by category (Eero Plus feature).

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Activity data grouped by category

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.activity.get_activity_categories(target_network_id)

    async def get_premium_status(self, network_id: Optional[str] = None) -> Dict:
        """Get Eero Plus/Eero Secure subscription status.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary containing:
            - premium_enabled: bool
            - premium_status: str
            - features: list
            - expires_at: str or None
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.networks.get_premium_status(target_network_id)

    async def is_premium(self, network_id: Optional[str] = None) -> bool:
        """Check if the network has an active Eero Plus subscription.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if Eero Plus is active, False otherwise
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.networks.is_premium(target_network_id)

    async def get_blocked_applications(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> List[str]:
        """Get blocked applications for a profile (Eero Plus feature).

        Args:
            profile_id: ID of the profile
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            List of blocked application identifiers

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.profiles.get_blocked_applications(target_network_id, profile_id)

    async def set_blocked_applications(
        self,
        profile_id: str,
        applications: List[str],
        network_id: Optional[str] = None,
    ) -> bool:
        """Set blocked applications for a profile (Eero Plus feature).

        Args:
            profile_id: ID of the profile
            applications: List of application identifiers to block
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful

        Note:
            Requires active Eero Plus subscription.
            Common app identifiers: "facebook", "instagram", "tiktok", "youtube",
            "netflix", "fortnite", "minecraft", "roblox", etc.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        result = await self._api.profiles.set_blocked_applications(
            target_network_id, profile_id, applications
        )

        # Clear profile cache on success
        if result:
            cache_key = f"{target_network_id}_{profile_id}"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

        return result

    async def add_blocked_application(
        self,
        profile_id: str,
        application: str,
        network_id: Optional[str] = None,
    ) -> bool:
        """Add a single application to the blocked list.

        Args:
            profile_id: ID of the profile
            application: Application identifier to block
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.profiles.add_blocked_application(
            target_network_id, profile_id, application
        )

    async def remove_blocked_application(
        self,
        profile_id: str,
        application: str,
        network_id: Optional[str] = None,
    ) -> bool:
        """Remove a single application from the blocked list.

        Args:
            profile_id: ID of the profile
            application: Application identifier to unblock
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.profiles.remove_blocked_application(
            target_network_id, profile_id, application
        )

    async def set_network_name(self, name: str, network_id: Optional[str] = None) -> bool:
        """Set the network name (SSID).

        Note: This may require a network restart to take effect.

        Args:
            name: New network name
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        result = await self._api.networks.set_network_name(target_network_id, name)

        # Clear network cache on success
        if result and target_network_id in self._cache.get("network", {}):
            del self._cache["network"][target_network_id]

        return result

    # ==================== Phase 2: Device Controls ====================

    async def get_led_status(self, eero_id: str, network_id: Optional[str] = None) -> Dict:
        """Get LED status for an Eero device.

        Args:
            eero_id: ID of the Eero device
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary with led_on and led_brightness
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.get_led_status(target_network_id, eero_id)

    async def set_led(
        self,
        eero_id: str,
        enabled: bool,
        network_id: Optional[str] = None,
    ) -> bool:
        """Set LED on/off for an Eero device.

        Args:
            eero_id: ID of the Eero device
            enabled: True to turn LED on, False to turn off
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        result = await self._api.eeros.set_led(target_network_id, eero_id, enabled)

        # Clear eero cache on success
        if result:
            cache_key = f"{target_network_id}_eeros"
            if cache_key in self._cache.get("eeros", {}):
                del self._cache["eeros"][cache_key]

        return result

    async def set_led_brightness(
        self,
        eero_id: str,
        brightness: int,
        network_id: Optional[str] = None,
    ) -> bool:
        """Set LED brightness for an Eero device.

        Args:
            eero_id: ID of the Eero device
            brightness: Brightness level (0-100)
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.set_led_brightness(target_network_id, eero_id, brightness)

    async def get_nightlight(self, eero_id: str, network_id: Optional[str] = None) -> Dict:
        """Get nightlight settings for an Eero Beacon device.

        Note: Nightlight is only available on Eero Beacon devices.

        Args:
            eero_id: ID of the Eero Beacon device
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary with nightlight settings
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.get_nightlight(target_network_id, eero_id)

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
    ) -> bool:
        """Set nightlight settings for an Eero Beacon device.

        Note: Nightlight is only available on Eero Beacon devices.

        Args:
            eero_id: ID of the Eero Beacon device
            enabled: True to enable nightlight, False to disable
            brightness: Brightness level (0-100)
            schedule_enabled: True to enable schedule mode
            schedule_on: Time to turn on (HH:MM format)
            schedule_off: Time to turn off (HH:MM format)
            ambient_light_enabled: True to auto-adjust based on ambient light
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        result = await self._api.eeros.set_nightlight(
            target_network_id,
            eero_id,
            enabled=enabled,
            brightness=brightness,
            schedule_enabled=schedule_enabled,
            schedule_on=schedule_on,
            schedule_off=schedule_off,
            ambient_light_enabled=ambient_light_enabled,
        )

        # Clear eero cache on success
        if result:
            cache_key = f"{target_network_id}_eeros"
            if cache_key in self._cache.get("eeros", {}):
                del self._cache["eeros"][cache_key]

        return result

    async def set_nightlight_brightness(
        self,
        eero_id: str,
        brightness: int,
        network_id: Optional[str] = None,
    ) -> bool:
        """Set nightlight brightness for an Eero Beacon device.

        Args:
            eero_id: ID of the Eero Beacon device
            brightness: Brightness level (0-100)
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.set_nightlight_brightness(
            target_network_id, eero_id, brightness
        )

    async def set_nightlight_schedule(
        self,
        eero_id: str,
        enabled: bool,
        on_time: Optional[str] = None,
        off_time: Optional[str] = None,
        network_id: Optional[str] = None,
    ) -> bool:
        """Set nightlight schedule for an Eero Beacon device.

        Args:
            eero_id: ID of the Eero Beacon device
            enabled: True to enable schedule
            on_time: Time to turn on (HH:MM format)
            off_time: Time to turn off (HH:MM format)
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.set_nightlight_schedule(
            target_network_id, eero_id, enabled, on_time, off_time
        )

    # ==================== Backup Network (Eero Plus) ====================

    async def get_backup_network(self, network_id: Optional[str] = None) -> Dict:
        """Get backup network configuration (Eero Plus feature).

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary containing backup network settings

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.get_backup_network(target_network_id)

    async def get_backup_status(self, network_id: Optional[str] = None) -> Dict:
        """Get current backup network status (Eero Plus feature).

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary containing current backup status

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.get_backup_status(target_network_id)

    async def set_backup_network(
        self,
        enabled: bool,
        network_id: Optional[str] = None,
    ) -> bool:
        """Enable or disable backup network (Eero Plus feature).

        Args:
            enabled: True to enable, False to disable
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.set_backup_network(target_network_id, enabled)

    async def configure_backup_network(
        self,
        enabled: Optional[bool] = None,
        phone_number: Optional[str] = None,
        network_id: Optional[str] = None,
    ) -> bool:
        """Configure backup network settings (Eero Plus feature).

        Args:
            enabled: True to enable, False to disable
            phone_number: Phone number to use for backup connection
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.configure_backup_network(
            target_network_id, enabled=enabled, phone_number=phone_number
        )

    async def is_using_backup(self, network_id: Optional[str] = None) -> bool:
        """Check if the network is currently using backup connection.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if backup connection is currently active

        Note:
            Requires active Eero Plus subscription.
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.is_using_backup(target_network_id)

    # ==================== Phase 3: Advanced Features ====================

    # --- Schedule API ---

    async def get_profile_schedule(self, profile_id: str, network_id: Optional[str] = None) -> Dict:
        """Get internet access schedule for a profile.

        Args:
            profile_id: ID of the profile
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary containing schedule configuration
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.get_profile_schedule(target_network_id, profile_id)

    async def set_profile_schedule(
        self,
        profile_id: str,
        time_blocks: List[Dict],
        network_id: Optional[str] = None,
    ) -> bool:
        """Set internet access schedule for a profile.

        Args:
            profile_id: ID of the profile
            time_blocks: List of time blocks with days, start, end
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        result = await self._api.schedule.set_profile_schedule(
            target_network_id, profile_id, time_blocks
        )

        # Clear profile cache on success
        if result:
            cache_key = f"{target_network_id}_{profile_id}"
            if cache_key in self._cache.get("profiles", {}):
                del self._cache["profiles"][cache_key]

        return result

    async def enable_bedtime(
        self,
        profile_id: str,
        start_time: str,
        end_time: str,
        days: Optional[List[str]] = None,
        network_id: Optional[str] = None,
    ) -> bool:
        """Enable bedtime mode for a profile.

        Args:
            profile_id: ID of the profile
            start_time: Time to start blocking (HH:MM format, e.g., "21:00")
            end_time: Time to end blocking (HH:MM format, e.g., "07:00")
            days: Days to apply (defaults to all days)
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.enable_bedtime(
            target_network_id, profile_id, start_time, end_time, days
        )

    async def clear_profile_schedule(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> bool:
        """Clear all schedules for a profile.

        Args:
            profile_id: ID of the profile
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.clear_profile_schedule(target_network_id, profile_id)

    # --- DNS API ---

    async def get_dns_settings(self, network_id: Optional[str] = None) -> Dict:
        """Get DNS configuration for the network.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary containing DNS settings
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns.get_dns_settings(target_network_id)

    async def set_dns_caching(self, enabled: bool, network_id: Optional[str] = None) -> bool:
        """Enable or disable DNS caching.

        Args:
            enabled: True to enable DNS caching, False to disable
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns.set_dns_caching(target_network_id, enabled)

    async def set_custom_dns(
        self, dns_servers: List[str], network_id: Optional[str] = None
    ) -> bool:
        """Set custom DNS servers.

        Args:
            dns_servers: List of DNS server IPs (max 2)
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns.set_custom_dns(target_network_id, dns_servers)

    async def set_dns_mode(
        self,
        mode: str,
        custom_servers: Optional[List[str]] = None,
        network_id: Optional[str] = None,
    ) -> bool:
        """Set DNS mode for the network.

        Args:
            mode: DNS mode - "auto", "custom", "cloudflare", "google", "opendns"
            custom_servers: Custom DNS servers (required if mode is "custom")
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns.set_dns_mode(target_network_id, mode, custom_servers)

    # --- SQM/QoS API ---

    async def get_sqm_settings(self, network_id: Optional[str] = None) -> Dict:
        """Get SQM/QoS settings for the network.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary containing SQM settings
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.sqm.get_sqm_settings(target_network_id)

    async def set_sqm_enabled(self, enabled: bool, network_id: Optional[str] = None) -> bool:
        """Enable or disable SQM (Smart Queue Management).

        Args:
            enabled: True to enable SQM, False to disable
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.sqm.set_sqm_enabled(target_network_id, enabled)

    async def configure_sqm(
        self,
        enabled: bool,
        upload_mbps: Optional[int] = None,
        download_mbps: Optional[int] = None,
        network_id: Optional[str] = None,
    ) -> bool:
        """Configure SQM settings.

        Args:
            enabled: True to enable SQM, False to disable
            upload_mbps: Upload bandwidth limit in Mbps
            download_mbps: Download bandwidth limit in Mbps
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.sqm.configure_sqm(
            target_network_id, enabled, upload_mbps, download_mbps
        )

    # --- Device Priority API ---

    async def get_device_priority(self, device_id: str, network_id: Optional[str] = None) -> Dict:
        """Get priority settings for a device.

        Args:
            device_id: ID of the device
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary with priority settings
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.devices.get_device_priority(target_network_id, device_id)

    async def set_device_priority(
        self,
        device_id: str,
        prioritized: bool,
        duration_minutes: Optional[int] = None,
        network_id: Optional[str] = None,
    ) -> bool:
        """Set priority for a device (bandwidth prioritization).

        Args:
            device_id: ID of the device
            prioritized: True to prioritize, False to remove priority
            duration_minutes: Duration in minutes (0 or None = indefinite)
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        result = await self._api.devices.set_device_priority(
            target_network_id, device_id, prioritized, duration_minutes
        )

        # Clear device cache on success
        if result:
            cache_key = f"{target_network_id}_devices"
            if cache_key in self._cache.get("devices", {}):
                del self._cache["devices"][cache_key]

        return result

    async def prioritize_device(
        self,
        device_id: str,
        duration_minutes: int = 0,
        network_id: Optional[str] = None,
    ) -> bool:
        """Prioritize a device for bandwidth.

        Args:
            device_id: ID of the device
            duration_minutes: Duration in minutes (0 = indefinite)
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.devices.prioritize_device(
            target_network_id, device_id, duration_minutes
        )

    async def deprioritize_device(self, device_id: str, network_id: Optional[str] = None) -> bool:
        """Remove priority from a device.

        Args:
            device_id: ID of the device
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.devices.deprioritize_device(target_network_id, device_id)

    async def get_prioritized_devices(self, network_id: Optional[str] = None) -> List[Dict]:
        """Get list of prioritized devices.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            List of prioritized devices
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.devices.get_prioritized_devices(target_network_id)

    # --- Security API ---

    async def get_security_settings(self, network_id: Optional[str] = None) -> Dict:
        """Get security settings for the network.

        Args:
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            Dictionary containing security settings
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.get_security_settings(target_network_id)

    async def set_wpa3(self, enabled: bool, network_id: Optional[str] = None) -> bool:
        """Enable or disable WPA3 encryption.

        Note: This may require a network restart to take effect.

        Args:
            enabled: True to enable WPA3, False to use WPA2
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_wpa3(target_network_id, enabled)

    async def set_band_steering(self, enabled: bool, network_id: Optional[str] = None) -> bool:
        """Enable or disable band steering.

        Args:
            enabled: True to enable band steering, False to disable
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_band_steering(target_network_id, enabled)

    async def set_upnp(self, enabled: bool, network_id: Optional[str] = None) -> bool:
        """Enable or disable UPnP.

        Args:
            enabled: True to enable UPnP, False to disable
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_upnp(target_network_id, enabled)

    async def set_ipv6(self, enabled: bool, network_id: Optional[str] = None) -> bool:
        """Enable or disable IPv6.

        Args:
            enabled: True to enable IPv6, False to disable
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_ipv6(target_network_id, enabled)

    async def set_thread_enabled(self, enabled: bool, network_id: Optional[str] = None) -> bool:
        """Enable or disable Thread (for smart home devices).

        Args:
            enabled: True to enable Thread, False to disable
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.set_thread(target_network_id, enabled)

    async def configure_security(
        self,
        wpa3: Optional[bool] = None,
        band_steering: Optional[bool] = None,
        upnp: Optional[bool] = None,
        ipv6: Optional[bool] = None,
        thread: Optional[bool] = None,
        network_id: Optional[str] = None,
    ) -> bool:
        """Configure multiple security settings at once.

        Args:
            wpa3: Enable/disable WPA3
            band_steering: Enable/disable band steering
            upnp: Enable/disable UPnP
            ipv6: Enable/disable IPv6
            thread: Enable/disable Thread
            network_id: ID of the network (uses preferred network if not specified)

        Returns:
            True if the operation was successful
        """
        target_network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.configure_security(
            target_network_id,
            wpa3=wpa3,
            band_steering=band_steering,
            upnp=upnp,
            ipv6=ipv6,
            thread=thread,
        )
