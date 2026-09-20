"""DHCP / WAN connection settings API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.

Every write in this module goes to the network's ``settings`` sub-resource
(the same endpoint used by ``eero.api.networks`` and ``eero.api.dns``), with
the ``dhcp``, ``connection``, and ``nat_port_randomization`` fields
declared for that endpoint. None of these writes have been confirmed
against a live network, and DHCP/connection-mode changes are settings-class
writes: the DNS write path on this same endpoint is confirmed to reboot the
entire mesh (every eero restarts, all clients drop), and this SDK treats
every other settings-class write as capable of the same behaviour until
proven otherwise. Follow the read-compare-skip discipline documented on
each write below, and never retry a failed write in a loop.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Valid values for ``dhcp.mode``.
DHCP_MODE_AUTOMATIC = "automatic"
DHCP_MODE_MANUAL = "manual"
_DHCP_MODES = frozenset({DHCP_MODE_AUTOMATIC, DHCP_MODE_MANUAL})

#: Fields the API accepts on a manual DHCP lease range (``dhcp.custom``).
_CUSTOM_LEASE_FIELDS = frozenset({"start_ip", "end_ip", "subnet_ip", "subnet_mask"})

#: Fields the API accepts on the per-subnet DHCP configuration
#: (``dhcp.custom_v2``).
_CUSTOM_V2_FIELDS = frozenset({"main", "guest", "subnetA", "subnetB", "supernet"})


def _filter_given_keys(mapping: Mapping[str, Any], allowed: frozenset) -> Dict[str, Any]:
    """Copy only the caller-supplied keys that the API declares for a field.

    Args:
        mapping: The caller-supplied mapping. Read only; never mutated.
        allowed: The set of field names the API accepts here.

    Returns:
        A new dict containing only the keys in ``mapping`` that are also in
        ``allowed``.

    Raises:
        EeroValidationException: If ``mapping`` carries a key outside
            ``allowed``.
    """
    unknown = set(mapping) - allowed
    if unknown:
        raise EeroValidationException(
            "field", f"unrecognised field(s): {sorted(unknown)}; expected one of {sorted(allowed)}"
        )
    return {key: mapping[key] for key in mapping}


class DhcpAPI(AuthenticatedAPI):
    """DHCP / WAN connection settings API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}

    Reads for these settings stay in the network envelope returned by
    `eero.api.networks.NetworksAPI.get_network` -- see ``data.dhcp``,
    ``data.lease``, ``data.connection``, ``data.ip_settings``, and
    ``data.wan_type``.
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DhcpAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def set_dhcp(
        self,
        network_id: str,
        *,
        mode: Optional[str] = None,
        custom: Optional[Mapping[str, Any]] = None,
        custom_v2: Optional[Mapping[str, Any]] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set the network's DHCP configuration - returns raw Eero API response.

        Issues a JSON PUT to the network's ``settings`` link with exactly
        the ``dhcp`` sub-fields supplied among ``mode``, ``custom``, and
        ``custom_v2``.

        .. warning::
            This is a settings-class write. Its side effects have not been
            confirmed against a live network, and the DNS write on this same
            endpoint is confirmed to reboot every eero on the mesh. Treat
            this write as capable of doing the same: read the current
            configuration first (`eero.api.networks.NetworksAPI.get_network`),
            skip the write when it already matches, and never retry a failed
            write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            mode: ``"automatic"`` or ``"manual"``. Omitted from the request
                when ``None``.
            custom: Manual lease-range fields, sent only for the keys
                supplied: ``start_ip``, ``end_ip``, ``subnet_ip``,
                ``subnet_mask``. Omitted from the request when ``None``.
            custom_v2: Per-subnet lease-range fields, sent only for the keys
                supplied: ``main``, ``guest``, ``subnetA``, ``subnetB``,
                ``supernet``. Omitted from the request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``settings`` link is used
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``mode`` is not ``"automatic"`` or
                ``"manual"``, no field is supplied, or ``custom``/
                ``custom_v2`` carry a field the API does not declare here
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        dhcp: Dict[str, Any] = {}
        if mode is not None:
            if mode not in _DHCP_MODES:
                raise EeroValidationException(
                    "mode", f"must be one of {sorted(_DHCP_MODES)}, got {mode!r}"
                )
            dhcp["mode"] = mode
        if custom is not None:
            dhcp["custom"] = _filter_given_keys(custom, _CUSTOM_LEASE_FIELDS)
        if custom_v2 is not None:
            dhcp["custom_v2"] = _filter_given_keys(custom_v2, _CUSTOM_V2_FIELDS)

        if not dhcp:
            raise EeroValidationException(
                "dhcp", "at least one of mode, custom, custom_v2 must be supplied"
            )

        url = sub_resource_url(
            network_id, "networks/{id}/settings", link="settings", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(
            _LOGGER,
            "set DHCP configuration for network "
            "-- may reboot every eero, like the confirmed DNS write path",
        )
        return await self.put(url, auth_token=auth_token, json={"dhcp": dhcp})

    async def set_connection_mode(
        self,
        network_id: str,
        mode: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set the network's WAN connection mode - returns raw Eero API response.

        Issues a JSON PUT to the network's ``settings`` link with
        ``{"connection": {"mode": ...}}``.

        .. warning::
            This is a settings-class write. Its side effects have not been
            confirmed against a live network, and the DNS write on this same
            endpoint is confirmed to reboot every eero on the mesh. Treat
            this write as capable of doing the same: read the current
            configuration first, skip the write when it already matches,
            and never retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            mode: ``"BRIDGE"`` or ``"NAT"`` -- the values declared for this
                field.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``settings`` link is used
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``mode`` is not ``"BRIDGE"`` or
                ``"NAT"``
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        valid_modes = frozenset({"BRIDGE", "NAT"})
        if not isinstance(mode, str) or mode not in valid_modes:
            raise EeroValidationException(
                "mode", f"must be one of {sorted(valid_modes)}, got {mode!r}"
            )

        url = sub_resource_url(
            network_id, "networks/{id}/settings", link="settings", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(
            _LOGGER,
            "set connection mode for network "
            "-- may reboot every eero, like the confirmed DNS write path",
        )
        return await self.put(url, auth_token=auth_token, json={"connection": {"mode": mode}})

    async def set_nat_port_randomization(
        self,
        network_id: str,
        enabled: bool,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Enable or disable NAT port randomization - returns raw Eero API response.

        Issues a JSON PUT to the network's ``settings`` link with
        ``{"nat_port_randomization": bool}``.

        .. warning::
            This is a settings-class write. Its side effects have not been
            confirmed against a live network, and the DNS write on this same
            endpoint is confirmed to reboot every eero on the mesh. Treat
            this write as capable of doing the same: read the current
            configuration first, skip the write when it already matches,
            and never retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable NAT port randomization, False to disable.
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
        warn_uncharacterised_write(
            _LOGGER,
            "set NAT port randomization for network "
            "-- may reboot every eero, like the confirmed DNS write path",
        )
        return await self.put(url, auth_token=auth_token, json={"nat_port_randomization": enabled})

    async def set_pppoe(
        self,
        eero_serial_or_id: str,
        *,
        username: str,
        password: str,
    ) -> Dict[str, Any]:
        """Encrypt PPPoE credentials for an Eero device - returns raw Eero API response.

        Issues a JSON POST to the eero's ``pppoe`` sub-resource with
        ``{"pppoe": {"username": ..., "password": ...}}``. The response
        carries the encrypted credential blob the API expects to receive
        back on a subsequent DHCP/connection write; this method does not
        interpret or forward that value anywhere. The password value is
        never logged; the field name ``password`` is redacted by the secure
        logger by convention.

        .. warning::
            This write's side effects have not been confirmed against a
            live network.

        Args:
            eero_serial_or_id: A bare eero serial/ID, API-returned path, or
                absolute URL.
            username: The PPPoE username.
            password: The PPPoE password. Never logged.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(eero_serial_or_id, "eeros/{id}/pppoe")
        warn_uncharacterised_write(_LOGGER, "encrypt PPPoE credentials for eero")
        return await self.post(
            url,
            auth_token=auth_token,
            json={"pppoe": {"username": username, "password": password}},
        )
