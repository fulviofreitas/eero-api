"""DNS Settings API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

Wire format (live-verified 2026-09-12 against API 2.2):

    PUT networks/{id}/settings

    IPv4:  {"dns":  {"mode": "custom"|"automatic",
                     "custom": {"ips": [...]}}}
    IPv6:  {"ipv6": {"name_servers": {"mode": "custom"|"automatic",
                                      "custom": [...]}}}

The two address families are INDEPENDENT objects with their own mode selectors,
and their shapes are ASYMMETRIC: the IPv4 list nests under ``custom.ips`` while
the IPv6 list sits directly under ``custom``. Do not refactor them into a shared
helper that assumes symmetry.

Historical note: releases v4.1.3 through v6.2.0 sent a flat ``custom_dns`` field
(and ``dns_caching``). Neither field exists in the API. The backend accepts
unrecognised keys with HTTP 200 and silently discards them, so those writes were
no-ops that reported success. See issue #123.
"""

import ipaddress
import logging
from typing import Any, Dict, List, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)

#: Maximum custom DNS servers accepted per address family.
#:
#: This mirrors the eero app, which exposes exactly two slots per family
#: (primary + secondary). It is a deliberate client-side safety limit, NOT an
#: API-enforced one: the API was observed accepting at least five servers in a
#: single family. Exceeding two during probing on 2026-09-12 coincided with a
#: network outage whose mechanism was never established, so the SDK stays within
#: what the vendor UI itself allows. Change this constant if better evidence
#: emerges.
MAX_DNS_SERVERS_PER_FAMILY = 2

#: DNS mode values used by both ``dns.mode`` and ``ipv6.name_servers.mode``.
DNS_MODE_CUSTOM = "custom"
DNS_MODE_AUTOMATIC = "automatic"


def _validate_servers(servers: List[str], family: int, field: str) -> List[str]:
    """Validate and normalise a list of DNS server literals for one family.

    Args:
        servers: Candidate DNS server addresses.
        family: 4 or 6.
        field: Field name used in any raised validation error.

    Returns:
        The normalised (compressed) addresses, in the order supplied.

    Raises:
        EeroValidationException: If the list is not a list of valid, correctly
            versioned IP literals, or exceeds MAX_DNS_SERVERS_PER_FAMILY.
    """
    if not isinstance(servers, list):
        raise EeroValidationException(field, "must be a list of IP address strings")

    if len(servers) > MAX_DNS_SERVERS_PER_FAMILY:
        raise EeroValidationException(
            field,
            f"at most {MAX_DNS_SERVERS_PER_FAMILY} IPv{family} servers are supported "
            f"(got {len(servers)}); this matches the eero app's primary/secondary slots",
        )

    normalised: List[str] = []
    for entry in servers:
        if not isinstance(entry, str):
            raise EeroValidationException(
                field, f"expected an IP address string, got {type(entry).__name__}"
            )

        candidate = entry.strip()
        if not candidate:
            raise EeroValidationException(field, "IP address must not be empty")

        # `ipaddress` accepts scoped literals (fe80::1%eth0), but a zone
        # identifier only has meaning relative to the caller's own interfaces
        # and is nonsense to a cloud API.
        if "%" in candidate:
            raise EeroValidationException(
                field, f"{entry!r} has a zone identifier, which is not valid for a DNS server"
            )

        try:
            address = ipaddress.ip_address(candidate)
        except ValueError as exc:
            raise EeroValidationException(field, f"{entry!r} is not a valid IP address") from exc

        if address.version != family:
            raise EeroValidationException(
                field, f"{entry!r} is an IPv{address.version} address, expected IPv{family}"
            )

        normalised.append(str(address))

    return normalised


def _split_by_family(servers: List[str], field: str) -> Dict[str, List[str]]:
    """Partition a mixed list of IP literals into IPv4 and IPv6 groups.

    Validation of each group (including the per-family cap) is left to
    `_validate_servers`, so that error messages name the offending family.
    """
    if not isinstance(servers, list):
        raise EeroValidationException(field, "must be a list of IP address strings")

    ipv4: List[str] = []
    ipv6: List[str] = []
    for entry in servers:
        if not isinstance(entry, str):
            raise EeroValidationException(
                field, f"expected an IP address string, got {type(entry).__name__}"
            )
        candidate = entry.strip()
        if "%" in candidate:
            raise EeroValidationException(
                field, f"{entry!r} has a zone identifier, which is not valid for a DNS server"
            )
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError as exc:
            raise EeroValidationException(field, f"{entry!r} is not a valid IP address") from exc
        (ipv4 if address.version == 4 else ipv6).append(entry)

    return {"ipv4": ipv4, "ipv6": ipv6}


