"""Insights API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.
"""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)

# Valid values for the `cadence` query parameter on GET /insights.
INSIGHTS_CADENCES = ("hourly", "daily", "weekly")


class InsightsAPI(AuthenticatedAPI):
    """Insights API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the InsightsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_insights(
        self,
        network_id: str,
        *,
        start: str,
        end: str,
        insight_type: str,
        cadence: str = "daily",
    ) -> Dict[str, Any]:
        """Query insights time-series data — returns raw Eero API response.

        The Eero cloud API requires four query parameters on this endpoint;
        omitting any of ``start``, ``end``, ``insight_type``, or ``cadence``
        yields a 400 "error.form.errors" response. The SDK forwards the values
        as-is and returns the raw JSON envelope unchanged.

        Response shape (envelope):

        ::

            {
              "meta": {...},
              "data": {
                "network_id": <int>,
                "start": <iso8601>,
                "end": <iso8601>,
                "limit": <iso8601>,
                "series": [
                  {"insight_type": <str>, "sum": <int>, "values": [{"time": ..., "value": ...}, ...]},
                  ...
                ]
              }
            }

        Args:
            network_id: ID of the network to query.
            start: Window start, ISO 8601 timestamp (e.g. ``"2026-07-21T00:00:00Z"``).
            end: Window end, ISO 8601 timestamp.
            insight_type: Category to query. Live-observed valid inputs:
                ``"adblock"``, ``"blocked"``, ``"inspected"``. The server may
                emit additional types (e.g. ``"malware"``, ``"botnet"``) inside
                the response ``series`` array when ``insight_type="blocked"``.
            cadence: Bucket size for the returned series. One of
                ``"hourly"``, ``"daily"``, ``"weekly"``. Defaults to
                ``"daily"``. This is the only parameter with an SDK-supplied
                default — it controls display bucketing, not data scope.

        Returns:
            Raw API response: ``{"meta": {...}, "data": {...}}``.

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error (400 on invalid
                params, 403 on insufficient subscription, etc.).
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        params = {
            "start": start,
            "end": end,
            "cadence": cadence,
            "insight_type": insight_type,
        }
        _LOGGER.debug(
            "Getting insights for network %s: insight_type=%s cadence=%s window=%s..%s",
            network_id,
            insight_type,
            cadence,
            start,
            end,
        )
        return await self.get(
            f"networks/{network_id}/insights",
            auth_token=auth_token,
            params=params,
        )

    async def run_insights(self, network_id: str) -> Dict[str, Any]:
        """Run insights analysis - returns raw Eero API response.

        Args:
            network_id: ID of the network to analyze

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Running insights for network %s", network_id)
        return await self.post(
            f"networks/{network_id}/insights",
            auth_token=auth_token,
            json={},
        )
