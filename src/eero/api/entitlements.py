"""Entitlements API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients. In particular, this module makes no attempt to
interpret premium/subscription status from any of the envelopes it
returns -- that interpretation belongs entirely to the caller.
"""

from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url

_LOGGER = get_secure_logger(__name__)


class EntitlementsAPI(AuthenticatedAPI):
    """Entitlements API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the EntitlementsAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_features(self, network_id: str) -> Dict[str, Any]:
        """Get the network's entitled features -- returns raw Eero API response.

        Operation: GET ``/2.2/entitlements/networks/{id}/features``. The SDK
        returns the entitled-features envelope exactly as the API sends it;
        any premium-status interpretation belongs to the caller.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "entitlements/networks/{id}/features")
        _LOGGER.debug("Getting entitled features for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def get_upsell_features(self, network_id: str) -> Dict[str, Any]:
        """Get the network's upsell features -- returns raw Eero API response.

        Operation: GET ``/2.2/entitlements/networks/{id}/upsell_features``.
        The SDK returns the upsell-features envelope exactly as the API
        sends it; any premium-status interpretation belongs to the caller.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "entitlements/networks/{id}/upsell_features")
        _LOGGER.debug("Getting upsell features for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def get_model_capabilities(self, network_id: str) -> Dict[str, Any]:
        """Get eero model capabilities for a network -- returns raw Eero API response.

        Operation: GET ``/2.2/eero_models/capabilities`` with the query
        parameter ``networkId`` (this exact casing on the wire).

        Args:
            network_id: The network's bare ID. Sent verbatim as the
                ``networkId`` query parameter -- this endpoint has no
                path-scoped variant, so id/path/URL polymorphism does not
                apply here.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting eero model capabilities for network %s", network_id)
        return await self.get(
            "eero_models/capabilities",
            auth_token=auth_token,
            params={"networkId": network_id},
        )

    async def get_premium_customer(self) -> Dict[str, Any]:
        """Get the premium customer record -- returns raw Eero API response.

        Operation: GET ``/2.2/premium/customer``. The SDK returns the
        customer envelope exactly as the API sends it; any premium-status
        interpretation belongs to the caller.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting premium customer record")
        return await self.get("premium/customer", auth_token=auth_token)


__all__ = ["EntitlementsAPI"]
