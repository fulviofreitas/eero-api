"""Diagnostics API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import sub_resource_url

_LOGGER = get_secure_logger(__name__)


class DiagnosticsAPI(AuthenticatedAPI):
    """Diagnostics API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DiagnosticsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_diagnostics(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get network diagnostics results - returns raw Eero API response.

        GETs the network's ``diagnostics`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``diagnostics`` link is
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
            "networks/{id}/diagnostics",
            link="diagnostics",
            parent=as_envelope(parent),
        )
        _LOGGER.debug("Getting diagnostics for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def run_diagnostics(
        self,
        network_id: str,
        *,
        device: Optional[str] = None,
        symptom: Optional[str] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run network diagnostics - returns raw Eero API response.

        Issues a JSON POST to the network's ``diagnostics`` link with
        exactly the keys given among ``device`` and ``symptom`` (an empty
        JSON object when neither is supplied). Results are read back via
        `get_diagnostics` on the same link.

        .. warning::
            The request body shape has not been confirmed against a live
            network. Follow the read-compare-skip discipline where
            applicable, and do not retry on failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            device: Optional device identifier to scope the diagnostics run
                to. Omitted from the request body when ``None``.
            symptom: Optional symptom identifier describing the issue being
                diagnosed. Omitted from the request body when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``diagnostics`` link is
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
            "networks/{id}/diagnostics",
            link="diagnostics",
            parent=as_envelope(parent),
        )
        payload: Dict[str, str] = {}
        if device is not None:
            payload["device"] = device
        if symptom is not None:
            payload["symptom"] = symptom

        warn_uncharacterised_write(_LOGGER, f"run diagnostics for network {network_id}")
        return await self.post(url, auth_token=auth_token, json=payload)
