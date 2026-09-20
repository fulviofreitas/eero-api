"""OUI Check API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

``GET networks/{network_id}/ouicheck`` requires two query parameters, ``serial``
and ``version``, identifying the eero hardware being checked. Omitting either
causes the API to respond 404.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._params import resolve_network_url
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = get_secure_logger(__name__)


class OUICheckAPI(AuthenticatedAPI):
    """OUI Check API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the OUICheckAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_ouicheck(
        self,
        network_id: str,
        *,
        serial: str,
        version: str,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get OUI check results - returns raw Eero API response.

        Args:
            network_id: The network's bare ID, path, or absolute URL.
            serial: Serial number of the eero hardware being checked, as
                found in an eero envelope returned by the API (e.g. from
                `EerosAPI.get_eeros`).
            version: Firmware/hardware version string of the eero hardware
                being checked, as found in the same eero envelope.
            parent: The cached network envelope, if the caller has one.
                Preferred over `network_id` to resolve the base URL when
                supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroValidationException: If ``serial`` or ``version`` is empty or
                non-string.
            EeroAPIException: If the API returns an error.
        """
        if not isinstance(serial, str) or not serial:
            raise EeroValidationException("serial", "must be a non-empty string")
        if not isinstance(version, str) or not version:
            raise EeroValidationException("version", "must be a non-empty string")

        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{resolve_network_url(network_id, parent)}/ouicheck"
        _LOGGER.debug("Getting OUI check for network %s", network_id)
        return await self.get(
            url,
            auth_token=auth_token,
            params={"serial": serial, "version": version},
        )
