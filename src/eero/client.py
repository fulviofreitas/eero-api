"""High-level client for interacting with Eero networks.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
Response format: {"meta": {...}, "data": {...}}
"""

import copy
import logging
import time
from typing import Any, Dict, List, Mapping, Optional

from aiohttp import ClientSession

from .api import EeroAPI
from .const import DEFAULT_ACCEPT_LANGUAGE
from .exceptions import EeroException

_LOGGER = logging.getLogger(__name__)


class EeroClient:
    """High-level client for interacting with Eero networks.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}

    Downstream clients must handle:
    - Data extraction from response envelopes
    - Field renaming (e.g., wan_ip → public_ip)
    - Nested data extraction (e.g., geo_ip.isp → isp_name)
    - Status normalization
    - Model validation/conversion

    Cache isolation contract: the in-memory cache and the object returned to
    a caller are independent copies of each other. Every write into the
    cache stores a ``copy.deepcopy`` of the response, and every read from
    the cache returns a fresh ``copy.deepcopy`` of the stored entry
    (including when a cached envelope is reused internally as a domain
    call's ``parent=`` argument). A caller that mutates a dict/list it
    received back from a method on this class can therefore never poison
    the cache, and can never affect a ``parent=`` envelope built from that
    cache on a later call. The one exception -- by design, not oversight --
    is the value returned directly from a fresh (non-cached) domain-API
    call: that object is handed to the caller exactly as the domain API
    produced it, and only the copy stored in the cache is independent of it.
    """

    def __init__(
        self,
        session: Optional[ClientSession] = None,
        cookie_file: Optional[str] = None,
        use_keyring: bool = True,
        cache_timeout: int = 60,
        *,
        send_legacy_cookie: bool = True,
        accept_language: str = DEFAULT_ACCEPT_LANGUAGE,
        get_retries: int = 0,
    ) -> None:
        """Initialize the EeroClient.

        Args:
            session: Optional aiohttp ClientSession to use for requests
            cookie_file: Optional path to a file for storing authentication cookies
            use_keyring: Whether to use keyring for secure token storage
            cache_timeout: Cache timeout in seconds
            send_legacy_cookie: When True (default), also send the session
                token as the legacy ``s=<token>`` cookie, per request, on
                requests to the configured API host. Exists for compatibility
                with the eero mobile app for one major version and defaults
                on.
            accept_language: Value sent as the ``X-Accept-Language`` header
                on every request. Validated as printable ASCII with no
                CR/LF.
            get_retries: Number of additional attempts for GET requests that
                fail with a transport error or a 5xx response. 0 (default)
                disables retrying. Never applies to writes
                (POST/PUT/DELETE/PATCH).
        """
        self._api = EeroAPI(
            session=session,
            cookie_file=cookie_file,
            use_keyring=use_keyring,
            send_legacy_cookie=send_legacy_cookie,
            accept_language=accept_language,
            get_retries=get_retries,
        )
        self._cache_timeout = cache_timeout
        self._preferred_network_id: Optional[str] = None
        self._cache: Dict[str, Dict] = {
            "account": {"data": None, "timestamp": 0},
            "networks": {"data": None, "timestamp": 0},
            "network": {},
            "eeros": {},
            "devices": {},
            "profiles": {},
        }

    async def __aenter__(self) -> "EeroClient":
        """Enter async context manager."""
        await self._api.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        await self._api.__aexit__(exc_type, exc_val, exc_tb)

    @property
    def is_authenticated(self) -> bool:
        """Check if the client is authenticated."""
        return self._api.is_authenticated

    def _is_cache_valid(self, cache_key: str, subkey: Optional[str] = None) -> bool:
        """Check if a cache entry is valid."""
        if cache_key not in self._cache:
            return False

        if subkey is None:
            cache_entry = self._cache[cache_key]
        else:
            if subkey not in self._cache[cache_key]:
                return False
            cache_entry = self._cache[cache_key][subkey]

        if not cache_entry or "timestamp" not in cache_entry:
            return False

        current_time = time.monotonic()
        return (current_time - cache_entry["timestamp"]) < self._cache_timeout

    def _update_cache(self, cache_key: str, subkey: Optional[str], data: Any) -> None:
        """Store a deep copy of ``data`` in the cache.

        A deep copy is stored (rather than the object itself) so that any
        later mutation of the object the caller received back from a public
        method can never reach the cached entry. See the cache isolation
        contract in the class docstring.
        """
        current_time = time.monotonic()
        stored = copy.deepcopy(data)

        if subkey is None:
            self._cache[cache_key] = {"data": stored, "timestamp": current_time}
        else:
            if cache_key not in self._cache:
                self._cache[cache_key] = {}
            self._cache[cache_key][subkey] = {"data": stored, "timestamp": current_time}

    def _get_from_cache(self, cache_key: str, subkey: Optional[str] = None) -> Any:
        """Return a deep copy of a cached entry.

        A deep copy is returned (rather than the cached object itself) so
        that a caller mutating the result -- whether it reaches them
        directly or via a ``parent=`` kwarg built from it -- can never
        poison the cache. See the cache isolation contract in the class
        docstring.
        """
        if cache_key not in self._cache:
            return None

        if subkey is None:
            cache_entry = self._cache[cache_key]
        else:
            if subkey not in self._cache[cache_key]:
                return None
            cache_entry = self._cache[cache_key][subkey]

        return copy.deepcopy(cache_entry.get("data"))

    def clear_cache(self) -> None:
        """Clear all cached data."""
        for cache_key in self._cache:
            if isinstance(self._cache[cache_key], dict) and "data" in self._cache[cache_key]:
                self._cache[cache_key]["data"] = None
            else:
                self._cache[cache_key] = {}

    async def _ensure_network_id(
        self, network_id: Optional[str], auto_discover: bool = True
    ) -> str:
        """Ensure a valid network ID is available.

        Args:
            network_id: Optional network ID provided by caller
            auto_discover: If True, attempt to discover networks when no ID available

        Returns:
            Valid network ID

        Raises:
            EeroException: If no network ID can be determined
        """
        # Use provided ID or fall back to preferred
        resolved_id = network_id or self._preferred_network_id
        if resolved_id:
            return resolved_id

        # Try to auto-discover if enabled
        if auto_discover:
            networks_response = await self.get_networks()
            # Extract networks from raw response
            data = networks_response.get("data", {})
            networks = []
            if isinstance(data, list):
                networks = data
            elif isinstance(data, dict):
                networks = data.get("networks") or data.get("data") or []

            if networks and len(networks) > 0:
                # Extract ID from URL or id field
                first_network = networks[0]
                net_id = first_network.get("id")
                if not net_id and first_network.get("url"):
                    net_id = first_network["url"].rstrip("/").split("/")[-1]
                if net_id:
                    return net_id

        raise EeroException("No network ID provided and no preferred network set")

    # ==================== Link-aware parent resolution ====================
    #
    # These helpers are the single place the facade looks up a cached
    # envelope to pass as ``parent=`` to a domain method, so that every
    # wrapper below reuses one lookup instead of repeating it. They only
    # ever READ the cache; the returned envelope is never mutated, and the
    # v2.0 raw-response contract is preserved because the envelope itself is
    # forwarded unchanged as a domain method's ``parent`` argument, not
    # merged into anything this facade returns.

    def _network_parent(self, network_id: str) -> Optional[Dict[str, Any]]:
        """Return the cached network envelope for use as ``parent``, if fresh.

        Args:
            network_id: The resolved network ID to look up.

        Returns:
            The cached raw envelope (``{"meta": ..., "data": ...}``) for
            ``network_id``, or ``None`` when nothing fresh is cached for it.
        """
        if not self._is_cache_valid("network", network_id):
            return None
        return self._get_from_cache("network", network_id)

    def _network_parent_kwargs(self, network_id: str) -> Dict[str, Any]:
        """Build a ``parent=`` kwarg dict from the cached network envelope.

        Args:
            network_id: The resolved network ID to look up.

        Returns:
            ``{"parent": <cached envelope>}`` when a fresh cached network
            envelope is available, otherwise ``{}`` -- so unpacking this
            into a domain call omits the ``parent`` keyword entirely rather
            than passing ``parent=None``.
        """
        parent = self._network_parent(network_id)
        return {"parent": parent} if parent is not None else {}

    @staticmethod
    def _find_by_id_or_url(envelopes: Any, resource_id: str) -> Optional[Dict[str, Any]]:
        """Find an envelope in a list matching a bare ID by ``id`` or trailing ``url`` segment.

        Args:
            envelopes: The candidate list of raw envelopes (as returned in a
                collection response's ``data`` field), or anything else --
                non-lists yield no match.
            resource_id: The bare ID being searched for.

        Returns:
            The matching envelope (read only; never mutated), or ``None``.
        """
        if not isinstance(envelopes, list):
            return None
        for entry in envelopes:
            if not isinstance(entry, dict):
                continue
            if entry.get("id") == resource_id:
                return entry
            url = entry.get("url")
            if isinstance(url, str) and url.rstrip("/").split("/")[-1] == resource_id:
                return entry
        return None

    def _eero_parent_kwargs(self, network_id: str, eero_id: str) -> Dict[str, Any]:
        """Build a ``parent=`` kwarg dict from the cached eeros list.

        Looks up the cached ``get_eeros`` response for ``network_id`` (only
        if still fresh) and finds the entry matching ``eero_id`` by its
        ``id`` field or the trailing segment of its ``url``.

        Args:
            network_id: The resolved network ID the eero belongs to.
            eero_id: A bare eero ID, API-returned path, or absolute URL.

        Returns:
            ``{"parent": <matching eero envelope>}`` when found, else ``{}``.
        """
        cache_key = f"{network_id}_eeros"
        if not self._is_cache_valid("eeros", cache_key):
            return {}
        cached = self._get_from_cache("eeros", cache_key)
        if not isinstance(cached, dict):
            return {}
        match = self._find_by_id_or_url(cached.get("data"), eero_id)
        return {"parent": match} if match is not None else {}

    def _device_parent_kwargs(self, network_id: str, device_id: str) -> Dict[str, Any]:
        """Build a ``parent=`` kwarg dict from a cached single-device envelope.

        Args:
            network_id: The resolved network ID the device belongs to.
            device_id: The device's bare MAC, path, or absolute URL.

        Returns:
            ``{"parent": <cached device envelope>}`` when a fresh cached
            envelope exists for this exact device, else ``{}``.
        """
        cache_key = f"{network_id}_{device_id}"
        if not self._is_cache_valid("devices", cache_key):
            return {}
        cached = self._get_from_cache("devices", cache_key)
        return {"parent": cached} if cached is not None else {}

    # ==================== Authentication ====================

    async def login(self, user_identifier: str) -> bool:
        """Start the login process by requesting a verification code.

        Args:
            user_identifier: Email address or phone number for the Eero account

        Returns:
            True if login request was successful
        """
        return await self._api.login(user_identifier)

    async def verify(self, verification_code: str) -> bool:
        """Verify login with the code sent to the user.

        Args:
            verification_code: The verification code sent to the user

        Returns:
            True if verification was successful
        """
        result = await self._api.verify(verification_code)
        if result:
            self.clear_cache()
        return result

    async def logout(self) -> bool:
        """Log out from the Eero API.

        Returns:
            True if logout was successful
        """
        result = await self._api.logout()
        if result:
            self.clear_cache()
        return result

    async def set_session_token(self, token: str) -> None:
        """Seed the active session with a pre-existing session token.

        Bypasses the interactive login + verify flow.  Useful when the token
        is supplied externally (e.g. from a secret manager, environment
        variable, or test fixture).

        Any in-memory cache entries are invalidated so that the very next
        request uses the new session.

        Args:
            token: The opaque session-cookie value (the ``s=`` cookie).

        Raises:
            EeroValidationException: If the token is empty or non-string.
        """
        await self._api.auth.set_session_token(token)
        self.clear_cache()

    async def clear_session_token(self) -> None:
        """Clear the active session token from cookie jar, in-memory creds, and storage.

        Any in-memory cache entries are invalidated alongside the token so that
        subsequent requests are not served stale data from a previous session.
        """
        await self._api.auth.clear_session_token()
        self.clear_cache()

    # ==================== Account ====================

    async def get_account(self, refresh_cache: bool = False) -> Dict[str, Any]:
        """Get account information - returns raw Eero API response.

        Args:
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        if not refresh_cache and self._is_cache_valid("account"):
            cached = self._get_from_cache("account")
            if cached:
                return cached

        response = await self._api.auth.get(
            "/account", auth_token=await self._api.auth.get_auth_token()
        )
        self._update_cache("account", None, response)
        return response

    # ==================== Networks ====================

    async def get_networks(self, refresh_cache: bool = False) -> Dict[str, Any]:
        """Get list of networks - returns raw Eero API response.

        Args:
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Note:
            The Eero API may return an empty list from the /networks endpoint.
            In this case, we fall back to extracting networks from the /account endpoint.
        """
        if not refresh_cache and self._is_cache_valid("networks"):
            cached = self._get_from_cache("networks")
            if cached:
                return cached

        response = await self._api.networks.get_networks()

        # Check if response has networks
        data = response.get("data", {})
        networks = []
        if isinstance(data, list):
            networks = data
        elif isinstance(data, dict):
            networks = data.get("networks") or data.get("data") or []

        # If /networks returns empty, fall back to /account endpoint
        if not networks:
            _LOGGER.debug("Networks endpoint returned empty, falling back to account endpoint")
            try:
                account_response = await self.get_account(refresh_cache=True)
                account_data = account_response.get("data", {})
                networks_data = account_data.get("networks", {})

                # Extract networks from account response
                if isinstance(networks_data, dict):
                    networks = networks_data.get("data", [])
                elif isinstance(networks_data, list):
                    networks = networks_data

                if networks:
                    # Construct a response in the expected format
                    response = {
                        "meta": response.get("meta", {}),
                        "data": {"networks": networks},
                    }
            except Exception as e:
                _LOGGER.debug("Failed to get networks from account endpoint: %s", e)

        self._update_cache("networks", None, response)

        # Set preferred network ID if not already set
        if not self._preferred_network_id:
            # Re-extract networks from updated response
            data = response.get("data", {})
            networks = []
            if isinstance(data, list):
                networks = data
            elif isinstance(data, dict):
                networks = data.get("networks") or data.get("data") or []

            if networks and len(networks) > 0:
                first_network = networks[0]
                net_id = first_network.get("id")
                if not net_id and first_network.get("url"):
                    net_id = first_network["url"].rstrip("/").split("/")[-1]
                if net_id:
                    self._preferred_network_id = net_id

        return response

    async def get_network(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> Dict[str, Any]:
        """Get network information - returns raw Eero API response.

        Args:
            network_id: ID of the network to get (uses preferred network if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        if not refresh_cache and self._is_cache_valid("network", network_id):
            cached = self._get_from_cache("network", network_id)
            if cached:
                return cached

        response = await self._api.networks.get_network(network_id)
        self._update_cache("network", network_id, response)
        return response

    async def get_premium_status(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get premium status - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.networks.get_premium_status(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_network_name(self, name: str, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Set network name - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.networks.set_network_name(
            network_id, name, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_network_password(
        self, password: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set the network's Wi-Fi password - returns raw Eero API response.

        .. warning::
            This write disconnects clients while it takes effect, and has
            not been confirmed against a live network. Follow the
            read-compare-skip discipline and do not retry on failure.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.networks.set_network_password(
            network_id, password, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def clear_network_password(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Clear the network's Wi-Fi password - returns raw Eero API response.

        .. warning::
            This write disconnects clients while it takes effect, and has
            not been confirmed against a live network. Follow the
            read-compare-skip discipline and do not retry on failure.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.networks.clear_network_password(
            network_id, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    # ==================== Eeros ====================

    async def get_eeros(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> Dict[str, Any]:
        """Get list of Eero devices - returns raw Eero API response.

        Args:
            network_id: ID of the network to get Eeros from (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_eeros"
        if not refresh_cache and self._is_cache_valid("eeros", cache_key):
            cached = self._get_from_cache("eeros", cache_key)
            if cached:
                return cached

        response = await self._api.eeros.get_eeros(
            network_id, **self._network_parent_kwargs(network_id)
        )
        self._update_cache("eeros", cache_key, response)
        return response

    async def get_eero(
        self,
        eero_id: str,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Dict[str, Any]:
        """Get information about a specific Eero device - returns raw Eero API response.

        Args:
            eero_id: ID of the Eero device to get
            network_id: ID of the network (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)
        return await self._api.eeros.get_eero(
            network_id, eero_id, **self._eero_parent_kwargs(network_id, eero_id)
        )

    async def reboot_eero(self, eero_id: str, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Reboot an Eero device - returns raw Eero API response.

        Args:
            eero_id: ID of the Eero device to reboot
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.eeros.reboot_eero(
            network_id, eero_id, **self._eero_parent_kwargs(network_id, eero_id)
        )
        self._invalidate_eeros_cache(network_id)
        return response

    def _invalidate_eeros_cache(self, network_id: str) -> None:
        """Drop the cached eeros list for a network after a write to one of its eeros."""
        cache_key = f"{network_id}_eeros"
        if cache_key in self._cache.get("eeros", {}):
            del self._cache["eeros"][cache_key]

    async def set_location(
        self, eero_id: str, location: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set the descriptive location label for an Eero device - returns raw Eero API response.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_eero` first, and
            only issue this write when the stored location differs from the
            desired one.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.eeros.set_location(
            network_id, eero_id, location, **self._eero_parent_kwargs(network_id, eero_id)
        )
        self._invalidate_eeros_cache(network_id)
        return response

    async def get_connections(
        self, eero_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get an Eero device's client connections - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.get_connections(
            network_id, eero_id, **self._eero_parent_kwargs(network_id, eero_id)
        )

    # ==================== Devices ====================

    async def get_devices(
        self,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
        *,
        thread: Optional[bool] = None,
        proxied_node: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Get list of connected devices - returns raw Eero API response.

        Args:
            network_id: ID of the network to get devices from (uses preferred if None)
            refresh_cache: Whether to refresh the cache
            thread: When supplied, filters devices by Thread membership.
                Bypasses the cache, since the cached list is unfiltered.
            proxied_node: When supplied, filters devices by whether they are
                a proxied node. Bypasses the cache, like ``thread``.

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)
        filtered = thread is not None or proxied_node is not None

        cache_key = f"{network_id}_devices"
        if not filtered and not refresh_cache and self._is_cache_valid("devices", cache_key):
            cached = self._get_from_cache("devices", cache_key)
            if cached:
                return cached

        response = await self._api.devices.get_devices(
            network_id,
            thread=thread,
            proxied_node=proxied_node,
            **self._network_parent_kwargs(network_id),
        )
        if not filtered:
            self._update_cache("devices", cache_key, response)
        return response

    async def get_device(
        self,
        device_id: str,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Dict[str, Any]:
        """Get information about a specific device - returns raw Eero API response.

        Args:
            device_id: ID of the device to get
            network_id: ID of the network (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_{device_id}"
        if not refresh_cache and self._is_cache_valid("devices", cache_key):
            cached = self._get_from_cache("devices", cache_key)
            if cached:
                return cached

        response = await self._api.devices.get_device(network_id, device_id)
        self._update_cache("devices", cache_key, response)
        return response

    async def set_device_nickname(
        self, device_id: str, nickname: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set a nickname for a device - returns raw Eero API response.

        Args:
            device_id: ID of the device
            nickname: New nickname for the device
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.devices.set_device_nickname(network_id, device_id, nickname)

        # Clear device cache
        self._invalidate_device_cache(network_id, device_id)

        return response

    async def block_device(
        self, device_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a device to the network's block list - returns raw Eero API response.

        Args:
            device_id: MAC address of the device to block.
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.devices.block_device(network_id, device_id)

        self._invalidate_device_cache(network_id, device_id)

        return response

    async def unblock_device(
        self, device_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Remove a device from the network's block list - returns raw Eero API response.

        Args:
            device_id: MAC address (or blacklist device ID) to unblock.
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.devices.unblock_device(network_id, device_id)

        self._invalidate_device_cache(network_id, device_id)

        return response

    async def pause_device(
        self, device_id: str, paused: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pause or unpause internet access for a device - returns raw Eero API response.

        Args:
            device_id: ID of the device
            paused: True to pause internet access, False to resume
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.devices.pause_device(network_id, device_id, paused)

        # Clear device cache
        self._invalidate_device_cache(network_id, device_id)

        return response

    async def update_device_via_link(
        self,
        device_id: str,
        *,
        nickname: Optional[str] = None,
        paused: Optional[bool] = None,
        profile: Optional[str] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a device via its own URL - returns raw Eero API response.

        .. warning::
            Unlike `set_device_nickname`/`pause_device`, this path has not
            been live-verified. Prefer `set_device_nickname` and
            `pause_device` for those two fields. Follow the
            read-compare-skip discipline for any write through this method:
            read the device back afterwards and do not retry on failure.
        """
        network_id = await self._ensure_network_id(network_id)
        response = await self._api.devices.update_device_via_link(
            network_id,
            device_id,
            nickname=nickname,
            paused=paused,
            profile=profile,
            **self._device_parent_kwargs(network_id, device_id),
        )
        self._invalidate_device_cache(network_id, device_id)
        return response

    async def set_device_type(
        self, device_id: str, device_type: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set a device's type - returns raw Eero API response.

        .. warning::
            This write has not been verified against a live network. Follow
            the read-compare-skip discipline: read the device back
            afterwards and do not retry on failure.
        """
        network_id = await self._ensure_network_id(network_id)
        response = await self._api.devices.set_device_type(network_id, device_id, device_type)
        self._invalidate_device_cache(network_id, device_id)
        return response

    async def get_device_labels(
        self, device_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the hardware/manufacturer labels for a device - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id)
        return await self._api.devices.get_device_labels(network_id, device_id)

    async def set_device_labels(
        self,
        device_id: str,
        *,
        make_label: Optional[str] = None,
        model_label: Optional[str] = None,
        version_label: Optional[str] = None,
        type_label: Optional[str] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set the hardware/manufacturer labels for a device - returns raw Eero API response.

        .. warning::
            This write has not been verified against a live network. Follow
            the read-compare-skip discipline: call `get_device_labels`
            afterwards and do not retry on failure.
        """
        network_id = await self._ensure_network_id(network_id)
        response = await self._api.devices.set_device_labels(
            network_id,
            device_id,
            make_label=make_label,
            model_label=model_label,
            version_label=version_label,
            type_label=type_label,
        )
        self._invalidate_device_cache(network_id, device_id)
        return response

    def _invalidate_device_cache(self, network_id: str, device_id: str) -> None:
        """Invalidate device-related cache entries."""
        cache_key = f"{network_id}_{device_id}"
        if cache_key in self._cache.get("devices", {}):
            del self._cache["devices"][cache_key]

        cache_key = f"{network_id}_devices"
        if cache_key in self._cache.get("devices", {}):
            del self._cache["devices"][cache_key]

    # ==================== Profiles ====================

    async def get_profiles(
        self, network_id: Optional[str] = None, refresh_cache: bool = False
    ) -> Dict[str, Any]:
        """Get list of profiles - returns raw Eero API response.

        Args:
            network_id: ID of the network to get profiles from (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": [...]}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_profiles"
        if not refresh_cache and self._is_cache_valid("profiles", cache_key):
            cached = self._get_from_cache("profiles", cache_key)
            if cached:
                return cached

        response = await self._api.profiles.get_profiles(
            network_id, **self._network_parent_kwargs(network_id)
        )
        self._update_cache("profiles", cache_key, response)
        return response

    async def get_profile(
        self,
        profile_id: str,
        network_id: Optional[str] = None,
        refresh_cache: bool = False,
    ) -> Dict[str, Any]:
        """Get information about a specific profile - returns raw Eero API response.

        Args:
            profile_id: ID of the profile to get
            network_id: ID of the network (uses preferred if None)
            refresh_cache: Whether to refresh the cache

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroException: If no network ID is available
        """
        network_id = await self._ensure_network_id(network_id)

        cache_key = f"{network_id}_{profile_id}"
        if not refresh_cache and self._is_cache_valid("profiles", cache_key):
            cached = self._get_from_cache("profiles", cache_key)
            if cached:
                return cached

        response = await self._api.profiles.get_profile(network_id, profile_id)
        self._update_cache("profiles", cache_key, response)
        return response

    async def pause_profile(
        self, profile_id: str, paused: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Pause or unpause internet access for a profile - returns raw Eero API response.

        Args:
            profile_id: ID of the profile
            paused: Whether to pause or unpause the profile
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.profiles.pause_profile(network_id, profile_id, paused)

        # Clear profile cache
        self._invalidate_profile_cache(network_id, profile_id)

        return response

    def _invalidate_profile_cache(self, network_id: str, profile_id: str) -> None:
        """Invalidate profile-related cache entries."""
        cache_key = f"{network_id}_{profile_id}"
        if cache_key in self._cache.get("profiles", {}):
            del self._cache["profiles"][cache_key]

        cache_key = f"{network_id}_profiles"
        if cache_key in self._cache.get("profiles", {}):
            del self._cache["profiles"][cache_key]

    def _invalidate_profiles_list_cache(self, network_id: str) -> None:
        """Invalidate the profiles list cache for a network."""
        cache_key = f"{network_id}_profiles"
        if cache_key in self._cache.get("profiles", {}):
            del self._cache["profiles"][cache_key]

    async def create_profile(
        self,
        name: str,
        *,
        devices: Optional[List[str]] = None,
        paused: Optional[bool] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new profile on the network - returns raw Eero API response.

        Args:
            name: Name for the new profile
            devices: Optional list of device URLs to assign at creation time.
            paused: Optional initial paused state.
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.profiles.create_profile(
            network_id,
            name,
            devices=devices,
            paused=paused,
            **self._network_parent_kwargs(network_id),
        )

        self._invalidate_profiles_list_cache(network_id)

        return response

    async def rename_profile(
        self, profile_id: str, name: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Rename an existing profile - returns raw Eero API response.

        Args:
            profile_id: ID of the profile to rename
            name: New name for the profile
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.profiles.rename_profile(network_id, profile_id, name)

        self._invalidate_profile_cache(network_id, profile_id)
        self._invalidate_profiles_list_cache(network_id)

        return response

    async def delete_profile(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a profile from the network - returns raw Eero API response.

        Devices previously assigned to this profile will become unassigned.

        Args:
            profile_id: ID of the profile to delete
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {"code": 200, ...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.profiles.delete_profile(network_id, profile_id)

        self._invalidate_profile_cache(network_id, profile_id)
        self._invalidate_profiles_list_cache(network_id)

        return response

    # ==================== Guest Network ====================

    async def get_guest_network(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get guest network configuration - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.networks.get_guest_network(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_guest_network(
        self,
        enabled: bool,
        name: Optional[str] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enable or disable the guest network - returns raw Eero API response.

        Use `set_guest_password` to set the guest network's password.

        Args:
            enabled: Whether to enable or disable the guest network
            name: Optional new name for the guest network
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.networks.set_guest_network(
            network_id,
            enabled=enabled,
            name=name,
            **self._network_parent_kwargs(network_id),
        )

        # Clear network cache
        self._invalidate_network_cache(network_id)

        return response

    async def set_guest_password(
        self, password: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set the guest network's password - returns raw Eero API response.

        .. warning::
            This write disconnects guest clients while it takes effect, and
            has not been confirmed against a live network. Follow the
            read-compare-skip discipline and do not retry on failure.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.networks.set_guest_password(network_id, password)
        self._invalidate_network_cache(network_id)
        return response

    async def clear_guest_password(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Clear the guest network's password - returns raw Eero API response.

        .. warning::
            This write disconnects guest clients while it takes effect, and
            has not been confirmed against a live network. Follow the
            read-compare-skip discipline and do not retry on failure.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.networks.clear_guest_password(network_id)
        self._invalidate_network_cache(network_id)
        return response

    # ==================== Speed Test ====================

    async def run_speed_test(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Run a speed test on the network - returns raw Eero API response.

        Args:
            network_id: ID of the network (uses preferred if None)

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        network_id = await self._ensure_network_id(network_id)

        response = await self._api.networks.run_speed_test(
            network_id, **self._network_parent_kwargs(network_id)
        )

        # Clear network cache
        self._invalidate_network_cache(network_id)

        return response

    async def get_speed_tests(
        self,
        network_id: Optional[str] = None,
        *,
        limit: Optional[int] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get past speed test results - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.networks.get_speed_tests(
            network_id,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
            **self._network_parent_kwargs(network_id),
        )

    # ==================== Network Settings ====================

    def set_preferred_network(self, network_id: str) -> None:
        """Set the preferred network ID to use for requests.

        This is an in-memory preference only. For persistent storage,
        the CLI application should manage its own configuration file.

        Args:
            network_id: ID of the network to use
        """
        self._preferred_network_id = network_id

    @property
    def preferred_network_id(self) -> Optional[str]:
        """Get the preferred network ID."""
        return self._preferred_network_id

    # ==================== Diagnostics & Settings ====================

    async def get_diagnostics(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get network diagnostics - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.diagnostics.get_diagnostics(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def run_diagnostics(
        self,
        network_id: Optional[str] = None,
        *,
        device: Optional[str] = None,
        symptom: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run network diagnostics - returns raw Eero API response.

        .. warning::
            The request body shape has not been confirmed against a live
            network. Follow the read-compare-skip discipline where
            applicable, and do not retry on failure.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.diagnostics.run_diagnostics(
            network_id,
            device=device,
            symptom=symptom,
            **self._network_parent_kwargs(network_id),
        )

    async def get_insights(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        insight_type: str,
        cadence: str = "daily",
    ) -> Dict[str, Any]:
        """Query insights time-series data - returns raw Eero API response.

        Thin wrapper over :meth:`InsightsAPI.get_insights`. See that method's
        docstring for parameter semantics and response shape. The Eero cloud
        API requires ``start``, ``end``, ``insight_type``, and ``cadence``
        as query parameters; only ``cadence`` has an SDK-supplied default
        (``"daily"``) since it controls display bucketing rather than data
        scope.

        Args:
            network_id: ID of the network (uses preferred if None).
            start: Window start, ISO 8601 timestamp (e.g. ``"2026-07-21T00:00:00Z"``).
            end: Window end, ISO 8601 timestamp.
            insight_type: One of ``"adblock"``, ``"blocked"``, ``"inspected"``.
            cadence: One of ``"hourly"``, ``"daily"``, ``"weekly"``. Defaults to
                ``"daily"``.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.insights.get_insights(
            network_id,
            start=start,
            end=end,
            insight_type=insight_type,
            cadence=cadence,
        )

    async def get_devices_insights(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
    ) -> Dict[str, Any]:
        """Query insights series for every device on a network - raw response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.insights.get_devices_insights(
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            insight_type=insight_type,
            **self._network_parent_kwargs(network_id),
        )

    async def get_device_insights(
        self,
        device_id: str,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
    ) -> Dict[str, Any]:
        """Query the insights series for a single device - raw response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.insights.get_device_insights(
            network_id,
            device_id,
            start=start,
            end=end,
            cadence=cadence,
            insight_type=insight_type,
        )

    async def get_profiles_insights(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
    ) -> Dict[str, Any]:
        """Query insights series for every profile on a network - raw response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.insights.get_profiles_insights(
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            insight_type=insight_type,
            **self._network_parent_kwargs(network_id),
        )

    async def get_profile_insights(
        self,
        profile_id: str,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
    ) -> Dict[str, Any]:
        """Query the insights series for a single profile - raw response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.insights.get_profile_insights(
            network_id,
            profile_id,
            start=start,
            end=end,
            cadence=cadence,
            insight_type=insight_type,
        )

    async def get_profile_devices_insights(
        self,
        profile_id: str,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        insight_type: str,
    ) -> Dict[str, Any]:
        """Query insights series for the devices assigned to a profile - raw response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.insights.get_profile_devices_insights(
            network_id,
            profile_id,
            start=start,
            end=end,
            cadence=cadence,
            insight_type=insight_type,
        )

    async def get_routing(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get network routing - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.routing.get_routing(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def get_thread(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get Thread status - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.thread.get_thread(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_thread_enabled(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable or disable Thread - returns raw Eero API response.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_thread` first, and
            only issue this write when the stored value differs from the
            desired one.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.thread.set_thread_enabled(network_id, enabled)
        self._invalidate_network_cache(network_id)
        return response

    async def update_thread(
        self,
        *,
        thread_enable: Optional[bool] = None,
        enable_credential_syncing: Optional[bool] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update Thread configuration - returns raw Eero API response.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_thread` first, and
            only issue this write when the stored configuration differs from
            the desired one.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.thread.update_thread(
            network_id,
            thread_enable=thread_enable,
            enable_credential_syncing=enable_credential_syncing,
        )
        self._invalidate_network_cache(network_id)
        return response

    async def regenerate_thread_credentials(
        self, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Regenerate Thread network credentials - returns raw Eero API response.

        .. warning::
            This write has not been confirmed against a live network. The
            response is documented to carry a ``network`` key of unknown
            shape -- this method returns it unmodified.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.thread.regenerate_thread_credentials(network_id)
        self._invalidate_network_cache(network_id)
        return response

    async def get_support(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get support info - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.support.get_support(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def get_blacklist(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get device blacklist - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.blacklist.get_blacklist(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def get_reservations(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get DHCP reservations - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.reservations.get_reservations(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def create_reservation(
        self, reservation_data: Dict[str, Any], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a DHCP reservation - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.reservations.create_reservation(
            network_id, reservation_data, **self._network_parent_kwargs(network_id)
        )

    async def update_reservation(
        self,
        reservation_id: str,
        reservation_data: Dict[str, Any],
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a DHCP reservation - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.reservations.update_reservation(
            reservation_id, reservation_data, network=network_id
        )

    async def delete_reservation(
        self,
        reservation_id: str,
        network_id: Optional[str] = None,
        *,
        delete_forwards: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Delete a DHCP reservation - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        kwargs: Dict[str, Any] = {}
        if delete_forwards is not None:
            kwargs["delete_forwards"] = delete_forwards
        return await self._api.reservations.delete_reservation(network_id, reservation_id, **kwargs)

    async def get_forwards(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get port forwards - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.forwards.get_forwards(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def create_forward(
        self, forward_data: Dict[str, Any], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a port forward - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.forwards.create_forward(
            network_id, forward_data, **self._network_parent_kwargs(network_id)
        )

    async def update_forward(
        self,
        forward_id: str,
        forward_data: Dict[str, Any],
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a port forward - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.forwards.update_forward(forward_id, forward_data, network=network_id)

    async def delete_forward(
        self, forward_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a port forward - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.forwards.delete_forward(network_id, forward_id)

    async def get_transfer_stats(
        self, network_id: Optional[str] = None, device_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get transfer statistics - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.transfer.get_transfer_stats(
            network_id, device_id, **self._network_parent_kwargs(network_id)
        )

    async def get_data_usage(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get network-level data usage - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_data_usage`. The reads in
        this family are time-windowed, so they are never cached.

        Args:
            network_id: ID of the network (uses preferred if None).
            start: Window start, ISO 8601 timestamp.
            end: Window end, ISO 8601 timestamp.
            cadence: Bucket size for the returned series, ``"daily"`` or
                ``"hourly"``.
            timezone: Optional IANA timezone name.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_data_usage(
            network_id, start=start, end=end, cadence=cadence, timezone=timezone
        )

    async def get_data_usage_breakdown(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a data usage breakdown - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_breakdown`. Not cached; the
        read is time-windowed.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_breakdown(
            network_id, start=start, end=end, cadence=cadence, timezone=timezone
        )

    async def get_devices_data_usage(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: Optional[str] = None,
        timezone: Optional[str] = None,
        profile_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get per-device data usage - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_devices_usage`. Not cached;
        the read is time-windowed.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_devices_usage(
            network_id,
            start=start,
            end=end,
            cadence=cadence,
            timezone=timezone,
            profile_id=profile_id,
        )

    async def get_device_data_usage(
        self,
        device_mac: str,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data usage for a single device - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_device_usage`. Not cached;
        the read is time-windowed.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_device_usage(
            network_id, device_mac, start=start, end=end, cadence=cadence, timezone=timezone
        )

    async def get_eeros_data_usage_summary(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a summary of data usage across all Eero devices - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_eeros_summary`. Not cached;
        the read is time-windowed.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_eeros_summary(
            network_id, start=start, end=end, cadence=cadence, timezone=timezone
        )

    async def get_eero_data_usage(
        self,
        eero_id: str,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data usage for a single Eero device - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_eero_usage`. Not cached;
        the read is time-windowed.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_eero_usage(
            network_id, eero_id, start=start, end=end, cadence=cadence, timezone=timezone
        )

    async def get_profile_data_usage(
        self,
        profile_id: str,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data usage for a single profile - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_profile_usage`. Not cached;
        the read is time-windowed.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_profile_usage(
            network_id, profile_id, start=start, end=end, cadence=cadence, timezone=timezone
        )

    async def get_unprofiled_devices_data_usage(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: Optional[str] = None,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get data usage for devices not assigned to a profile - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_unprofiled_devices`. Not
        cached; the read is time-windowed.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_unprofiled_devices(
            network_id, start=start, end=end, cadence=cadence, timezone=timezone
        )

    async def get_unprofiled_data_usage_summary(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        cadence: str,
        timezone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a summary of data usage for unprofiled devices - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_unprofiled_summary`. Not
        cached; the read is time-windowed.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_unprofiled_summary(
            network_id, start=start, end=end, cadence=cadence, timezone=timezone
        )

    async def get_data_usage_report_settings(
        self, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the data usage report settings for a network - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.get_report_settings`.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.data_usage.get_report_settings(network_id)

    async def set_data_usage_report_settings(
        self,
        *,
        cadence: str,
        notification_day: str,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set the data usage report settings for a network - returns raw Eero API response.

        Thin wrapper over :meth:`DataUsageAPI.set_report_settings`. See that
        method's docstring — this write is not live-verified and must be
        issued conditionally (read via `get_data_usage_report_settings`
        first, skip if unchanged) rather than unconditionally or in a retry
        loop.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.data_usage.set_report_settings(
            network_id, cadence=cadence, notification_day=notification_day
        )
        self._invalidate_network_cache(network_id)
        return response

    async def get_ac_compat(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get AC compatibility - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.ac_compat.get_ac_compat(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def get_ouicheck(
        self,
        network_id: Optional[str] = None,
        *,
        serial: str,
        version: str,
    ) -> Dict[str, Any]:
        """Get OUI check - returns raw Eero API response.

        Args:
            network_id: ID of the network (uses preferred if None).
            serial: Serial number of the eero hardware being checked.
            version: Firmware/hardware version string of the eero hardware
                being checked.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.ouicheck.get_ouicheck(
            network_id, serial=serial, version=version, **self._network_parent_kwargs(network_id)
        )

    async def get_updates(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get update info - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.updates.get_updates(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def apply_update(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Apply a pending update - returns raw Eero API response.

        .. warning::
            This is a reboot-class write: applying an update reboots every
            node on the network, and its request/response shape has not
            been confirmed against a live network. Follow the
            read-compare-skip discipline: read `get_updates` first, and only
            issue this write when an update is actually pending. Never
            retry on failure.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.updates.apply_update(
            network_id, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    # ==================== LED & Nightlight ====================

    async def get_led_status(
        self, eero_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get LED status - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.get_led_status(
            network_id, eero_id, **self._eero_parent_kwargs(network_id, eero_id)
        )

    async def set_led(
        self, eero_id: str, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set LED on/off - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.eeros.set_led(
            network_id, eero_id, enabled, **self._eero_parent_kwargs(network_id, eero_id)
        )
        self._invalidate_eeros_cache(network_id)
        return response

    async def set_led_brightness(
        self, eero_id: str, brightness: int, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set LED brightness - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.eeros.set_led_brightness(
            network_id, eero_id, brightness, **self._eero_parent_kwargs(network_id, eero_id)
        )
        self._invalidate_eeros_cache(network_id)
        return response

    async def get_nightlight(
        self, eero_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get nightlight settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.eeros.get_nightlight(
            network_id, eero_id, **self._eero_parent_kwargs(network_id, eero_id)
        )

    async def set_nightlight(
        self,
        eero_id: str,
        enabled: Optional[bool] = None,
        brightness_percentage: Optional[int] = None,
        schedule: Optional[Dict[str, Any]] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set nightlight settings - returns raw Eero API response.

        .. warning::
            This write has not been confirmed against a live network.
            Follow the read-compare-skip discipline: read `get_nightlight`
            first, and only issue this write when the stored settings
            differ from the desired ones.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.eeros.set_nightlight(
            network_id,
            eero_id,
            enabled=enabled,
            brightness_percentage=brightness_percentage,
            schedule=schedule,
            **self._eero_parent_kwargs(network_id, eero_id),
        )
        self._invalidate_eeros_cache(network_id)
        return response

    async def set_nightlight_brightness(
        self,
        eero_id: str,
        brightness_percentage: int,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set nightlight brightness - returns raw Eero API response.

        Convenience wrapper around `set_nightlight` for just the brightness
        field.
        """
        return await self.set_nightlight(
            eero_id, brightness_percentage=brightness_percentage, network_id=network_id
        )

    async def set_nightlight_schedule(
        self,
        eero_id: str,
        schedule: Dict[str, Any],
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set nightlight schedule - returns raw Eero API response.

        Convenience wrapper around `set_nightlight` for just the schedule
        field.
        """
        return await self.set_nightlight(eero_id, schedule=schedule, network_id=network_id)

    # ==================== Backup Internet ====================

    async def get_backup_internet(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get backup internet configuration - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.get_backup_internet(network_id)

    async def set_backup_internet(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable or disable backup internet - returns raw Eero API response.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_backup_internet`
            first, and only issue this write when the stored value differs
            from the desired one.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.backup.set_backup_internet(network_id, enabled)
        self._invalidate_network_cache(network_id)
        return response

    async def get_cellular_backup_usage(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get cellular backup data usage - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.get_cellular_backup_usage(network_id)

    async def get_cellular_backup_events(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get cellular backup events - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup.get_cellular_backup_events(network_id)

    # ==================== Schedule ====================

    async def get_schedules(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get the scheduled pauses for a profile - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.get_schedules(network_id, profile_id)

    async def create_schedule(
        self,
        profile_id: str,
        *,
        name: str,
        days: List[str],
        start: str,
        end: str,
        enabled: bool = True,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a scheduled pause for a profile - returns raw Eero API response.

        .. warning::
            This write has not been verified against a live network. Follow
            the read-compare-skip discipline: read `get_schedules` first,
            and do not retry a failed write.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.create_schedule(
            network_id, profile_id, name=name, days=days, start=start, end=end, enabled=enabled
        )

    async def update_schedule(
        self,
        schedule: Any,
        *,
        name: Optional[str] = None,
        days: Optional[List[str]] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a scheduled pause via its own URL - returns raw Eero API response.

        .. warning::
            This write has not been verified against a live network. Follow
            the read-compare-skip discipline and do not retry on failure.

        Args:
            schedule: The pause's own path/absolute URL (as returned by
                `get_schedules`/`create_schedule`), or its cached envelope.
            name: New name, or ``None`` to omit.
            days: New days list, or ``None`` to omit.
            start: New start time, or ``None`` to omit.
            end: New end time, or ``None`` to omit.
            enabled: New enabled state, or ``None`` to omit.
        """
        return await self._api.schedule.update_schedule(
            schedule, name=name, days=days, start=start, end=end, enabled=enabled
        )

    async def delete_schedule(self, schedule: Any) -> Dict[str, Any]:
        """Delete a scheduled pause via its own URL - returns raw Eero API response.

        Args:
            schedule: The pause's own path/absolute URL, or its cached
                envelope.
        """
        return await self._api.schedule.delete_schedule(schedule)

    async def clear_profile_schedule(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Delete every scheduled pause currently set on a profile.

        Returns:
            A list of the raw API responses from each individual DELETE.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.clear_profile_schedule(network_id, profile_id)

    async def enable_bedtime(
        self,
        profile_id: str,
        start_time: str,
        end_time: str,
        days: Optional[List[str]] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enable bedtime - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.schedule.enable_bedtime(
            network_id, profile_id, start_time, end_time, days
        )

    # ==================== DNS ====================

    async def get_dns_settings(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get DNS settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns.get_dns_settings(network_id)

    def _invalidate_network_cache(self, network_id: str) -> None:
        """Drop the cached network snapshot after a write to it.

        DNS settings live inside the network resource, so any DNS write makes a
        cached snapshot stale. Mirrors `set_network_name` / `set_guest_network`.
        """
        if network_id in self._cache.get("network", {}):
            del self._cache["network"][network_id]

    async def set_dns_caching(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set DNS caching - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns.set_dns_caching(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_custom_dns(
        self, dns_servers: List[str], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set custom DNS from a mixed IPv4/IPv6 list - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns.set_custom_dns(
            network_id, dns_servers, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_custom_dns_ipv4(
        self, dns_servers: List[str], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set IPv4 custom DNS, leaving IPv6 untouched - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns.set_custom_dns_ipv4(
            network_id, dns_servers, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_custom_dns_ipv6(
        self, dns_servers: List[str], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set IPv6 custom DNS, leaving IPv4 untouched - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns.set_custom_dns_ipv6(
            network_id, dns_servers, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def clear_custom_dns(
        self, family: Optional[str] = None, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Switch DNS back to automatic - returns raw Eero API response.

        Non-destructive: the API retains the configured servers. Pass
        family="ipv4" or "ipv6" to clear one family only.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns.clear_custom_dns(
            network_id, family, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_dns_mode(
        self,
        mode: str,
        custom_servers: Optional[List[str]] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set DNS mode - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns.set_dns_mode(
            network_id, mode, custom_servers, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    # ==================== SQM ====================

    async def get_sqm_settings(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get SQM settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.sqm.get_sqm_settings(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_sqm(self, enabled: bool, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Enable or disable SQM (Smart Queue Management) - returns raw Eero API response.

        .. warning::
            This is a settings-class write: it has not been confirmed
            against a live network, and -- like other writes to this
            endpoint -- may trigger a mesh reboot. Follow the
            read-compare-skip discipline: read `get_sqm_settings` first, and
            only issue this write when the stored value differs from the
            desired one. Never retry on failure.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.sqm.set_sqm(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    # ==================== Device Priority ====================

    async def get_device_priority(
        self, device_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get device priority - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.devices.get_device(network_id, device_id)

    # ==================== Security ====================

    async def get_security_settings(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get security settings - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.get_security_settings(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_wpa3(self, enabled: bool, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Set WPA3 - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.security.set_wpa3(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_band_steering(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set band steering - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.security.set_band_steering(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_upnp(self, enabled: bool, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Set UPnP - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.security.set_upnp(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_ipv6(self, enabled: bool, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Set IPv6 - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.security.set_ipv6(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def configure_security(
        self,
        wpa3: Optional[bool] = None,
        band_steering: Optional[bool] = None,
        upnp: Optional[bool] = None,
        ipv6: Optional[bool] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Configure security - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.security.configure_security(
            network_id,
            wpa3=wpa3,
            band_steering=band_steering,
            upnp=upnp,
            ipv6=ipv6,
            **self._network_parent_kwargs(network_id),
        )
        self._invalidate_network_cache(network_id)
        return response

    # ==================== Profile Devices ====================

    async def get_profile_devices(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get profile devices - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id)
        return await self._api.profiles.get_profile_devices(network_id, profile_id)

    async def set_profile_devices(
        self,
        profile_id: str,
        device_urls: List[str],
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set profile devices - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id)
        response = await self._api.profiles.set_profile_devices(network_id, profile_id, device_urls)
        self._invalidate_profile_cache(network_id, profile_id)
        return response

    # ==================== Entitlements & Capabilities ====================

    async def get_entitlement_features(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the network's entitled features - returns raw Eero API response.

        Verified read. Any premium-status interpretation belongs to the caller.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.entitlements.get_features(network_id)

    async def get_upsell_features(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the network's upsell features - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.entitlements.get_upsell_features(network_id)

    async def get_model_capabilities(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get eero model capabilities for the network - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.entitlements.get_model_capabilities(network_id)

    async def get_premium_customer(self) -> Dict[str, Any]:
        """Get the account's premium customer record - returns raw Eero API response."""
        return await self._api.entitlements.get_premium_customer()

    # ==================== Events & Telemetry ====================

    async def get_app_events(
        self,
        network_id: Optional[str] = None,
        *,
        page_size: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get the network's app events - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.events.get_app_events(
            network_id,
            page_size=page_size,
            timestamp=timestamp,
            **self._network_parent_kwargs(network_id),
        )

    async def get_network_scan(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the network scan result - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.events.get_network_scan(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def get_channel_utilization(
        self,
        network_id: Optional[str] = None,
        *,
        start: str,
        end: str,
        busy_threshold: Optional[int] = None,
        eero_id: Optional[int] = None,
        band: Optional[str] = None,
        granularity: Optional[int] = None,
        gap_data_placeholder: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Get Wi-Fi channel utilisation series - returns raw Eero API response.

        Verified read with ``start`` and ``end``; the optional parameters
        follow the API's declared shape. Not cached (time-windowed).
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.events.get_channel_utilization(
            network_id,
            start=start,
            end=end,
            busy_threshold=busy_threshold,
            eero_id=eero_id,
            band=band,
            granularity=granularity,
            gap_data_placeholder=gap_data_placeholder,
            **self._network_parent_kwargs(network_id),
        )

    async def get_permissions(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the current user's permissions on the network - raw response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.permissions.get_permissions(
            network_id, **self._network_parent_kwargs(network_id)
        )

    # ==================== Notifications ====================

    async def get_notification_settings(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get notification settings - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.notifications.get_settings(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_notification_settings(
        self, settings: Mapping[str, bool], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set notification settings - returns raw Eero API response.

        Unverified write; read the settings first and skip when unchanged.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.notifications.set_settings(
            network_id, settings, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def has_unread_notifications(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the unread-notifications flag - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.notifications.has_unread(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def mark_notifications_read(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Mark notifications read - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.notifications.mark_read(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def get_notification_history(
        self, network_id: Optional[str] = None, *, timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get notification history - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.notifications.get_history(
            network_id, timestamp=timestamp, **self._network_parent_kwargs(network_id)
        )

    async def set_push_settings(self, settings: Mapping[str, bool]) -> Dict[str, Any]:
        """Set the account's push settings - returns raw Eero API response (unverified write)."""
        return await self._api.notifications.set_push_settings(settings)

    # ==================== DNS Policies (content filtering) ====================

    async def get_advanced_content_filter(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the advanced content filter - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns_policies.get_advanced_content_filter(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def allow_domain(
        self,
        domain: str,
        network_id: Optional[str] = None,
        *,
        add_cname: Optional[bool] = None,
        reason_to_allow: Optional[int] = None,
        is_delete: Optional[bool] = None,
        keep_profiles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Allow a domain for the network - returns raw Eero API response.

        Unverified write. Removal is expressed with ``is_delete=True``.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns_policies.allow_domain(
            network_id,
            domain,
            add_cname=add_cname,
            reason_to_allow=reason_to_allow,
            is_delete=is_delete,
            keep_profiles=keep_profiles,
            **self._network_parent_kwargs(network_id),
        )
        self._invalidate_network_cache(network_id)
        return response

    async def allow_cnames(
        self, domains: List[str], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Allow CNAME domains for the network - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns_policies.allow_cnames(
            network_id, domains, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def block_domain(
        self,
        domain: str,
        network_id: Optional[str] = None,
        *,
        is_delete: Optional[bool] = None,
        keep_profiles: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Block a domain for the network - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns_policies.block_domain(
            network_id,
            domain,
            is_delete=is_delete,
            keep_profiles=keep_profiles,
            **self._network_parent_kwargs(network_id),
        )
        self._invalidate_network_cache(network_id)
        return response

    async def allow_domain_for_profiles(
        self,
        domain: str,
        network_id: Optional[str] = None,
        *,
        profiles: List[str],
        override: Optional[bool] = None,
        add_cname: Optional[bool] = None,
        reason_to_allow: Optional[int] = None,
        is_delete: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Allow a domain for profiles - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns_policies.allow_domain_for_profiles(
            network_id,
            domain,
            profiles=profiles,
            override=override,
            add_cname=add_cname,
            reason_to_allow=reason_to_allow,
            is_delete=is_delete,
            **self._network_parent_kwargs(network_id),
        )
        self._invalidate_profiles_list_cache(network_id)
        return response

    async def allow_cnames_for_profiles(
        self, domains: List[str], network_id: Optional[str] = None, *, profiles: List[str]
    ) -> Dict[str, Any]:
        """Allow CNAME domains for profiles - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns_policies.allow_cnames_for_profiles(
            network_id, domains, profiles=profiles, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_profiles_list_cache(network_id)
        return response

    async def block_domain_for_profiles(
        self,
        domain: str,
        network_id: Optional[str] = None,
        *,
        profiles: List[str],
        is_delete: Optional[bool] = None,
        override: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Block a domain for profiles - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns_policies.block_domain_for_profiles(
            network_id,
            domain,
            profiles=profiles,
            is_delete=is_delete,
            override=override,
            **self._network_parent_kwargs(network_id),
        )
        self._invalidate_profiles_list_cache(network_id)
        return response

    async def get_dns_policy_applications(
        self, profile_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a profile's application policies - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.dns_policies.get_profile_applications(network_id, profile_id)

    async def set_profile_blocked_applications(
        self, profile_id: str, applications: List[str], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set a profile's blocked applications - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dns_policies.set_profile_blocked_applications(
            network_id, profile_id, applications
        )
        self._invalidate_profile_cache(network_id, profile_id)
        return response

    # ==================== Members, Invites & Admins ====================

    async def get_members(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the network's members - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.members.get_members(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def get_invites(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get pending invites - returns raw Eero API response (unverified: 403 on some accounts)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.members.get_invites(network_id)

    async def create_invite(self, *, role: str, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Create an invite - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.members.create_invite(network_id, role=role)

    async def update_invite(
        self, invite_id: str, *, invite_nickname: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an invite's nickname - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.members.update_invite(
            network_id, invite_id, invite_nickname=invite_nickname
        )

    async def delete_invite(
        self, invite_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete an invite - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.members.delete_invite(network_id, invite_id)

    async def respond_to_invite(
        self,
        *,
        accept: bool,
        invite_id: Optional[str] = None,
        invite_code: Optional[str] = None,
        network_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Respond to an invite - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.members.respond_to_invite(
            network_id, accept=accept, invite_id=invite_id, invite_code=invite_code
        )

    async def cancel_pending_admin(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Cancel a pending admin invite - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.members.cancel_pending_admin(network_id)

    async def promote_member(
        self, member_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Promote a member to admin - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.members.promote_member(network_id, member_id)

    async def remove_admin(self, user_id: str, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Remove an admin - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.members.remove_admin(network_id, user_id)

    async def query_invite(self, invite_code: str) -> Dict[str, Any]:
        """Look up an invite by code - returns raw Eero API response (unverified)."""
        return await self._api.members.query_invite(invite_code)

    # ==================== Account Profile ====================

    async def set_account_name(self, name: str) -> Dict[str, Any]:
        """Set the account name - returns raw Eero API response (unverified write)."""
        response = await self._api.account.set_name(name)
        self._cache["account"] = {"data": None, "timestamp": 0}
        return response

    async def set_account_email(self, email: str) -> Dict[str, Any]:
        """Start an account e-mail change - returns raw Eero API response (unverified write)."""
        return await self._api.account.set_email(email)

    async def verify_account_email(self, code: str) -> Dict[str, Any]:
        """Verify an account e-mail change - returns raw Eero API response (unverified write)."""
        response = await self._api.account.verify_email(code)
        self._cache["account"] = {"data": None, "timestamp": 0}
        return response

    async def set_account_phone(self, phone: str) -> Dict[str, Any]:
        """Start an account phone change - returns raw Eero API response (unverified write)."""
        return await self._api.account.set_phone(phone)

    async def verify_account_phone(self, code: str) -> Dict[str, Any]:
        """Verify an account phone change - returns raw Eero API response (unverified write)."""
        response = await self._api.account.verify_phone(code)
        self._cache["account"] = {"data": None, "timestamp": 0}
        return response

    async def set_account_consents(self, *, marketing_emails: bool) -> Dict[str, Any]:
        """Set account consents - returns raw Eero API response (unverified write)."""
        response = await self._api.account.set_consents(marketing_emails=marketing_emails)
        self._cache["account"] = {"data": None, "timestamp": 0}
        return response

    async def get_sms_countries(self) -> Dict[str, Any]:
        """Get the SMS country list - returns raw Eero API response."""
        return await self._api.account.get_sms_countries()

    # ==================== DHCP, Connection Mode & NAT ====================

    async def set_dhcp(
        self,
        network_id: Optional[str] = None,
        *,
        mode: Optional[str] = None,
        custom: Optional[Mapping[str, Any]] = None,
        custom_v2: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set DHCP configuration - returns raw Eero API response.

        Unverified settings-class write that may reboot the entire mesh; read
        the network first and skip when unchanged; never retry.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dhcp.set_dhcp(
            network_id,
            mode=mode,
            custom=custom,
            custom_v2=custom_v2,
            **self._network_parent_kwargs(network_id),
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_connection_mode(
        self, mode: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set the WAN connection mode - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dhcp.set_connection_mode(
            network_id, mode, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_nat_port_randomization(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set NAT port randomisation - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.dhcp.set_nat_port_randomization(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_pppoe(
        self, eero_serial_or_id: str, *, username: str, password: str
    ) -> Dict[str, Any]:
        """Set PPPoE credentials on an eero - returns raw Eero API response (unverified write)."""
        return await self._api.dhcp.set_pppoe(
            eero_serial_or_id, username=username, password=password
        )

    # ==================== WPA3 per band, MLO, Fast Transition, Passpoint ====================

    async def get_wpa3_per_band(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get WPA3 mode per band - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.wpa3.get_wpa3_per_band(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_wpa3_per_band(
        self,
        network_id: Optional[str] = None,
        *,
        band_2_4_ghz: Optional[str] = None,
        band_5_ghz: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Set WPA3 mode per band - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.wpa3.set_wpa3_per_band(
            network_id,
            band_2_4_ghz=band_2_4_ghz,
            band_5_ghz=band_5_ghz,
            **self._network_parent_kwargs(network_id),
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_mlo_mode(self, mode: str, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Set multi-link operation mode - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.security.set_mlo_mode(
            network_id, mode, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def get_fast_transition(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the fast-transition setting - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.security.get_fast_transition(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_fast_transition(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set fast transition - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.security.set_fast_transition(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_passpoint_enabled(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable or disable Passpoint - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.security.set_passpoint_enabled(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def set_proxied_nodes(
        self, enabled: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable or disable proxied nodes - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.security.set_proxied_nodes(
            network_id, enabled, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    # ==================== Power Saving ====================

    async def set_power_saving(
        self,
        network_id: Optional[str] = None,
        *,
        enable: Optional[bool] = None,
        power_saving_schedule_enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Set power saving - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.power_saving.set_power_saving(
            network_id,
            enable=enable,
            power_saving_schedule_enabled=power_saving_schedule_enabled,
            **self._network_parent_kwargs(network_id),
        )
        self._invalidate_network_cache(network_id)
        return response

    async def get_power_saving_schedules(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get power-saving schedules - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.power_saving.get_schedules(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def create_power_saving_schedule(
        self,
        network_id: Optional[str] = None,
        *,
        name: str,
        days: Any,
        start_time: str,
        end_time: str,
        enabled: bool = True,
    ) -> Dict[str, Any]:
        """Create a power-saving schedule - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.power_saving.create_schedule(
            network_id,
            name=name,
            days=days,
            start_time=start_time,
            end_time=end_time,
            enabled=enabled,
        )

    async def update_power_saving_schedule(
        self,
        schedule_id: str,
        network_id: Optional[str] = None,
        *,
        name: Optional[str] = None,
        days: Optional[Any] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Update a power-saving schedule - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.power_saving.update_schedule(
            network_id,
            schedule_id,
            name=name,
            days=days,
            start_time=start_time,
            end_time=end_time,
            enabled=enabled,
        )

    async def delete_power_saving_schedule(
        self, schedule_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a power-saving schedule - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.power_saving.delete_schedule(network_id, schedule_id)

    # ==================== Dynamic DNS ====================

    async def enable_ddns(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Enable dynamic DNS - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.ddns.enable(
            network_id, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    async def disable_ddns(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Disable dynamic DNS - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.ddns.disable(
            network_id, **self._network_parent_kwargs(network_id)
        )
        self._invalidate_network_cache(network_id)
        return response

    # ==================== Backup Access Points ====================

    async def list_backup_access_points(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """List Wi-Fi backup access points - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup_access_points.list(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def add_backup_access_point(
        self,
        network_id: Optional[str] = None,
        *,
        ssid: str,
        password: str,
        uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a backup access point - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup_access_points.add(
            network_id, ssid=ssid, password=password, uuid=uuid
        )

    async def update_backup_access_point(
        self,
        backup_network_id: str,
        network_id: Optional[str] = None,
        *,
        ssid: Optional[str] = None,
        password: Optional[str] = None,
        enabled: Optional[bool] = None,
        uuid: Optional[str] = None,
        connectivity: Optional[Mapping[str, Any]] = None,
        created: Optional[str] = None,
        last_updated_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a backup access point - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup_access_points.update(
            network_id,
            backup_network_id,
            ssid=ssid,
            password=password,
            enabled=enabled,
            uuid=uuid,
            connectivity=connectivity,
            created=created,
            last_updated_at=last_updated_at,
        )

    async def delete_backup_access_point(
        self, backup_network_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a backup access point - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup_access_points.delete_backup_access_point(
            network_id, backup_network_id
        )

    async def rearrange_backup_access_points(
        self, order: List[str], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Reorder backup access points - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup_access_points.rearrange(network_id, order)

    async def discover_backup_ssids(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get discovered backup SSIDs - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup_access_points.discover_ssids(network_id)

    async def start_backup_ssid_discovery(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Start backup SSID discovery - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup_access_points.start_ssid_discovery(network_id)

    async def backup_connectivity_check(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Run a backup connectivity check - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.backup_access_points.connectivity_check(network_id)

    # ==================== Subnets ====================

    async def get_subnets_config(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the subnets configuration - returns raw Eero API response (verified read)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.subnets.get_config(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_subnets_config(
        self, config: Mapping[str, Any], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set the subnets configuration - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.subnets.set_config(network_id, config)
        self._invalidate_network_cache(network_id)
        return response

    async def delete_subnet(
        self, subnet_type: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Delete a subnet - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.subnets.delete_subnet(network_id, subnet_type)
        self._invalidate_network_cache(network_id)
        return response

    async def set_subnet_content_filters(
        self, filters: Mapping[str, Any], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set subnet content filters - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.subnets.set_content_filters(network_id, filters)

    async def get_subnet_content_filters(
        self, subnet_id: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a subnet's content filters - returns raw Eero API response."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.subnets.get_content_filters(network_id, subnet_id)

    # ==================== Multi-static IP & Secondary WAN ====================

    async def get_multistaticip(self, network_id: Optional[str] = None) -> Dict[str, Any]:
        """Get the multi-static-IP configuration - returns raw Eero API response.

        The API answers 404 with ``error.network.multistaticip_not_found`` on
        a network without the feature.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        return await self._api.wan.get_multistaticip(
            network_id, **self._network_parent_kwargs(network_id)
        )

    async def set_multistaticip(
        self, config: Mapping[str, Any], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set the multi-static-IP configuration - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.wan.set_multistaticip(network_id, config)
        self._invalidate_network_cache(network_id)
        return response

    async def set_secondary_wan_config(
        self, config: Mapping[str, Any], network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Set the secondary WAN configuration - raw response (unverified; may reboot the mesh)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.wan.set_secondary_wan_config(network_id, config)
        self._invalidate_network_cache(network_id)
        return response

    async def set_device_secondary_wan_access(
        self, mac: str, *, deny: bool, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Allow or deny a device's secondary WAN access - raw response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.wan.set_device_secondary_wan_access(network_id, mac, deny=deny)
        self._invalidate_device_cache(network_id, mac)
        return response

    # ==================== Eero Node & Port Actions ====================

    async def node_action(
        self, eero_id: str, action: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run a node action (port power cycle, optionally with reboot) - raw response.

        Unverified write; the reboot variant restarts the node.
        """
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.eeros.node_action(
            eero_id, action, **self._eero_parent_kwargs(network_id, eero_id)
        )
        self._invalidate_eeros_cache(network_id)
        return response

    async def port_action(
        self, eero_id: str, interface_number: str, action: str, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Run a port action on an eero - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.eeros.port_action(eero_id, interface_number, action)
        self._invalidate_eeros_cache(network_id)
        return response

    async def led_cycle(
        self, eero_serial: str, *, colors: Any, duration: str, time_per_color: str
    ) -> Dict[str, Any]:
        """Cycle an eero's LED colours - returns raw Eero API response (unverified write)."""
        return await self._api.eeros.led_cycle(
            eero_serial, colors=colors, duration=duration, time_per_color=time_per_color
        )

    async def nightlight_override(
        self, eero_id: str, *, brightness_percentage: int, network_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Override the nightlight brightness - returns raw Eero API response (unverified write)."""
        network_id = await self._ensure_network_id(network_id, auto_discover=False)
        response = await self._api.eeros.nightlight_override(
            eero_id, brightness_percentage=brightness_percentage
        )
        self._invalidate_eeros_cache(network_id)
        return response

    async def get_eero_support(self, eero_serial: str) -> Dict[str, Any]:
        """Get an eero's support record - returns raw Eero API response (404 on some nodes)."""
        return await self._api.eeros.get_eero_support(eero_serial)
