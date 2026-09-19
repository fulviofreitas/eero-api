"""Networks API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

URL resolution goes exclusively through ``eero.api.links``: a bare network
ID, an API-returned path, or an absolute API-host URL are all accepted
wherever a ``network_id`` parameter is documented, and every method accepts
an optional keyword-only ``parent`` -- the caller's own cached network (or,
for the guest-network password methods, guest-network) envelope -- so the
link the API published on it is used instead of a locally-built template.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI, RequestEncoding
from .links import Envelope, resolve_link, resource_url, self_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)


def _guest_password_url(network_id: str, guest_parent: Optional[Envelope]) -> str:
    """Resolve the guest network's password link, falling back to the literal path.

    Args:
        network_id: A bare network ID, API-returned path, or absolute URL,
            used only for the template fallback.
        guest_parent: The guest network's own cached envelope, if the
            caller has one.

    Returns:
        The absolute URL of the guest network's password sub-resource.
    """
    if guest_parent is not None:
        resolved = resolve_link(guest_parent, "password")
        if resolved is not None:
            return resolved
    return resource_url(network_id, "networks/{id}/guestnetwork/password")


def _network_own_url(network_id: str, parent: Optional[Envelope]) -> str:
    """Resolve a network's own URL, preferring its parent envelope's ``url``.

    Args:
        network_id: A bare network ID, API-returned path, or absolute URL.
        parent: The network's own cached envelope, if the caller has one.

    Returns:
        The absolute URL of the network resource itself.
    """
    if parent is not None:
        own = self_url(parent)
        if own is not None:
            return own
    return resource_url(network_id, "networks/{id}")


class NetworksAPI(AuthenticatedAPI):
    """Networks API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the NetworksAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_networks(self) -> Dict[str, Any]:
        """Get list of networks - returns raw Eero API response.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
            The data field may contain "networks" list or other formats.

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting networks")
        return await self.get("networks", auth_token=auth_token)

    async def get_network(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get network information - returns raw Eero API response.

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

        _LOGGER.debug("Getting network %s", network_id)
        return await self.get(
            _network_own_url(network_id, as_envelope(parent)), auth_token=auth_token
        )

    async def get_premium_status(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get Eero Plus/Eero Secure subscription status - returns raw Eero API response.

        This returns the full network data which includes premium status information.
        Downstream clients should extract premium_status, eero_plus, or premium_dns fields.

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

        _LOGGER.debug("Getting premium status for network %s", network_id)
        return await self.get(
            _network_own_url(network_id, as_envelope(parent)), auth_token=auth_token
        )

    async def reboot_network(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Reboot the entire network - returns raw Eero API response.

        Issues a POST with the two-character body ``""`` -- the shape the
        API accepts for this parameterless operation -- to the network's
        ``reboot`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``reboot`` link is used
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
            network_id, "networks/{id}/reboot", link="reboot", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(_LOGGER, f"reboot network {network_id}")
        _LOGGER.debug("Rebooting network %s", network_id)
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )

    async def run_speed_test(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Run a speed test on the network - returns raw Eero API response.

        Issues a POST with the two-character body ``""`` to the network's
        ``speedtest`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``speedtest`` link is used
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
            network_id, "networks/{id}/speedtest", link="speedtest", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(_LOGGER, f"run speed test for network {network_id}")
        _LOGGER.debug("Running speed test for network %s", network_id)
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )

    async def get_speed_tests(
        self,
        network_id: str,
        *,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get past speed test results - returns raw Eero API response.

        GETs the network's ``speedtest`` link with the optional query
        parameters the API accepts on this endpoint.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            limit: Optional maximum number of results, sent as the ``limit``
                query parameter. Omitted from the request when ``None``.
            start_time: Optional window start, sent as the ``startTime``
                query parameter. Omitted from the request when ``None``.
            end_time: Optional window end, sent as the ``endTime`` query
                parameter. Omitted from the request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``speedtest`` link is used
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
            network_id, "networks/{id}/speedtest", link="speedtest", parent=as_envelope(parent)
        )
        params: Dict[str, str] = {}
        if limit is not None:
            params["limit"] = str(limit)
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        _LOGGER.debug("Getting speed test history for network %s", network_id)
        return await self.get(url, auth_token=auth_token, params=params)

    async def set_network_name(
        self, network_id: str, name: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Rename the network (SSID) - returns raw Eero API response.

        Issues a form-encoded PUT (``name=<value>``) to the network's
        ``settings`` link.

        .. warning::
            This write disconnects clients while it takes effect. A JSON
            write to the same path (``{"name": ...}``) was live-verified in
            the past (issue #43); this form-encoded shape is adopted as the
            API's declared form for the ``settings`` endpoint, but has not
            itself been re-verified live.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            name: The new network name.
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

        url = sub_resource_url(
            network_id, "networks/{id}/settings", link="settings", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(_LOGGER, f"set network name for network {network_id}")
        return await self.put(url, auth_token=auth_token, data={"name": name})

    async def set_network_password(
        self, network_id: str, password: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Set the network's Wi-Fi password - returns raw Eero API response.

        Issues a form-encoded PUT (``password=<value>``) to the network's
        ``password`` link. The password value is never logged; the field
        name ``password`` is redacted by the secure logger by convention.

        .. warning::
            This write disconnects clients while it takes effect, and has
            not been confirmed against a live network. Follow the
            read-compare-skip discipline and do not retry on failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            password: The new Wi-Fi password.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``password`` link is used
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
            network_id, "networks/{id}/password", link="password", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(_LOGGER, f"set network password for network {network_id}")
        return await self.put(url, auth_token=auth_token, data={"password": password})

    async def clear_network_password(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Clear the network's Wi-Fi password - returns raw Eero API response.

        Issues a DELETE to the network's ``password`` link.

        .. warning::
            This write disconnects clients while it takes effect, and has
            not been confirmed against a live network. Follow the
            read-compare-skip discipline and do not retry on failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``password`` link is used
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
            network_id, "networks/{id}/password", link="password", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(_LOGGER, f"clear network password for network {network_id}")
        return await self.delete(url, auth_token=auth_token)

    async def get_guest_network(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get guest network configuration - returns raw Eero API response.

        GETs the network's ``guestnetwork`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``guestnetwork`` link is
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
            "networks/{id}/guestnetwork",
            link="guestnetwork",
            parent=as_envelope(parent),
        )
        _LOGGER.debug("Getting guest network settings for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def set_guest_network(
        self,
        network_id: str,
        *,
        enabled: bool,
        name: Optional[str] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Enable or disable the guest network - returns raw Eero API response.

        Issues a form-encoded PUT to the network's ``guestnetwork`` link
        with the ``enabled`` field and, when supplied, the ``name`` field.
        Use `set_guest_password` to set the guest network's password.

        .. warning::
            This write disconnects guest clients while it takes effect, and
            has not been confirmed against a live network. Follow the
            read-compare-skip discipline and do not retry on failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: Whether to enable or disable the guest network.
            name: Optional new name for the guest network. Omitted from the
                request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``guestnetwork`` link is
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
            "networks/{id}/guestnetwork",
            link="guestnetwork",
            parent=as_envelope(parent),
        )
        payload: Dict[str, str] = {"enabled": "true" if enabled else "false"}
        if name is not None:
            payload["name"] = name

        warn_uncharacterised_write(_LOGGER, f"set guest network for network {network_id}")
        return await self.put(url, auth_token=auth_token, data=payload)

    async def set_guest_password(
        self,
        network_id: str,
        password: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set the guest network's password - returns raw Eero API response.

        Issues a form-encoded PUT (``password=<value>``) to the guest
        network's own ``password`` link. The password value is never
        logged.

        .. warning::
            This write disconnects guest clients while it takes effect, and
            has not been confirmed against a live network. Follow the
            read-compare-skip discipline and do not retry on failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            password: The new guest network password.
            parent: The guest network's own cached envelope (as returned by
                `get_guest_network`), if the caller has one; when supplied
                and it carries a published ``password`` link, that link is
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

        url = _guest_password_url(network_id, as_envelope(parent))
        warn_uncharacterised_write(_LOGGER, f"set guest password for network {network_id}")
        return await self.put(url, auth_token=auth_token, data={"password": password})

    async def clear_guest_password(
        self,
        network_id: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Clear the guest network's password - returns raw Eero API response.

        Issues a DELETE to the guest network's own ``password`` link.

        .. warning::
            This write disconnects guest clients while it takes effect, and
            has not been confirmed against a live network. Follow the
            read-compare-skip discipline and do not retry on failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The guest network's own cached envelope (as returned by
                `get_guest_network`), if the caller has one; when supplied
                and it carries a published ``password`` link, that link is
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

        url = _guest_password_url(network_id, as_envelope(parent))
        warn_uncharacterised_write(_LOGGER, f"clear guest password for network {network_id}")
        return await self.delete(url, auth_token=auth_token)
