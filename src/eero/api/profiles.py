"""Profiles API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
from typing import Any, Dict, List

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class ProfilesAPI(AuthenticatedAPI):
    """Profiles API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ProfilesAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_profiles(self, network_id: str) -> Dict[str, Any]:
        """Get list of profiles - returns raw Eero API response.

        Args:
            network_id: ID of the network to get profiles from

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting profiles for network %s", network_id)
        return await self.get(f"networks/{network_id}/profiles", auth_token=auth_token)

    async def get_profile(self, network_id: str, profile_id: str) -> Dict[str, Any]:
        """Get information about a specific profile - returns raw Eero API response.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile to get

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting profile %s in network %s", profile_id, network_id)
        return await self.get(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
        )

    async def pause_profile(self, network_id: str, profile_id: str, paused: bool) -> Dict[str, Any]:
        """Pause or unpause internet access for a profile - returns raw Eero API response.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            paused: Whether to pause or unpause the profile

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("%s profile %s", "Pausing" if paused else "Unpausing", profile_id)

        return await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"paused": paused},
        )

    async def get_profile_devices(self, network_id: str, profile_id: str) -> Dict[str, Any]:
        """Get profile data including devices - returns raw Eero API response.

        The devices are in the 'devices' field of the response data.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting devices for profile %s", profile_id)
        return await self.get(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
        )

    async def set_profile_devices(
        self,
        network_id: str,
        profile_id: str,
        device_urls: List[str],
    ) -> Dict[str, Any]:
        """Set the devices assigned to a profile - returns raw Eero API response.

        This replaces all existing device assignments with the provided list.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            device_urls: List of device URLs to assign to the profile.
                        URLs should be in format: "/2.2/networks/{net_id}/devices/{dev_id}"

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

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

        return await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"devices": devices_payload},
        )

    async def update_profile_content_filter(
        self, network_id: str, profile_id: str, filters: Dict[str, bool]
    ) -> Dict[str, Any]:
        """Update content filtering settings for a profile - returns raw Eero API response.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            filters: Dictionary of filter settings to update

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

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
                _LOGGER.warning("Ignoring invalid filter setting: %s", key)

        _LOGGER.debug("Updating content filter for profile %s: %s", profile_id, content_filter)

        return await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"content_filter": content_filter},
        )

    async def update_profile_block_list(
        self,
        network_id: str,
        profile_id: str,
        domains: List[str],
        block: bool = True,
    ) -> Dict[str, Any]:
        """Update custom domain block/allow list for a profile - returns raw Eero API response.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            domains: List of domains to block or allow
            block: True to add to block list, False for allow list

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        list_type = "custom_block_list" if block else "custom_allow_list"
        _LOGGER.debug(
            "Updating %s list for profile %s with %d domains",
            "block" if block else "allow",
            profile_id,
            len(domains),
        )

        return await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={list_type: domains},
        )

    async def get_blocked_applications(self, network_id: str, profile_id: str) -> Dict[str, Any]:
        """Get blocked applications for a profile - returns raw Eero API response.

        Eero Plus feature. The blocked applications are in the 'blocked_applications'
        or 'premium_dns.blocked_applications' field of the response data.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting blocked applications for profile %s", profile_id)
        return await self.get(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
        )

    async def set_blocked_applications(
        self,
        network_id: str,
        profile_id: str,
        applications: List[str],
    ) -> Dict[str, Any]:
        """Set blocked applications for a profile - returns raw Eero API response.

        Args:
            network_id: ID of the network the profile belongs to
            profile_id: ID of the profile
            applications: List of application identifiers to block

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

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

        return await self.put(
            f"networks/{network_id}/profiles/{profile_id}",
            auth_token=auth_token,
            json={"blocked_applications": applications},
        )
