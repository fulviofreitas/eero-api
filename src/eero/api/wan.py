"""Multi-static-IP and secondary WAN configuration API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.

This family is only served on API version 2.3
(`eero.const.API_VERSION_MULTISTATICIP` / `API_VERSION_SECONDARY_WAN`), unlike
most of this SDK's default 2.2 endpoints.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_MULTISTATICIP, API_VERSION_SECONDARY_WAN
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._params import resolve_nested_url
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)


class WanAPI(AuthenticatedAPI):
    """Multi-static-IP and secondary WAN configuration API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the WanAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_multistaticip(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get the network's multi-static-IP configuration - returns raw Eero API response.

        GETs the network's ``multistaticip`` sub-resource on API version
        2.3. This is a verified read.

        Note: on a network without the multi-static-IP feature, the API has
        been observed to return HTTP 404 with the error code
        ``error.network.multistaticip_not_found``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``multistaticip`` link is
                used instead of the default template. Read only; never
                mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroNotFoundException: If the network has no multi-static-IP
                configuration
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/multistaticip",
            link="multistaticip",
            parent=as_envelope(parent),
            version=API_VERSION_MULTISTATICIP,
        )
        _LOGGER.debug("Getting multi-static-IP configuration for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def set_multistaticip(self, network_id: str, config: Mapping[str, Any]) -> Dict[str, Any]:
        """Set the network's multi-static-IP configuration - returns raw Eero API response.

        Issues a JSON PUT to the network's ``multistaticip`` sub-resource on
        API version 2.3 with ``config`` forwarded unchanged. The API
        declares ``enabled``, ``type``, ``multistaticip_settings``
        (``router_ip``, ``subnet_ip``, ``subnet_mask``), and
        ``multistaticip_settings_nat_portfwd`` (``subnet_ip_start``,
        ``subnet_ip_end``) as the fields for this endpoint; this method
        performs no validation of ``config``'s keys or values.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_multistaticip`
            first, and only issue this write when the stored configuration
            differs from the desired one. Never retry a failed write in a
            loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            config: The multi-static-IP configuration, forwarded to the API
                unchanged.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(
            network_id, "networks/{id}/multistaticip", version=API_VERSION_MULTISTATICIP
        )
        warn_uncharacterised_write(_LOGGER, "set multi-static-IP configuration for network")
        return await self.put(url, auth_token=auth_token, json=dict(config))

    async def set_secondary_wan_config(
        self, network_id: str, config: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """Set per-device secondary-WAN access - returns raw Eero API response.

        Issues a JSON PUT to the network's
        ``devices/secondary_wan_config`` sub-resource on API version 2.3
        with ``config`` forwarded unchanged. The API declares ``devices``
        (a list of ``{"mac": ..., "secondary_wan_deny_access": ...}``
        entries) as the field for this endpoint; this method performs no
        validation of ``config``'s keys or values.

        .. warning::
            This is a settings-class write. Its side effects have not been
            confirmed against a live network, and the DNS write on the
            sibling ``networks/{id}/settings`` endpoint is confirmed to
            reboot every eero on the mesh. Treat this write as capable of
            doing the same: read the current configuration first, skip the
            write when it already matches, and never retry a failed write
            in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            config: The secondary-WAN device configuration, forwarded to the
                API unchanged.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(
            network_id,
            "networks/{id}/devices/secondary_wan_config",
            version=API_VERSION_SECONDARY_WAN,
        )
        warn_uncharacterised_write(
            _LOGGER,
            "set secondary WAN configuration for network "
            "-- may reboot every eero, like the confirmed DNS write path",
        )
        return await self.put(url, auth_token=auth_token, json=dict(config))

    async def set_device_secondary_wan_access(
        self, network_id: str, mac: str, *, deny: bool
    ) -> Dict[str, Any]:
        """Set a single device's secondary-WAN access - returns raw Eero API response.

        Issues a JSON PUT to the network's ``devices/{mac}`` sub-resource on
        API version 2.3 with ``{"secondary_wan_deny_access": bool}``.

        .. warning::
            This is a settings-class write. Its side effects have not been
            confirmed against a live network, and the DNS write on the
            sibling ``networks/{id}/settings`` endpoint is confirmed to
            reboot every eero on the mesh. Treat this write as capable of
            doing the same: read the current configuration first, skip the
            write when it already matches, and never retry a failed write
            in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            mac: The device's MAC address.
            deny: True to deny the device secondary-WAN access, False to
                allow it.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resolve_nested_url(
            network_id,
            mac,
            prefix="devices",
            version=API_VERSION_SECONDARY_WAN,
        )
        warn_uncharacterised_write(
            _LOGGER,
            "set secondary WAN access for device on network "
            "-- may reboot every eero, like the confirmed DNS write path",
        )
        return await self.put(url, auth_token=auth_token, json={"secondary_wan_deny_access": deny})
