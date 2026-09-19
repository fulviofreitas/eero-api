"""Per-band WPA3 settings API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Valid values for each band's WPA3 mode.
WPA3_MODE_WPA2 = "WPA2"
WPA3_MODE_WPA2_WPA3 = "WPA2_WPA3"
WPA3_MODE_WPA3 = "WPA3"
_WPA3_MODES = frozenset({WPA3_MODE_WPA2, WPA3_MODE_WPA2_WPA3, WPA3_MODE_WPA3})


def _validate_mode(value: str, field: str) -> str:
    """Validate a WPA3-per-band mode value.

    Args:
        value: The candidate mode.
        field: Field name used in any raised validation error.

    Returns:
        ``value`` unchanged.

    Raises:
        EeroValidationException: If ``value`` is not a declared mode.
    """
    if not isinstance(value, str) or value not in _WPA3_MODES:
        raise EeroValidationException(field, f"must be one of {sorted(_WPA3_MODES)}, got {value!r}")
    return value


class Wpa3API(AuthenticatedAPI):
    """Per-band WPA3 settings API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the Wpa3API.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_wpa3_per_band(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get the per-band WPA3 mode - returns raw Eero API response.

        GETs the network's ``wpa3_per_band`` sub-resource. This is a
        verified read.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``wpa3_per_band`` link is
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
            "networks/{id}/wpa3_per_band",
            link="wpa3_per_band",
            parent=as_envelope(parent),
        )
        _LOGGER.debug("Getting per-band WPA3 mode for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def set_wpa3_per_band(
        self,
        network_id: str,
        *,
        band_2_4_ghz: Optional[str] = None,
        band_5_ghz: Optional[str] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set the per-band WPA3 mode - returns raw Eero API response.

        Issues a JSON PUT to the network's ``wpa3_per_band`` sub-resource
        with exactly the bands supplied. Each value must be one of
        ``"WPA2"``, ``"WPA2_WPA3"``, ``"WPA3"``.

        .. warning::
            This write has not been confirmed against a live network. May
            require devices to reconnect if their negotiated security mode
            is no longer offered. Follow the read-compare-skip discipline:
            read `get_wpa3_per_band` first, and only issue this write when
            the stored mode differs from the desired one. Never retry a
            failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            band_2_4_ghz: The 2.4GHz band's WPA3 mode. Omitted from the
                request when ``None``.
            band_5_ghz: The 5GHz band's WPA3 mode. Omitted from the request
                when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``wpa3_per_band`` link is
                used instead of the default template. Read only; never
                mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If no band is supplied, or a supplied
                value is not a declared WPA3 mode
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {}
        if band_2_4_ghz is not None:
            payload["band_2_4_ghz"] = _validate_mode(band_2_4_ghz, "band_2_4_ghz")
        if band_5_ghz is not None:
            payload["band_5_ghz"] = _validate_mode(band_5_ghz, "band_5_ghz")

        if not payload:
            raise EeroValidationException(
                "wpa3_per_band", "at least one of band_2_4_ghz, band_5_ghz must be supplied"
            )

        url = sub_resource_url(
            network_id,
            "networks/{id}/wpa3_per_band",
            link="wpa3_per_band",
            parent=as_envelope(parent),
        )
        warn_uncharacterised_write(_LOGGER, f"set per-band WPA3 mode for network {network_id}")
        return await self.put(url, auth_token=auth_token, json=payload)
