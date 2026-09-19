"""Devices API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

Device mutation writes are split across two paths:

* The nickname/pause write (``PUT networks/{id}/devices/{mac}`` on API
  version 2.3) is live-verified (issue #102): the identical write on the
  default 2.2 endpoint is a silent no-op.
* `update_device_via_link`, `set_device_type`, `get_device_labels`, and
  `set_device_labels` follow the API's declared request shape recovered
  from static analysis, but have not themselves been confirmed live. Each
  logs a warning via `eero.api._writes.warn_uncharacterised_write`.

Blocking/unblocking a device is delegated to `eero.api.blacklist.
BlacklistAPI`, which owns the ``networks/{id}/blacklist`` request building
for the whole SDK -- see that module for the wire format.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_DEFAULT, API_VERSION_DEVICE_WRITES
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .blacklist import BlacklistAPI
from .links import resource_url, self_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Template for a single device resource on the default API version.
_DEVICE_TEMPLATE = "networks/{network}/devices/{{id}}"


def _bool_param(value: Optional[bool]) -> Optional[str]:
    """Render an optional boolean as the ``"true"``/``"false"`` the API expects.

    Args:
        value: The candidate boolean, or ``None`` to omit the parameter.

    Returns:
        ``"true"``, ``"false"``, or ``None``.
    """
    if value is None:
        return None
    return "true" if value else "false"


class DevicesAPI(AuthenticatedAPI):
    """Devices API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DevicesAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    def _device_url(self, network: str, mac: str, *, version: str = API_VERSION_DEFAULT) -> str:
        """Resolve a single device's URL from a network ID and a device identifier.

        Args:
            network: ID of the network the device belongs to.
            mac: The device's bare MAC, path, or absolute URL.
            version: The API version for the template fallback.

        Returns:
            The absolute device URL.
        """
        return resource_url(mac, _DEVICE_TEMPLATE.format(network=network), version=version)

    async def _update_device(
        self, network_id: str, mac: str, payload: Dict[str, Any], auth_token: str
    ) -> Dict[str, Any]:
        """Send a device-mutation PUT against the 2.3 API endpoint.

        Device writes (nickname/blocked/paused/prioritized) are silently dropped
        on the default 2.2 endpoint — the backend returns 200 OK but the change
        never persists. Version 2.3 processes them correctly, so all device
        mutations are routed here via an absolute 2.3 URL while reads continue to
        use the 2.2 base URL. See issue #102.

        Args:
            network_id: ID of the network the device belongs to
            mac: The device's bare MAC, path, or absolute URL
            payload: JSON body describing the mutation
            auth_token: Authentication token

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        url = self._device_url(network_id, mac, version=API_VERSION_DEVICE_WRITES)
        return await self.put(url, auth_token=auth_token, json=payload)

    async def get_devices(
        self,
        network: str,
        *,
        thread: Optional[bool] = None,
        proxied_node: Optional[bool] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get list of connected devices - returns raw Eero API response.

        Args:
            network: ID of the network to get devices from.
            thread: When supplied, filters devices by Thread membership
                (sent as the query parameter ``thread=true``/``false``).
                Omitted from the request when ``None``.
            proxied_node: When supplied, filters devices by whether they are
                a proxied node (sent as ``proxied_node=true``/``false``).
                Omitted from the request when ``None``.
            parent: The cached network envelope (full or ``data``), if the
                caller has one. Preferred over ``network`` to resolve the
                ``devices`` link when supplied. Never mutated.

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
            "networks/{id}/devices",
            link="devices",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )

        params: Dict[str, str] = {}
        thread_param = _bool_param(thread)
        if thread_param is not None:
            params["thread"] = thread_param
        proxied_node_param = _bool_param(proxied_node)
        if proxied_node_param is not None:
            params["proxied_node"] = proxied_node_param

        _LOGGER.debug("Getting devices for network %s", network)
        return await self.get(url, auth_token=auth_token, params=params if params else None)

    async def get_device(
        self,
        network: str,
        mac: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get information about a specific device - returns raw Eero API response.

        Args:
            network: ID of the network the device belongs to.
            mac: The device's bare MAC, path, or absolute URL.
            parent: The device's own cached envelope, if the caller has one.
                When supplied, its own ``url`` is used and ``network``/``mac``
                are ignored for URL resolution. Never mutated.

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
            self._device_url(network, mac)
        )

        _LOGGER.debug("Getting device %s in network %s", mac, network)
        return await self.get(url, auth_token=auth_token)

    async def set_device_nickname(self, network_id: str, mac: str, nickname: str) -> Dict[str, Any]:
        """Set a nickname for a device - returns raw Eero API response.

        This is the live-verified write (issue #102): it targets the 2.3
        endpoint, where the mutation persists.

        Args:
            network_id: ID of the network the device belongs to
            mac: The device's bare MAC, path, or absolute URL
            nickname: New nickname for the device

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting nickname for device %s to '%s'", mac, nickname)

        return await self._update_device(network_id, mac, {"nickname": nickname}, auth_token)

    async def pause_device(self, network_id: str, mac: str, paused: bool) -> Dict[str, Any]:
        """Pause or unpause internet access for a device - returns raw Eero API response.

        This is the live-verified write (issue #102): it targets the 2.3
        endpoint, where the mutation persists. The device remains connected
        but cannot access the internet while paused.

        Args:
            network_id: ID of the network the device belongs to
            mac: The device's bare MAC, path, or absolute URL
            paused: True to pause internet access, False to resume

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error

        Note:
            This is different from blocking a device:
            - Paused: Device stays connected but has no internet access
            - Blocked: Device is completely removed from the network
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("%s device %s", "Pausing" if paused else "Unpausing", mac)

        return await self._update_device(network_id, mac, {"paused": paused}, auth_token)

    async def update_device_via_link(
        self,
        network: str,
        mac: str,
        *,
        nickname: Optional[str] = None,
        paused: Optional[bool] = None,
        profile: Optional[str] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update a device via its own URL - returns raw Eero API response.

        This is the API's declared request shape for updating a device: a PUT
        of a subset of ``mac``, ``nickname``, ``paused``, ``profile`` to the
        device's own URL. It is issued on the default API version.

        .. warning::
            Unlike `set_device_nickname`/`pause_device`, this path has not
            been live-verified -- only the 2.3-pinned write is confirmed to
            persist (issue #102). Prefer `set_device_nickname` and
            `pause_device` for those two fields. Follow the read-compare-skip
            discipline for any write through this method: read the device
            back afterwards and do not retry on failure.

        Args:
            network: ID of the network the device belongs to.
            mac: The device's bare MAC, path, or absolute URL. Ignored when
                ``parent`` resolves to a URL.
            nickname: New nickname, or ``None`` to omit.
            paused: New paused state, or ``None`` to omit.
            profile: New profile URL to assign the device to, or ``None`` to
                omit.
            parent: The device's own cached envelope, if the caller has one.
                Its own ``url`` is preferred over building one from
                ``network``/``mac``. Never mutated.

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
            self._device_url(network, mac)
        )

        payload: Dict[str, Any] = {}
        if nickname is not None:
            payload["nickname"] = nickname
        if paused is not None:
            payload["paused"] = paused
        if profile is not None:
            payload["profile"] = profile

        warn_uncharacterised_write(_LOGGER, "update_device_via_link")
        _LOGGER.debug("Updating device %s via its own link: %s", mac, sorted(payload))
        return await self.put(url, auth_token=auth_token, json=payload)

    async def set_device_type(self, network: str, mac: str, device_type: str) -> Dict[str, Any]:
        """Set a device's type - returns raw Eero API response.

        .. warning::
            This write has not been verified against a live network. Follow
            the read-compare-skip discipline: read the device back
            afterwards and do not retry on failure.

        Args:
            network: ID of the network the device belongs to.
            mac: The device's bare MAC, path, or absolute URL.
            device_type: The device type to set, forwarded unchanged.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = self._device_url(network, mac)
        warn_uncharacterised_write(_LOGGER, "set_device_type")
        _LOGGER.debug("Setting device type for %s to '%s'", mac, device_type)
        return await self.put(url, auth_token=auth_token, json={"device_type": device_type})

    async def get_device_labels(self, network: str, mac: str) -> Dict[str, Any]:
        """Get the hardware/manufacturer labels for a device - returns raw Eero API response.

        Args:
            network: ID of the network the device belongs to.
            mac: The device's bare MAC, path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{self._device_url(network, mac)}/labels"
        _LOGGER.debug("Getting labels for device %s", mac)
        return await self.get(url, auth_token=auth_token)

    async def set_device_labels(
        self,
        network: str,
        mac: str,
        *,
        make_label: Optional[str] = None,
        model_label: Optional[str] = None,
        version_label: Optional[str] = None,
        type_label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set the hardware/manufacturer labels for a device - returns raw Eero API response.

        The labels are sent as query parameters on the PUT, not a JSON or
        form body.

        .. warning::
            This write has not been verified against a live network. Follow
            the read-compare-skip discipline: call `get_device_labels`
            afterwards and do not retry on failure.

        Args:
            network: ID of the network the device belongs to.
            mac: The device's bare MAC, path, or absolute URL.
            make_label: New manufacturer label, or ``None`` to omit.
            model_label: New model label, or ``None`` to omit.
            version_label: New hardware version label, or ``None`` to omit.
            type_label: New device type label, or ``None`` to omit.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{self._device_url(network, mac)}/labels"
        params: Dict[str, str] = {}
        if make_label is not None:
            params["make_label"] = make_label
        if model_label is not None:
            params["model_label"] = model_label
        if version_label is not None:
            params["version_label"] = version_label
        if type_label is not None:
            params["type_label"] = type_label

        warn_uncharacterised_write(_LOGGER, "set_device_labels")
        _LOGGER.debug("Setting labels for device %s: %s", mac, sorted(params))
        return await self.put(url, auth_token=auth_token, params=params)

    async def block_device(self, network: str, mac: str) -> Dict[str, Any]:
        """Add a device to the network's block list - returns raw Eero API response.

        Delegates to `eero.api.blacklist.BlacklistAPI.add_to_blacklist`,
        which owns the block-list request building for the whole SDK.

        Args:
            network: ID of the network the device belongs to.
            mac: MAC address of the device to block.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        return await BlacklistAPI(self._auth_api).add_to_blacklist(network, mac)

    async def unblock_device(self, network: str, mac: str) -> Dict[str, Any]:
        """Remove a device from the network's block list - returns raw Eero API response.

        Delegates to `eero.api.blacklist.BlacklistAPI.remove_from_blacklist`,
        which owns the block-list request building for the whole SDK.

        Args:
            network: ID of the network the device belongs to.
            mac: MAC address (or blacklist device ID) to unblock.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        return await BlacklistAPI(self._auth_api).remove_from_blacklist(network, mac)