class DnsAPI(AuthenticatedAPI):
    """DNS Settings API for Eero.

    Manages custom DNS servers (IPv4 and IPv6 independently), DNS caching, and
    the per-family automatic/custom mode selector.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DnsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def _put_settings(self, network_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """PUT a settings payload for a network.

        Every DNS write goes through here, so the endpoint and the auth guard
        live in one place.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        return await self.put(
            f"networks/{network_id}/settings",
            auth_token=auth_token,
            json=payload,
        )

    async def get_dns_settings(self, network_id: str) -> Dict[str, Any]:
        """Get DNS configuration for a network - returns raw Eero API response.

        DNS settings are part of the network resource. The relevant paths are:

        - ``data.dns.mode`` — "custom" or "automatic" (the IPv4 selector)
        - ``data.dns.custom.ips`` — configured IPv4 servers, retained even when
          the mode is "automatic"
        - ``data.dns.parent.ips`` — the ISP-provided upstream resolvers
        - ``data.dns.caching`` — DNS caching on/off
        - ``data.ipv6.name_servers.mode`` — the IPv6 selector
        - ``data.ipv6.name_servers.custom`` — configured IPv6 servers, stored in
          fully expanded form (``2606:4700:4700:0:0:0:0:1111``)

        Args:
            network_id: ID of the network

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting DNS settings for network %s", network_id)
        return await self.get(f"networks/{network_id}", auth_token=auth_token)

    async def set_dns_caching(self, network_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable DNS caching - returns raw Eero API response.

        Args:
            network_id: ID of the network
            enabled: True to enable DNS caching, False to disable

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        _LOGGER.debug(
            "%s DNS caching for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )
        return await self._put_settings(network_id, {"dns": {"caching": enabled}})

    async def set_custom_dns(
        self,
        network_id: str,
        dns_servers: List[str],
    ) -> Dict[str, Any]:
        """Set custom DNS servers from a mixed list - returns raw Eero API response.

        The list may contain IPv4 and/or IPv6 literals. They are partitioned by
        family, and each family that is represented is written to its own field
        and switched to custom mode. **A family not represented in the list is
        left untouched** — an IPv4-only list does not alter IPv6, and vice versa.
        Use `clear_custom_dns` to switch a family back to automatic.

        To address a single family explicitly, prefer `set_custom_dns_ipv4` or
        `set_custom_dns_ipv6`.

        Args:
            network_id: ID of the network
            dns_servers: DNS server IPs, at most
                MAX_DNS_SERVERS_PER_FAMILY per address family.
                e.g. ["1.1.1.1", "1.0.0.1", "2606:4700:4700::1111"]

        Returns:
            Raw API response from the final write: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If an entry is not a valid IP literal, or a
                family exceeds MAX_DNS_SERVERS_PER_FAMILY
            EeroAPIException: If the API returns an error
        """
        groups = _split_by_family(dns_servers, "dns_servers")
        ipv4 = _validate_servers(groups["ipv4"], 4, "dns_servers")
        ipv6 = _validate_servers(groups["ipv6"], 6, "dns_servers")

        if not ipv4 and not ipv6:
            raise EeroValidationException(
                "dns_servers",
                "no servers supplied; use clear_custom_dns() to switch to automatic DNS",
            )

        _LOGGER.debug(
            "Setting custom DNS for network %s (IPv4=%s, IPv6=%s)", network_id, ipv4, ipv6
        )

        payload: Dict[str, Any] = {}
        if ipv4:
            payload["dns"] = {"mode": DNS_MODE_CUSTOM, "custom": {"ips": ipv4}}
        if ipv6:
            payload["ipv6"] = {"name_servers": {"mode": DNS_MODE_CUSTOM, "custom": ipv6}}
        return await self._put_settings(network_id, payload)

    async def set_custom_dns_ipv4(self, network_id: str, dns_servers: List[str]) -> Dict[str, Any]:
        """Set the IPv4 custom DNS servers, leaving IPv6 untouched.

        Args:
            network_id: ID of the network
            dns_servers: IPv4 server IPs, at most MAX_DNS_SERVERS_PER_FAMILY

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If an entry is not a valid IPv4 literal, or
                the list exceeds MAX_DNS_SERVERS_PER_FAMILY
            EeroAPIException: If the API returns an error
        """
        servers = _validate_servers(dns_servers, 4, "dns_servers")
        if not servers:
            raise EeroValidationException(
                "dns_servers",
                "no servers supplied; use clear_custom_dns(family='ipv4') to switch to automatic",
            )
        _LOGGER.debug("Setting IPv4 custom DNS for network %s: %s", network_id, servers)
        return await self._put_settings(
            network_id, {"dns": {"mode": DNS_MODE_CUSTOM, "custom": {"ips": servers}}}
        )

    async def set_custom_dns_ipv6(self, network_id: str, dns_servers: List[str]) -> Dict[str, Any]:
        """Set the IPv6 custom DNS servers, leaving IPv4 untouched.

        Note: the API stores IPv6 addresses in fully expanded form, so a value
        written as ``2606:4700:4700::1111`` reads back as
        ``2606:4700:4700:0:0:0:0:1111``. Compare via `ipaddress.IPv6Address`,
        never by string equality.

        Args:
            network_id: ID of the network
            dns_servers: IPv6 server IPs, at most MAX_DNS_SERVERS_PER_FAMILY

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If an entry is not a valid IPv6 literal, or
                the list exceeds MAX_DNS_SERVERS_PER_FAMILY
            EeroAPIException: If the API returns an error
        """
        servers = _validate_servers(dns_servers, 6, "dns_servers")
        if not servers:
            raise EeroValidationException(
                "dns_servers",
                "no servers supplied; use clear_custom_dns(family='ipv6') to switch to automatic",
            )
        _LOGGER.debug("Setting IPv6 custom DNS for network %s: %s", network_id, servers)
        return await self._put_settings(
            network_id,
            {"ipv6": {"name_servers": {"mode": DNS_MODE_CUSTOM, "custom": servers}}},
        )

    async def clear_custom_dns(
        self, network_id: str, family: Optional[str] = None
    ) -> Dict[str, Any]:
        """Switch DNS back to automatic - returns raw Eero API response.

        This is non-destructive: the API retains the configured servers rather
        than discarding them, mirroring the eero app's "ISP DNS (Default)"
        option. Server-side retention is confirmed — a network switched to
        automatic in the app still reports its servers in ``dns.custom.ips``.

        Two caveats worth knowing:

        - **Writing ``mode`` is not yet live-verified.** The nested server
          writes were confirmed against API 2.2 on 2026-09-12, but no probe
          isolated a mode change, so this method rests on inference from the
          read shape. Verify with a read-back rather than assuming it applied.
        - **Re-enabling retained servers requires supplying them again.** The
          API appears to accept a mode-only write, but the SDK does not expose
          one, precisely because it is unverified. Pass the addresses to
          `set_custom_dns` to switch back.

        Args:
            network_id: ID of the network
            family: "ipv4" or "ipv6" to clear a single family, or None (the
                default) to switch both to automatic.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If family is not "ipv4", "ipv6", or None
            EeroAPIException: If the API returns an error
        """
        if family not in (None, "ipv4", "ipv6"):
            raise EeroValidationException("family", "must be 'ipv4', 'ipv6', or None")

        payload: Dict[str, Any] = {}
        if family in (None, "ipv4"):
            payload["dns"] = {"mode": DNS_MODE_AUTOMATIC}
        if family in (None, "ipv6"):
            payload["ipv6"] = {"name_servers": {"mode": DNS_MODE_AUTOMATIC}}

        _LOGGER.debug(
            "Clearing custom DNS for network %s (family=%s)", network_id, family or "both"
        )
        return await self._put_settings(network_id, payload)

    async def set_dns_mode(
        self,
        network_id: str,
        mode: str,
        custom_servers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Set DNS mode for the network - returns raw Eero API response.

        Named provider presets are deliberately not offered here. The API serves
        its own provider catalogue at ``data.dns.default_test_servers`` (read it
        via `get_dns_settings`), with IPv4 and IPv6 addresses per provider. A
        hardcoded copy in the SDK would duplicate server-owned data and go stale.
        Build a preset picker from that catalogue and pass the addresses as
        ``custom_servers``.

        Args:
            network_id: ID of the network
            mode: "auto"/"automatic" or "custom"
            custom_servers: DNS servers, required when mode is "custom". May mix
                IPv4 and IPv6 literals.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If the mode is unrecognised, or mode is
                "custom" without servers, or a server entry is invalid
            EeroAPIException: If the API returns an error
        """
        if not isinstance(mode, str):
            raise EeroValidationException("mode", f"expected a string, got {type(mode).__name__}")

        normalised_mode = mode.strip().lower()

        if normalised_mode in ("auto", DNS_MODE_AUTOMATIC):
            return await self.clear_custom_dns(network_id)

        if normalised_mode == DNS_MODE_CUSTOM:
            if not custom_servers:
                raise EeroValidationException("custom_servers", "required when mode is 'custom'")
            return await self.set_custom_dns(network_id, custom_servers)

        raise EeroValidationException(
            "mode",
            f"{mode!r} is not a valid DNS mode; expected 'auto' or 'custom'. "
            "Provider presets are available from the API at "
            "data.dns.default_test_servers — pass those addresses as custom_servers",
        )

    async def set_ipv6_dns(self, network_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable IPv6 upstream - returns raw Eero API response.

        .. warning::
            Despite its name this method does **not** control IPv6 DNS servers.
            It writes ``ipv6_upstream``, the network-level IPv6 connectivity
            toggle, and IPv6 custom DNS works independently of it (verified:
            ``ipv6.name_servers.mode`` can be "custom" while ``ipv6_upstream``
            is False). ``SecurityAPI.set_ipv6`` writes the same field *and*
            ``ipv6_downstream``, so the two can leave the network in a split
            state. Tracked separately; use `set_custom_dns_ipv6` for IPv6 DNS
            servers.

        Args:
            network_id: ID of the network
            enabled: True to enable IPv6 upstream, False to disable

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        _LOGGER.debug(
            "%s IPv6 upstream for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )
        return await self._put_settings(network_id, {"ipv6_upstream": enabled})
