"""SQM/QoS API for Eero (Smart Queue Management).

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

SQM is a single boolean toggle on the network's ``settings`` resource,
written as a query parameter with no body -- there is no API counterpart for
per-direction bandwidth limits or an explicit "auto" mode.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import Envelope, resource_url, self_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)


def _network_own_url(network_id: str, parent: Optional[Envelope]) -> str:
    """Resolve a network's own URL, preferring its parent envelope's ``url``."""
    if parent is not None:
        own = self_url(parent)
        if own is not None:
            return own
    return resource_url(network_id, "networks/{id}")


class SqmAPI(AuthenticatedAPI):
    """SQM/QoS API for Eero.

    Manages the Smart Queue Management (SQM) on/off toggle.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the SqmAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_sqm_settings(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get SQM/QoS settings for a network - returns raw Eero API response.

        SQM settings are included in the network data, under the ``sqm``
        field.

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

        _LOGGER.debug("Getting SQM settings for network %s", network_id)
        return await self.get(
            _network_own_url(network_id, as_envelope(parent)), auth_token=auth_token
        )

    async def set_sqm(
        self, network_id: str, enabled: bool, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enable or disable SQM (Smart Queue Management) - returns raw Eero API response.

        Issues a PUT with no request body to the network's ``settings``
        link, carrying the new value as the ``sqm`` query parameter
        (``true``/``false``).

        .. warning::
            This is a settings-class write: it has not been confirmed
            against a live network, and -- like other writes to this
            endpoint -- may trigger a mesh reboot. Follow the
            read-compare-skip discipline: read `get_sqm_settings` first, and
            only issue this write when the stored value differs from the
            desired one. Never retry on failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable SQM, False to disable.
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
        warn_uncharacterised_write(_LOGGER, "set SQM for network")
        return await self.put(
            url,
            auth_token=auth_token,
            params={"sqm": "true" if enabled else "false"},
        )
