"""Profiles API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

A profile's body has exactly four fields: ``devices``, ``name``, ``paused``,
``url``. Content filtering, block lists, and blocked applications are not
profile fields at all -- writing them here was a silent no-op (live-verified;
they never persisted). That functionality is served by the DNS-policy
resource family instead.
"""

from typing import Any, Dict, List, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._params import resolve_nested_url
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import self_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)


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

    def _profile_url(self, network: str, profile: str) -> str:
        """Resolve a single profile's URL from a network ID and a profile identifier.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.

        Returns:
            The absolute profile URL.
        """
        return resolve_nested_url(network, profile, prefix="profiles")

    async def get_profiles(
        self, network: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get list of profiles - returns raw Eero API response.

        Args:
            network: ID of the network to get profiles from.
            parent: The cached network envelope, if the caller has one.
                Preferred over ``network`` to resolve the ``profiles`` link
                when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network,
            "networks/{id}/profiles",
            link="profiles",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        _LOGGER.debug("Getting profiles for network %s", network)
        return await self.get(url, auth_token=auth_token)

    async def get_profile(
        self,
        network: str,
        profile: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get information about a specific profile - returns raw Eero API response.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            parent: The profile's own cached envelope, if the caller has
                one. When supplied, its own ``url`` is used and
                ``network``/``profile`` are ignored for URL resolution.
                Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        resolved_parent = as_envelope(parent)
        url = (self_url(resolved_parent) if resolved_parent is not None else None) or (
            self._profile_url(network, profile)
        )

        _LOGGER.debug("Getting profile %s in network %s", profile, network)
        return await self.get(url, auth_token=auth_token)

    async def _update_profile(
        self,
        network: str,
        profile: str,
        payload: Dict[str, Any],
        *,
        parent: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        """Issue a single PUT against a profile's own URL.

        Every profile write goes through here, so the URL resolution and
        auth guard live in one place. The body is passed through unchanged
        -- callers are responsible for restricting it to the profile's four
        fields (``devices``, ``name``, ``paused``, ``url``).

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            payload: The JSON body to PUT.
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        resolved_parent = as_envelope(parent)
        url = (self_url(resolved_parent) if resolved_parent is not None else None) or (
            self._profile_url(network, profile)
        )
        warn_uncharacterised_write(_LOGGER, "update profile")
        return await self.put(url, auth_token=auth_token, json=payload)

    async def pause_profile(
        self,
        network: str,
        profile: str,
        paused: bool,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Pause or unpause internet access for a profile - returns raw Eero API response.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            paused: Whether to pause or unpause the profile.
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        _LOGGER.debug("%s profile %s", "Pausing" if paused else "Unpausing", profile)
        return await self._update_profile(network, profile, {"paused": paused}, parent=parent)

    async def get_profile_devices(
        self,
        network: str,
        profile: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get profile data including devices - returns raw Eero API response.

        The devices are in the 'devices' field of the response data.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        return await self.get_profile(network, profile, parent=parent)

    async def set_profile_devices(
        self,
        network: str,
        profile: str,
        device_urls: List[str],
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set the devices assigned to a profile - returns raw Eero API response.

        This replaces all existing device assignments with the provided list.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            device_urls: List of device URLs to assign to the profile.
                        URLs should be in format: "/2.2/networks/{net_id}/devices/{dev_id}"
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error

        Example:
            device_urls = [
                "/2.2/networks/network-id-placeholder/devices/device-id-placeholder",
            ]
            await api.set_profile_devices(network, profile, device_urls)
        """
        devices_payload = [{"url": url} for url in device_urls]
        warn_uncharacterised_write(_LOGGER, "set devices for profile")
        _LOGGER.debug("Setting %d devices for profile %s", len(device_urls), profile)
        return await self._update_profile(
            network, profile, {"devices": devices_payload}, parent=parent
        )

    async def create_profile(
        self,
        network: str,
        name: str,
        *,
        devices: Optional[List[str]] = None,
        paused: Optional[bool] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new profile on the network - returns raw Eero API response.

        POSTs a ``ProfileUpdateRequest``-shaped body (``devices``, ``name``,
        ``paused``) to the network's ``profiles`` link.

        Args:
            network: ID of the network to create the profile on.
            name: Name for the new profile.
            devices: Optional list of device URLs to assign at creation
                time, in the ``[{"url": ...}, ...]`` request shape. Omitted
                from the request when ``None``.
            paused: Optional initial paused state. Omitted from the request
                when ``None``.
            parent: The cached network envelope, if the caller has one.
                Preferred over ``network`` to resolve the ``profiles`` link
                when supplied.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
            The data field contains the full profile object including
            the assigned URL/ID.

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network,
            "networks/{id}/profiles",
            link="profiles",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )

        payload: Dict[str, Any] = {"name": name}
        if devices is not None:
            payload["devices"] = [{"url": device_url} for device_url in devices]
        if paused is not None:
            payload["paused"] = paused

        warn_uncharacterised_write(_LOGGER, "create profile for network")
        _LOGGER.debug("Creating profile '%s' in network %s", name, network)
        return await self.post(url, auth_token=auth_token, json=payload)

    async def rename_profile(
        self,
        network: str,
        profile: str,
        name: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Rename an existing profile - returns raw Eero API response.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.
            name: New name for the profile.
            parent: The profile's own cached envelope, if the caller has one.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        _LOGGER.debug("Renaming profile %s to '%s'", profile, name)
        return await self._update_profile(network, profile, {"name": name}, parent=parent)

    async def delete_profile(self, network: str, profile: str) -> Dict[str, Any]:
        """Delete a profile from the network - returns raw Eero API response.

        Devices previously assigned to this profile will become unassigned.

        Args:
            network: ID of the network the profile belongs to.
            profile: The profile's bare ID, path, or absolute URL.

        Returns:
            Raw API response: {"meta": {"code": 200, ...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = self._profile_url(network, profile)
        warn_uncharacterised_write(_LOGGER, "delete profile")
        _LOGGER.debug("Deleting profile %s from network %s", profile, network)
        return await self.delete(url, auth_token=auth_token)
