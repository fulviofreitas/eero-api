"""Burst Reporters API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
import warnings
from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI, RequestEncoding
from .links import sub_resource_url

_LOGGER = logging.getLogger(__name__)


class BurstReportersAPI(AuthenticatedAPI):
    """Burst Reporters API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BurstReportersAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def create_burst_reporter(
        self,
        network_id: str,
        reporter_data: Optional[Dict[str, Any]] = None,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Request a live-usage burst for a network - returns raw Eero API response.

        POSTs the two-character body ``""`` to the network's
        ``burst_reporters`` link. The observed response shape is
        ``{"meta": ..., "data": {"next_burst": "<timestamp string>"}}``.

        The observed effect is that, after a short settle (about 12
        seconds), the device list's ``usage.down_mbps`` and
        ``usage.up_mbps`` values are refreshed, whereas before the POST
        they are zero or stale. This does not run a speed test and does
        not change any setting. At most one burst may be requested per
        minute per network.

        .. note::
            Live-verified 2026-10-20: one POST returned 200 with
            ``data.next_burst``; 12 seconds later 103 of 116 connected
            devices carried non-zero ``usage`` values (all were zero before),
            the values had largely decayed again by 30 seconds, no WAN-level
            usage field appeared on the network envelope, and no node's
            reboot marker moved in the following five minutes. Read the
            device list about 12 seconds after the POST, not later. Never
            retry it in a loop. The check covered the ``""`` body only: a
            deprecated non-empty ``reporter_data`` body remains
            uncharacterised and still logs the warning.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            reporter_data: Deprecated, removed in 9.0.0. The API operation
                takes no body. When supplied, a non-empty value is still
                forwarded unchanged as the JSON body; an empty value is
                ignored.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``burst_reporters`` link
                is used instead of the default template. Read only; never
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

        if reporter_data is not None:
            warnings.warn(
                "The reporter_data parameter of create_burst_reporter is deprecated and "
                "will be removed in 9.0.0; the API operation takes no body.",
                DeprecationWarning,
                stacklevel=2,
            )

        url = sub_resource_url(
            network_id,
            "networks/{id}/burst_reporters",
            link="burst_reporters",
            parent=as_envelope(parent),
        )
        _LOGGER.debug("Requesting live-usage burst for network %s", network_id)
        if reporter_data:
            warn_uncharacterised_write(
                _LOGGER, "request live-usage burst with a deprecated body for network"
            )
            return await self.post(url, auth_token=auth_token, json=reporter_data)
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )
