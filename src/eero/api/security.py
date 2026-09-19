"""Security Settings API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import Envelope, resource_url, self_url, sub_resource_url

_LOGGER = logging.getLogger(__name__)

#: Valid values for the network's MLO (Multi-Link Operation) mode.
MLO_MODE_DISABLED = "disabled"
MLO_MODE_SINGLE = "single"
MLO_MODE_MULTI = "multi"
_MLO_MODES = frozenset({MLO_MODE_DISABLED, MLO_MODE_SINGLE, MLO_MODE_MULTI})


def _network_own_url(network_id: str, parent: Optional[Envelope]) -> str:
    """Resolve a network's own URL, preferring its parent envelope's ``url``."""
    if parent is not None:
        own = self_url(parent)
        if own is not None:
            return own
    return resource_url(network_id, "networks/{id}")


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

    async def get_security_settings(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get security settings for a network - returns raw Eero API response.

        Security settings are included in the network data. Look for fields like:
        wpa3, band_steering, upnp, ipv6_upstream, ipv6_downstream, thread, etc.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one. Read only; never mutated.

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
        return await self.get(
            _network_own_url(network_id, as_envelope(parent)), auth_token=auth_token
        )

    async def set_wpa3(
        self, network_id: str, enabled: bool, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enable or disable WPA3 encryption - returns raw Eero API response.

        Note: This may require a network restart to take effect.
        Not all devices support WPA3 - older devices may lose connectivity.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable WPA3, False to use WPA2
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``settings`` link is used
                instead of the default template. Read only; never mutated.

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

        url = sub_resource_url(
            network_id, "networks/{id}/settings", link="settings", parent=as_envelope(parent)
        )
        return await self.put(
            url,
            auth_token=auth_token,
            json={"wpa3": enabled},
        )

    async def set_band_steering(
        self, network_id: str, enabled: bool, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enable or disable band steering - returns raw Eero API response.

        Band steering automatically moves devices to the optimal
        frequency band (2.4GHz or 5GHz) for better performance.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable band steering, False to disable
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``settings`` link is used
                instead of the default template. Read only; never mutated.

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

        url = sub_resource_url(
            network_id, "networks/{id}/settings", link="settings", parent=as_envelope(parent)
        )
        return await self.put(
            url,
            auth_token=auth_token,
            json={"band_steering": enabled},
        )

    async def set_upnp(
        self, network_id: str, enabled: bool, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enable or disable UPnP (Universal Plug and Play) - returns raw Eero API response.

        UPnP allows devices to automatically configure port forwarding.
        Disabling can improve security but may break some applications.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable UPnP, False to disable
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``settings`` link is used
                instead of the default template. Read only; never mutated.

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

        url = sub_resource_url(
            network_id, "networks/{id}/settings", link="settings", parent=as_envelope(parent)
        )
        return await self.put(
            url,
            auth_token=auth_token,
            json={"upnp": enabled},
        )

    async def set_ipv6(
        self, network_id: str, enabled: bool, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enable or disable IPv6 - returns raw Eero API response.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable IPv6, False to disable
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``settings`` link is used
                instead of the default template. Read only; never mutated.

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

        url = sub_resource_url(
            network_id, "networks/{id}/settings", link="settings", parent=as_envelope(parent)
        )
        return await self.put(
            url,
            auth_token=auth_token,
            json={
                "ipv6_upstream": enabled,
                "ipv6_downstream": enabled,
            },
        )

    async def configure_security(
        self,
        network_id: str,
        wpa3: Optional[bool] = None,
        band_steering: Optional[bool] = None,
        upnp: Optional[bool] = None,
        ipv6: Optional[bool] = None,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Configure multiple security settings at once - returns raw Eero API response.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            wpa3: Enable/disable WPA3
            band_steering: Enable/disable band steering
            upnp: Enable/disable UPnP
            ipv6: Enable/disable IPv6
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``settings`` link is used
                instead of the default template. Read only; never mutated.

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

        if not payload:
            _LOGGER.warning("No security settings provided")
            return {"meta": {"code": 400}, "data": {}}

        _LOGGER.debug("Configuring security for network %s: %s", network_id, payload)

        url = sub_resource_url(
            network_id, "networks/{id}/settings", link="settings", parent=as_envelope(parent)
        )
        return await self.put(
            url,
            auth_token=auth_token,
            json=payload,
        )

    async def set_mlo_mode(
        self, network_id: str, mode: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Set the network's MLO (Multi-Link Operation) mode - returns raw Eero API response.

        Issues a JSON PUT to the network's ``mlo_mode`` sub-resource with
        ``{"mlo_mode": ...}``.

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
            mode: ``"disabled"``, ``"single"``, or ``"multi"``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``mlo_mode`` link is used
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``mode`` is not a declared MLO mode
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        if not isinstance(mode, str) or mode not in _MLO_MODES:
            raise EeroValidationException(
                "mode", f"must be one of {sorted(_MLO_MODES)}, got {mode!r}"
            )

        url = sub_resource_url(
            network_id, "networks/{id}/mlo_mode", link="mlo_mode", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(
            _LOGGER,
            f"set MLO mode for network {network_id} "
            "-- may reboot every eero, like the confirmed DNS write path",
        )
        return await self.put(url, auth_token=auth_token, json={"mlo_mode": mode})

    async def get_fast_transition(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get the network's 802.11r fast-transition setting - returns raw Eero API response.

        GETs the network's ``fast_transition`` sub-resource. This is a
        verified read.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``fast_transition`` link
                is used instead of the default template. Read only; never
                mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/fast_transition",
            link="fast_transition",
            parent=as_envelope(parent),
        )
        _LOGGER.debug("Getting fast transition setting for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def set_fast_transition(
        self, network_id: str, enabled: bool, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Set the network's 802.11r fast-transition setting - returns raw Eero API response.

        Issues a JSON PUT to the network's ``fast_transition`` sub-resource
        with ``{"fast_transition": bool}``.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_fast_transition`
            first, and only issue this write when the stored value differs
            from the desired one. Never retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable fast transition, False to disable.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``fast_transition`` link
                is used instead of the default template. Read only; never
                mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/fast_transition",
            link="fast_transition",
            parent=as_envelope(parent),
        )
        warn_uncharacterised_write(_LOGGER, f"set fast transition for network {network_id}")
        return await self.put(url, auth_token=auth_token, json={"fast_transition": enabled})

    async def set_passpoint_enabled(
        self, network_id: str, enabled: bool, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enable or disable Passpoint - returns raw Eero API response.

        Issues a JSON PUT to the network's ``passpoint/enabled``
        sub-resource with ``{"enabled": bool}``.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable Passpoint, False to disable.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``passpoint`` link is used
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/passpoint/enabled",
            link="passpoint",
            parent=as_envelope(parent),
        )
        warn_uncharacterised_write(_LOGGER, f"set Passpoint enabled for network {network_id}")
        return await self.put(url, auth_token=auth_token, json={"enabled": enabled})

    async def set_proxied_nodes(
        self, network_id: str, enabled: bool, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enable or disable proxied nodes - returns raw Eero API response.

        Issues a JSON PUT to the network's ``proxied_nodes`` sub-resource
        with ``{"enabled": bool}``.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable proxied nodes, False to disable.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``proxied_nodes`` link is
                used instead of the default template. Read only; never
                mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/proxied_nodes",
            link="proxied_nodes",
            parent=as_envelope(parent),
        )
        warn_uncharacterised_write(_LOGGER, f"set proxied nodes for network {network_id}")
        return await self.put(url, auth_token=auth_token, json={"enabled": enabled})
