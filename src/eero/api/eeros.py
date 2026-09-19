"""Eero devices API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

URL resolution goes exclusively through ``eero.api.links``: a bare eero ID, an
API-returned path, or an absolute API-host URL are all accepted wherever an
``eero_id`` parameter is documented, and every method accepts an optional
keyword-only ``parent`` -- the caller's own cached eero envelope -- so the
link the API published on it is used instead of a locally-built template.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import (
    EeroAuthenticationException,
    EeroFeatureUnavailableException,
    EeroValidationException,
)
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI, RequestEncoding
from .links import Envelope, join_api_path, resource_url, self_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Valid range for both LED and nightlight brightness percentages.
_BRIGHTNESS_MIN = 0
_BRIGHTNESS_MAX = 100

#: Valid values for `node_action`'s ``action`` field.
_NODE_ACTIONS = frozenset({"POWER_CYCLE_ALL_PORTS", "POWER_CYCLE_ALL_PORTS_AND_REBOOT"})

#: Valid values for `port_action`'s ``action`` field.
_PORT_ACTIONS = frozenset(
    {
        "ENABLE_DATA",
        "DISABLE_DATA",
        "ENABLE_POE",
        "DISABLE_POE",
        "ENABLE_PORT",
        "DISABLE_PORT",
        "RESTART_POWER",
        "ENABLE_PORT_SECURITY",
        "DISABLE_PORT_SECURITY",
    }
)

#: Template for a single eero port's action sub-resource.
_PORT_ACTION_TEMPLATE = "eeros/{{id}}/ports/{interface_number}/action"


def _eero_own_url(eero_id: str, parent: Optional[Envelope]) -> str:
    """Resolve an eero's own URL, preferring its parent envelope's ``url``.

    Args:
        eero_id: A bare eero ID, API-returned path, or absolute URL.
        parent: The eero's own cached envelope (full or ``data``), if the
            caller has one. Read only; never mutated.

    Returns:
        The absolute URL of the eero resource itself.
    """
    if parent is not None:
        own = self_url(parent)
        if own is not None:
            return own
    return resource_url(eero_id, "eeros/{id}")


def _nightlight_url_from_envelope(envelope: Optional[Envelope]) -> Optional[str]:
    """Read the nightlight sub-resource URL out of an eero envelope, if present.

    The nightlight is not exposed through the generic ``resources`` link
    object every other sub-resource uses -- its URL lives at
    ``data.nightlight.url`` (or ``nightlight.url`` on an already-unwrapped
    ``data`` object). This function only reads that field; it never mutates
    ``envelope``.

    Args:
        envelope: A full response envelope or its unwrapped ``data`` object,
            or ``None``.

    Returns:
        The absolute nightlight URL, or ``None`` when ``envelope`` is
        ``None`` or carries no ``nightlight.url`` field.
    """
    if not isinstance(envelope, dict):
        return None
    data = (
        envelope["data"]
        if "meta" in envelope and isinstance(envelope.get("data"), dict)
        else envelope
    )
    if not isinstance(data, dict):
        return None
    nightlight = data.get("nightlight")
    if not isinstance(nightlight, dict):
        return None
    url = nightlight.get("url")
    if not isinstance(url, str) or not url:
        return None
    return join_api_path(url)


def _validate_brightness(brightness: int, field: str) -> int:
    """Validate a brightness percentage is an int in [0, 100].

    Args:
        brightness: Candidate brightness value.
        field: Field name used in any raised validation error.

    Returns:
        ``brightness`` unchanged.

    Raises:
        EeroValidationException: If ``brightness`` is not an int in range.
    """
    if isinstance(brightness, bool) or not isinstance(brightness, int):
        raise EeroValidationException(field, "must be an integer between 0 and 100")
    if not (_BRIGHTNESS_MIN <= brightness <= _BRIGHTNESS_MAX):
        raise EeroValidationException(field, "must be an integer between 0 and 100")
    return brightness


class EerosAPI(AuthenticatedAPI):
    """Eero devices API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the EerosAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def _resolve_nightlight_url(
        self,
        eero_id: str,
        auth_token: str,
        parent: Optional[Envelope],
    ) -> str:
        """Resolve the nightlight sub-resource URL, reading the eero once if needed.

        Args:
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            auth_token: A valid session token, already resolved by the caller.
            parent: The eero's own cached envelope, if the caller has one.

        Returns:
            The absolute nightlight URL.

        Raises:
            EeroFeatureUnavailableException: If the eero (whether read from
                ``parent`` or fetched fresh) carries no nightlight URL.
        """
        url = _nightlight_url_from_envelope(parent)
        if url is None:
            envelope = await self.get(_eero_own_url(eero_id, None), auth_token=auth_token)
            url = _nightlight_url_from_envelope(envelope)
        if url is None:
            raise EeroFeatureUnavailableException("nightlight", "not available on this eero")
        return url

    async def get_eeros(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get list of Eero devices - returns raw Eero API response.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, the network's published ``eeros`` link is
                used instead of the default template. Read only; never
                mutated.

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
            network_id, "networks/{id}/eeros", link="eeros", parent=as_envelope(parent)
        )
        _LOGGER.debug("Getting eeros for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def get_eero(
        self,
        network_id: str,
        eero_id: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get information about a specific Eero device - returns raw Eero API response.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            parent: The eero's own cached envelope, if the caller has one;
                when supplied, its own ``url`` is used instead of the default
                template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting eero %s", eero_id)
        return await self.get(_eero_own_url(eero_id, as_envelope(parent)), auth_token=auth_token)

    async def reboot_eero(
        self,
        network_id: str,
        eero_id: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Reboot an Eero device - returns raw Eero API response.

        Issues a POST with the two-character body ``""`` -- the shape the
        API accepts for this parameterless operation -- to the eero's
        ``reboot`` link.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            parent: The eero's own cached envelope, if the caller has one;
                when supplied, its published ``reboot`` link is used instead
                of the default template. Read only; never mutated.

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
            eero_id, "eeros/{id}/reboot", link="reboot", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(_LOGGER, f"reboot eero {eero_id}")
        _LOGGER.debug("Rebooting eero %s", eero_id)
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )

    async def get_led_status(
        self,
        network_id: str,
        eero_id: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get LED status for an Eero device - returns raw Eero API response.

        The raw response includes led_on and led_brightness in the data field.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            parent: The eero's own cached envelope, if the caller has one.
                Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting LED status for eero %s", eero_id)
        return await self.get(_eero_own_url(eero_id, as_envelope(parent)), auth_token=auth_token)

    async def set_led(
        self,
        network_id: str,
        eero_id: str,
        enabled: bool,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set LED on/off for an Eero device - returns raw Eero API response.

        Issues a form-encoded PUT (``led_on=true``/``led_on=false``) to the
        eero's ``led_action`` link.

        .. warning::
            A JSON write to the eero's own URL (``{"led_on": bool}``) was
            live-verified to change nothing. This form-encoded write to the
            dedicated ``led_action`` link is the shape the API declares for
            this operation, but a live check did not observe the node's
            light change state -- its side effects are unconfirmed.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            enabled: True to turn LED on, False to turn off.
            parent: The eero's own cached envelope, if the caller has one;
                when supplied, its published ``led_action`` link is used
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
            eero_id, "eeros/{id}/led", link="led_action", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(_LOGGER, f"set LED for eero {eero_id}")
        return await self.put(
            url,
            auth_token=auth_token,
            data={"led_on": "true" if enabled else "false"},
        )

    async def set_led_brightness(
        self,
        network_id: str,
        eero_id: str,
        brightness: int,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set LED brightness for an Eero device - returns raw Eero API response.

        Issues a form-encoded PUT (``led_brightness=<decimal string>``) to
        the eero's ``led_action`` link.

        .. warning::
            This write has not been confirmed against a live network to
            change the node's light. Follow the read-compare-skip
            discipline: read `get_led_status` first, and only issue this
            write when the stored value differs from the desired one.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            brightness: Brightness level, an integer in [0, 100].
            parent: The eero's own cached envelope, if the caller has one;
                when supplied, its published ``led_action`` link is used
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``brightness`` is not an integer in [0, 100]
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        brightness = _validate_brightness(brightness, "brightness")

        url = sub_resource_url(
            eero_id, "eeros/{id}/led", link="led_action", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(_LOGGER, f"set LED brightness for eero {eero_id}")
        return await self.put(
            url,
            auth_token=auth_token,
            data={"led_brightness": str(brightness)},
        )

    async def set_location(
        self,
        network_id: str,
        eero_id: str,
        location: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set the descriptive location label for an Eero device - returns raw Eero API response.

        Issues a form-encoded PUT (``location=<value>``) to the eero's own
        URL.

        .. warning::
            This write has not been confirmed against a live network.
            Follow the read-compare-skip discipline: read `get_eero` first,
            and only issue this write when the stored location differs from
            the desired one.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            location: The new location label, e.g. ``"Living Room"``.
            parent: The eero's own cached envelope, if the caller has one;
                when supplied, its own ``url`` is used instead of the
                default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = _eero_own_url(eero_id, as_envelope(parent))
        warn_uncharacterised_write(_LOGGER, f"set location for eero {eero_id}")
        return await self.put(url, auth_token=auth_token, data={"location": location})

    async def get_nightlight(
        self,
        network_id: str,
        eero_id: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get nightlight settings for an Eero Beacon device - returns raw Eero API response.

        Note: Nightlight is only available on Eero Beacon devices. The
        nightlight is a sub-resource whose URL lives at
        ``data.nightlight.url`` on the eero envelope; when ``parent``
        carries that URL it is used directly, otherwise the eero is read
        once to discover it.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            parent: The eero's own cached envelope, if the caller has one.
                Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroFeatureUnavailableException: If this eero has no nightlight
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = await self._resolve_nightlight_url(eero_id, auth_token, as_envelope(parent))
        _LOGGER.debug("Getting nightlight settings for eero %s", eero_id)
        return await self.get(url, auth_token=auth_token)

    async def set_nightlight(
        self,
        network_id: str,
        eero_id: str,
        *,
        enabled: Optional[bool] = None,
        brightness_percentage: Optional[int] = None,
        schedule: Optional[Mapping[str, Any]] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set nightlight settings for an Eero Beacon device - returns raw Eero API response.

        Issues a JSON PUT to the nightlight sub-resource with exactly the
        fields supplied among ``enabled``, ``brightness_percentage``, and
        ``schedule`` -- the only fields the API's nightlight object accepts.
        ``schedule`` is forwarded exactly as given, with no interpretation
        of its shape.

        .. warning::
            This write has not been confirmed against a live network.
            Follow the read-compare-skip discipline: read `get_nightlight`
            first, and only issue this write when the stored settings
            differ from the desired ones.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            enabled: True to enable the nightlight, False to disable. Omitted
                from the request when ``None``.
            brightness_percentage: Brightness level, an integer in [0, 100].
                Omitted from the request when ``None``.
            schedule: The nightlight schedule object, forwarded to the API
                unchanged. Omitted from the request when ``None``.
            parent: The eero's own cached envelope, if the caller has one;
                used to discover the nightlight URL without an extra read.
                Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If no field is supplied, or
                ``brightness_percentage`` is not an integer in [0, 100]
            EeroFeatureUnavailableException: If this eero has no nightlight
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {}
        if enabled is not None:
            payload["enabled"] = enabled
        if brightness_percentage is not None:
            payload["brightness_percentage"] = _validate_brightness(
                brightness_percentage, "brightness_percentage"
            )
        if schedule is not None:
            payload["schedule"] = schedule

        if not payload:
            raise EeroValidationException(
                "nightlight",
                "at least one of enabled, brightness_percentage, schedule must be supplied",
            )

        url = await self._resolve_nightlight_url(eero_id, auth_token, as_envelope(parent))
        warn_uncharacterised_write(_LOGGER, f"set nightlight for eero {eero_id}")
        return await self.put(url, auth_token=auth_token, json=payload)

    async def set_nightlight_brightness(
        self,
        network_id: str,
        eero_id: str,
        brightness_percentage: int,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set nightlight brightness for an Eero Beacon device - returns raw Eero API response.

        Convenience wrapper around `set_nightlight` for just the brightness
        field.

        Args:
            network_id: ID of the network the Eero belongs to
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            brightness_percentage: Brightness level, an integer in [0, 100].
            parent: The eero's own cached envelope, if the caller has one.
                Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        return await self.set_nightlight(
            network_id,
            eero_id,
            brightness_percentage=brightness_percentage,
            parent=parent,
        )

    async def set_nightlight_schedule(
        self,
        network_id: str,
        eero_id: str,
        schedule: Mapping[str, Any],
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set nightlight schedule for an Eero Beacon device - returns raw Eero API response.

        Convenience wrapper around `set_nightlight` for just the schedule
        field. ``schedule`` is forwarded to the API unchanged.

        Args:
            network_id: ID of the network the Eero belongs to
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            schedule: The nightlight schedule object, forwarded unchanged.
            parent: The eero's own cached envelope, if the caller has one.
                Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}
        """
        return await self.set_nightlight(network_id, eero_id, schedule=schedule, parent=parent)

    async def get_connections(
        self,
        network_id: str,
        eero_id: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get an Eero device's client connections - returns raw Eero API response.

        GETs the eero's ``connections`` link.

        Args:
            network_id: ID of the network the Eero belongs to (unused, kept for API compatibility)
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            parent: The eero's own cached envelope, if the caller has one;
                when supplied, its published ``connections`` link is used
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
            eero_id, "eeros/{id}/connections", link="connections", parent=as_envelope(parent)
        )
        _LOGGER.debug("Getting connections for eero %s", eero_id)
        return await self.get(url, auth_token=auth_token)

    async def node_action(
        self,
        eero_id: str,
        action: str,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Perform a node-level power action on an Eero device - returns raw Eero API response.

        Issues a JSON POST to the eero's ``action`` sub-resource with
        ``{"action": ...}``.

        .. warning::
            ``POWER_CYCLE_ALL_PORTS_AND_REBOOT`` reboots the eero; both
            actions power-cycle its ports, dropping wired clients while they
            renegotiate. Neither action's full effects have been confirmed
            against a live network. Never retry a failed write in a loop.

        Args:
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            action: ``"POWER_CYCLE_ALL_PORTS"`` or
                ``"POWER_CYCLE_ALL_PORTS_AND_REBOOT"``.
            parent: The eero's own cached envelope, if the caller has one;
                when supplied, its published ``action`` link is used
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``action`` is not a declared node
                action
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        if not isinstance(action, str) or action not in _NODE_ACTIONS:
            raise EeroValidationException(
                "action", f"must be one of {sorted(_NODE_ACTIONS)}, got {action!r}"
            )

        url = sub_resource_url(
            eero_id, "eeros/{id}/action", link="action", parent=as_envelope(parent)
        )
        warn_uncharacterised_write(
            _LOGGER,
            f"perform node action {action!r} on eero {eero_id} "
            "-- power-cycles ports and, for POWER_CYCLE_ALL_PORTS_AND_REBOOT, reboots the eero",
        )
        return await self.post(url, auth_token=auth_token, json={"action": action})

    async def port_action(
        self,
        eero_id: str,
        interface_number: str,
        action: str,
    ) -> Dict[str, Any]:
        """Perform a port-level action on an Eero device - returns raw Eero API response.

        Issues a JSON POST to the eero's ``ports/{interface_number}/action``
        sub-resource with ``{"action": ...}``.

        .. warning::
            This write has not been confirmed against a live network, and
            several of the declared actions (disabling data/PoE/the port
            itself, or ``RESTART_POWER``) are inherently disruptive to
            whatever is connected to that port. Never retry a failed write
            in a loop.

        Args:
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            interface_number: The port's interface number, as returned by
                the eero's own port listing.
            action: One of ``"ENABLE_DATA"``, ``"DISABLE_DATA"``,
                ``"ENABLE_POE"``, ``"DISABLE_POE"``, ``"ENABLE_PORT"``,
                ``"DISABLE_PORT"``, ``"RESTART_POWER"``,
                ``"ENABLE_PORT_SECURITY"``, ``"DISABLE_PORT_SECURITY"``.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``action`` is not a declared port
                action
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        if not isinstance(action, str) or action not in _PORT_ACTIONS:
            raise EeroValidationException(
                "action", f"must be one of {sorted(_PORT_ACTIONS)}, got {action!r}"
            )

        url = resource_url(eero_id, _PORT_ACTION_TEMPLATE.format(interface_number=interface_number))
        warn_uncharacterised_write(
            _LOGGER,
            f"perform port action {action!r} on eero {eero_id} port {interface_number}",
        )
        return await self.post(url, auth_token=auth_token, json={"action": action})

    async def led_cycle(
        self,
        eero_serial: str,
        *,
        colors: Any,
        duration: str,
        time_per_color: str,
    ) -> Dict[str, Any]:
        """Cycle an Eero device's LED through a sequence of colors - returns raw Eero API response.

        Issues a form-encoded POST (``colors[]=...``, ``duration=...``,
        ``time_per_color=...``) to the eero's ``led_cycle`` sub-resource.

        .. warning::
            This write has not been confirmed against a live network to
            change the node's light. Never retry a failed write in a loop.

        Args:
            eero_serial: A bare eero serial/ID, API-returned path, or
                absolute URL.
            colors: The color sequence to cycle through, sent as repeated
                ``colors[]`` form fields.
            duration: The total cycle duration, forwarded to the API
                unchanged.
            time_per_color: The time spent on each color, forwarded to the
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

        url = resource_url(eero_serial, "eeros/{id}/led_cycle")
        warn_uncharacterised_write(_LOGGER, f"cycle LED for eero {eero_serial}")
        return await self.post(
            url,
            auth_token=auth_token,
            data={
                "colors[]": colors,
                "duration": duration,
                "time_per_color": time_per_color,
            },
        )

    async def nightlight_override(
        self,
        eero_id: str,
        *,
        brightness_percentage: int,
    ) -> Dict[str, Any]:
        """Preview a nightlight brightness override on an Eero Beacon - returns raw Eero API response.

        Issues a form-encoded POST (``brightness_percentage=<decimal
        string>``) to the eero's ``nightlight/override`` sub-resource.

        .. warning::
            This write has not been confirmed against a live network to
            change the node's light. Never retry a failed write in a loop.

        Args:
            eero_id: A bare eero ID, API-returned path, or absolute URL.
            brightness_percentage: Brightness level, an integer in [0, 100].

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``brightness_percentage`` is not an
                integer in [0, 100]
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        brightness_percentage = _validate_brightness(brightness_percentage, "brightness_percentage")

        url = resource_url(eero_id, "eeros/{id}/nightlight/override")
        warn_uncharacterised_write(_LOGGER, f"override nightlight preview for eero {eero_id}")
        return await self.post(
            url,
            auth_token=auth_token,
            data={"brightness_percentage": str(brightness_percentage)},
        )

    async def get_eero_support(self, eero_serial: str) -> Dict[str, Any]:
        """Get support diagnostics for an Eero device - returns raw Eero API response.

        GETs the eero's ``support`` sub-resource.

        Note: this endpoint has been observed to return HTTP 404 on at
        least one live node, so its availability may be model- or
        state-dependent.

        Args:
            eero_serial: A bare eero serial/ID, API-returned path, or
                absolute URL.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroNotFoundException: If this eero has no support diagnostics
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(eero_serial, "eeros/{id}/support")
        _LOGGER.debug("Getting support diagnostics for eero %s", eero_serial)
        return await self.get(url, auth_token=auth_token)
