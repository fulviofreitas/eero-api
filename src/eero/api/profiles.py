"""Profiles API for Eero."""

import logging
from typing import Any, Dict, List

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class ProfilesAPI(AuthenticatedAPI):
    """Profiles API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ProfilesAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_profiles(self, network_id: str) -> List[Dict[str, Any]]:
        """Get list of profiles.

        Args:
            network_id: ID of the network to get profiles from

        Returns:
            List of profile data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting profiles for network {network_id}")

        # Simplified path construction
        response = await self.get(
            f"networks/{network_id}/profiles",
            auth_token=auth_token,
        )

        # Handle different response formats
        data = response.get("data", [])
        if isinstance(data, list):
            # Data is directly a list of profiles
            profiles_data = data
        elif isinstance(data, dict) and "data" in data:
            # Data is a dictionary with a nested data field
            profiles_data = data.get("data", [])
        else:
            # Fallback to empty list
            profiles_data = []

        _LOGGER.debug(f"Found {len(profiles_data)} profiles")

        return profiles_data

    async def get_profile(self, network_id: str, profile_id: str) -> Dict[str, Any]:
        """Get information about a specific profile.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile to get

        Returns:
            Profile data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting profile {profile_id} in network {network_id}")

        # Simplified path construction
        response = await self.get(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def pause_profile(self, network_id: str, profile_id: str, paused: bool) -> bool:
        """Pause or unpause internet access for a profile.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            paused: Whether to pause or unpause the profile

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"{'Pausing' if paused else 'Unpausing'} profile {profile_id}")

        # Simplified path construction
        response = await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"paused": paused},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    # ==================== Profile Device Management ====================

    async def get_profile_devices(self, network_id: str, profile_id: str) -> List[Dict[str, Any]]:
        """Get devices assigned to a profile.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile

        Returns:
            List of device data dictionaries with 'url' field containing device URL

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting devices for profile %s", profile_id)

        response = await self.get(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
        )

        data = response.get("data", {})
        devices = data.get("devices", [])

        # Ensure we return a list of dicts with 'url' field
        if isinstance(devices, list):
            return devices
        return []

    async def set_profile_devices(
        self,
        network_id: str,
        profile_id: str,
        device_urls: List[str],
    ) -> bool:
        """Set the devices assigned to a profile.

        This replaces all existing device assignments with the provided list.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            device_urls: List of device URLs to assign to the profile.
                        URLs should be in format: "/2.2/networks/{net_id}/devices/{dev_id}"

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error

        Example:
            device_urls = [
                "/2.2/networks/12345/devices/abc123",
                "/2.2/networks/12345/devices/def456",
            ]
            await api.set_profile_devices(network_id, profile_id, device_urls)
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        # Format devices as list of dicts with 'url' key (API format)
        devices_payload = [{"url": url} for url in device_urls]

        _LOGGER.debug(
            "Setting %d devices for profile %s",
            len(device_urls),
            profile_id,
        )

        response = await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"devices": devices_payload},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def add_device_to_profile(
        self,
        network_id: str,
        profile_id: str,
        device_id: str,
    ) -> bool:
        """Add a device to a profile.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            device_id: ID of the device to add

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        # Get current devices
        current_devices = await self.get_profile_devices(network_id, profile_id)
        current_urls = [d.get("url", "") for d in current_devices if isinstance(d, dict)]

        # Build device URL
        device_url = f"/2.2/networks/{network_id}/devices/{device_id}"

        # Check if already in profile
        if device_url in current_urls:
            _LOGGER.debug("Device %s is already in profile %s", device_id, profile_id)
            return True

        # Add new device
        updated_urls = current_urls + [device_url]
        return await self.set_profile_devices(network_id, profile_id, updated_urls)

    async def remove_device_from_profile(
        self,
        network_id: str,
        profile_id: str,
        device_id: str,
    ) -> bool:
        """Remove a device from a profile.

        Args:
            network_id: ID of the network
            profile_id: ID of the profile
            device_id: ID of the device to remove

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        # Get current devices
        current_devices = await self.get_profile_devices(network_id, profile_id)
        current_urls = [d.get("url", "") for d in current_devices if isinstance(d, dict)]

        # Build device URL
        device_url = f"/2.2/networks/{network_id}/devices/{device_id}"

        # Check if not in profile
        if device_url not in current_urls:
            _LOGGER.debug("Device %s is not in profile %s", device_id, profile_id)
            return True

        # Remove device
        updated_urls = [url for url in current_urls if url != device_url]
        return await self.set_profile_devices(network_id, profile_id, updated_urls)

    # ==================== Content Filtering ====================

    async def update_profile_content_filter(
        self, network_id: str, profile_id: str, filters: Dict[str, bool]
    ) -> bool:
        """Update content filtering settings for a profile.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            filters: Dictionary of filter settings to update

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        # Validate filter settings
        valid_filters = {
            "adblock",
            "adblock_plus",
            "safe_search",
            "block_malware",
            "block_illegal",
            "block_violent",
            "block_adult",
            "youtube_restricted",
        }

        content_filter = {}
        for key, value in filters.items():
            if key in valid_filters:
                content_filter[key] = value
            else:
                _LOGGER.warning(f"Ignoring invalid filter setting: {key}")

        _LOGGER.debug(f"Updating content filter for profile {profile_id}: {content_filter}")

        # Simplified path construction
        response = await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"content_filter": content_filter},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def update_profile_block_list(
        self,
        network_id: str,
        profile_id: str,
        domains: List[str],
        block: bool = True,
    ) -> bool:
        """Update custom domain block/allow list for a profile.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            domains: List of domains to block or allow
            block: True to add to block list, False for allow list

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        list_type = "custom_block_list" if block else "custom_allow_list"
        _LOGGER.debug(
            f"Updating {'block' if block else 'allow'} list for profile {profile_id} with {len(domains)} domains"
        )

        # Simplified path construction
        response = await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={list_type: domains},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def get_blocked_applications(self, network_id: str, profile_id: str) -> List[str]:
        """Get blocked applications for a profile (Eero Plus feature).

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile

        Returns:
            List of blocked application identifiers

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting blocked applications for profile %s", profile_id)

        # Get profile data and extract blocked applications
        response = await self.get(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
        )

        data = response.get("data", {})

        # Try to extract blocked applications from various possible locations
        blocked_apps = []

        # Check premium_dns.blocked_applications
        premium_dns = data.get("premium_dns", {})
        if isinstance(premium_dns, dict):
            blocked_apps = premium_dns.get("blocked_applications", [])

        # Also check direct blocked_applications field
        if not blocked_apps:
            blocked_apps = data.get("blocked_applications", [])

        return blocked_apps if isinstance(blocked_apps, list) else []

    async def set_blocked_applications(
        self,
        network_id: str,
        profile_id: str,
        applications: List[str],
    ) -> bool:
        """Set blocked applications for a profile (Eero Plus feature).

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            applications: List of application identifiers to block

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error

        Note:
            Common application identifiers include:
            - "facebook", "instagram", "tiktok", "snapchat" (social media)
            - "youtube", "netflix", "twitch" (streaming)
            - "fortnite", "minecraft", "roblox" (gaming)
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(
            "Setting %d blocked applications for profile %s",
            len(applications),
            profile_id,
        )

        response = await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"blocked_applications": applications},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def add_blocked_application(
        self,
        network_id: str,
        profile_id: str,
        application: str,
    ) -> bool:
        """Add a single application to the blocked list.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            application: Application identifier to block

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        # Get current blocked apps
        current_apps = await self.get_blocked_applications(network_id, profile_id)

        if application in current_apps:
            _LOGGER.debug("Application %s is already blocked", application)
            return True

        # Add new app to the list
        updated_apps = current_apps + [application]
        return await self.set_blocked_applications(network_id, profile_id, updated_apps)

    async def remove_blocked_application(
        self,
        network_id: str,
        profile_id: str,
        application: str,
    ) -> bool:
        """Remove a single application from the blocked list.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            application: Application identifier to unblock

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        # Get current blocked apps
        current_apps = await self.get_blocked_applications(network_id, profile_id)

        if application not in current_apps:
            _LOGGER.debug("Application %s is not blocked", application)
            return True

        # Remove app from the list
        updated_apps = [app for app in current_apps if app != application]
        return await self.set_blocked_applications(network_id, profile_id, updated_apps)
