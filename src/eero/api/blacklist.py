"""Device Blacklist API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

This module owns the block-list request building for the whole SDK.
``DevicesAPI.block_device``/``unblock_device`` delegate here rather than
duplicating the request shape, since both APIs ultimately address the same
``networks/{id}/blacklist`` resource.

Wire format: ``POST networks/{id}/blacklist`` takes a form-encoded ``mac``
field (the API's declared shape). ``DELETE networks/{id}/blacklist/{mac}``
takes no body. Both are reachable via the network's ``device_blacklist``
link when the caller supplies the cached network envelope.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import child_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Name of the network-level link to the block-list resource, as published
#: in a network envelope's ``resources`` object.
DEVICE_BLACKLIST_LINK = "device_blacklist"

#: Template used to build the block-list URL when no parent envelope is
#: supplied, or the parent has no ``device_blacklist`` link.
_BLACKLIST_TEMPLATE = "networks/{id}/blacklist"


class BlacklistAPI(AuthenticatedAPI):
    """Device Blacklist API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BlacklistAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    def _blacklist_url(self, network: str, parent: Optional[Mapping[str, Any]]) -> str:
        """Resolve the block-list collection URL for a network.

        Args:
            network: The network's bare ID, path, or absolute URL.
            parent: The cached network envelope, if the caller has one.

        Returns:
            The absolute block-list URL, preferring the network's own
            ``device_blacklist`` link when ``parent`` is supplied.
        """
        return sub_resource_url(
            network,
            _BLACKLIST_TEMPLATE,
            link=DEVICE_BLACKLIST_LINK,
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )

    async def get_blacklist(
        self, network: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get blacklisted devices - returns raw Eero API response.

        Args:
            network: The network's bare ID, path, or absolute URL.
            parent: The cached network envelope (full or ``data``), if the
                caller has one. Preferred over ``network`` to resolve the
                URL when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = self._blacklist_url(network, parent)
        _LOGGER.debug("Getting blacklist at %s", url)
        return await self.get(url, auth_token=auth_token)

    async def add_to_blacklist(
        self, network: str, mac: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Add a device to the blacklist - returns raw Eero API response.

        Sends a form-encoded ``mac`` field, the API's declared request shape
        for this operation.

        .. warning::
            This write has not been verified against a live network in its
            form-encoded shape: issue #109 live-verified a JSON body
            (``{"mac": ...}``) for the same operation, but the API's
            declared shape recovered from static analysis is form-encoded.
            Follow the read-compare-skip discipline: call `get_blacklist`
            after the write to confirm the device was added, and do not
            retry on failure.

        Args:
            network: The network's bare ID, path, or absolute URL.
            mac: MAC address of the device to blacklist (colon-separated,
                e.g. ``"aa:bb:cc:11:22:33"``).
            parent: The cached network envelope, if the caller has one.
                Preferred over ``network`` to resolve the URL when supplied.
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

        url = self._blacklist_url(network, parent)
        warn_uncharacterised_write(_LOGGER, "add_to_blacklist")
        _LOGGER.debug("Adding MAC to blacklist at %s", url)
        return await self.post(url, auth_token=auth_token, data={"mac": mac})

    async def remove_from_blacklist(
        self,
        network: str,
        mac_or_device_id: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Remove a device from the blacklist - returns raw Eero API response.

        Live-verified (issue #109): a blacklisted entry's ``device_id`` is
        the MAC address with colons stripped, so both the raw MAC and the
        colon-stripped form are accepted as the URL segment.

        Args:
            network: The network's bare ID, path, or absolute URL.
            mac_or_device_id: MAC address or device ID to remove from the
                blacklist.
            parent: The cached network envelope, if the caller has one.
                Preferred over ``network`` to resolve the URL when supplied.
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

        url = child_url(self._blacklist_url(network, parent), mac_or_device_id)
        _LOGGER.debug("Removing a device from the block list")
        return await self.delete(url, auth_token=auth_token)
