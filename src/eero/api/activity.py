"""Activity API for Eero (Eero Plus feature).

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

DEPRECATED: All methods in this module target ``/networks/{id}/activity*``
endpoints that no longer exist on Eero's cloud API. Every call currently
raises ``EeroAPIException`` with a 404. Live-verified against a real account
on both API versions 2.2 and 2.3, and against the network's own resource
map (which lists ``insights`` but no ``activity`` resource).

Callers should migrate to ``InsightsAPI.get_insights`` (for category /
adblock / inspected breakdowns) or ``DataUsageAPI.get_data_usage`` (for
bandwidth per client / node). See issue #107.

The methods are retained with a ``DeprecationWarning`` for one release
cycle so downstream consumers (eero-prometheus-exporter, eeroctl) get a
migration signal. Scheduled for removal in v6.0.0.
"""

import logging
import warnings
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)

# Shared by every method in ActivityAPI and the mirrored EeroClient wrappers.
# Kept in one place so a single edit updates every deprecation site.
ACTIVITY_DEPRECATION_MSG = (
    "The Eero cloud API no longer serves /networks/{id}/activity* — every call"
    " raises 404. Migrate to InsightsAPI.get_insights(...) for category / adblock"
    " / inspected breakdowns, or DataUsageAPI.get_data_usage(...) for bandwidth."
    " Scheduled for removal in v6.0.0."
    " See https://github.com/fulviofreitas/eero-api/issues/107"
)


class ActivityAPI(AuthenticatedAPI):
    """Activity API for Eero — DEPRECATED, endpoints no longer exist.

    Every method in this class targets a ``/networks/{id}/activity*`` path that
    Eero's cloud API returns 404 on. Retained (with ``DeprecationWarning``)
    for one release cycle so downstream callers see a migration signal instead
    of a silent import breakage. Scheduled for removal in v6.0.0.

    Replacements (both already in the SDK, both live-verified):

    - ``InsightsAPI.get_insights(network_id, start=..., end=..., insight_type=...)``
      for category / adblock / inspected breakdowns.
    - ``DataUsageAPI.get_data_usage(...)`` for bandwidth per client / node.

    See issue #107.
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ActivityAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_activity(self, network_id: str) -> Dict[str, Any]:
        """DEPRECATED — endpoint returns 404. See :class:`ActivityAPI` docstring."""
        warnings.warn(
            f"ActivityAPI.get_activity: {ACTIVITY_DEPRECATION_MSG}",
            DeprecationWarning,
            stacklevel=2,
        )
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting activity for network %s", network_id)
        return await self.get(f"networks/{network_id}/activity", auth_token=auth_token)

    async def get_activity_clients(self, network_id: str) -> Dict[str, Any]:
        """DEPRECATED — endpoint returns 404. See :class:`ActivityAPI` docstring."""
        warnings.warn(
            f"ActivityAPI.get_activity_clients: {ACTIVITY_DEPRECATION_MSG}",
            DeprecationWarning,
            stacklevel=2,
        )
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting client activity for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/activity/clients",
            auth_token=auth_token,
        )

    async def get_activity_for_device(self, network_id: str, device_id: str) -> Dict[str, Any]:
        """DEPRECATED — endpoint returns 404. See :class:`ActivityAPI` docstring."""
        warnings.warn(
            f"ActivityAPI.get_activity_for_device: {ACTIVITY_DEPRECATION_MSG}",
            DeprecationWarning,
            stacklevel=2,
        )
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting activity for device %s in network %s", device_id, network_id)
        return await self.get(
            f"networks/{network_id}/activity/{device_id}",
            auth_token=auth_token,
        )

    async def get_activity_history(
        self,
        network_id: str,
        period: str = "day",
    ) -> Dict[str, Any]:
        """DEPRECATED — endpoint returns 404. See :class:`ActivityAPI` docstring."""
        warnings.warn(
            f"ActivityAPI.get_activity_history: {ACTIVITY_DEPRECATION_MSG}",
            DeprecationWarning,
            stacklevel=2,
        )
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        valid_periods = ["hour", "day", "week", "month"]
        if period not in valid_periods:
            _LOGGER.warning("Invalid period '%s', defaulting to 'day'", period)
            period = "day"

        _LOGGER.debug("Getting activity history for network %s (period: %s)", network_id, period)
        return await self.get(
            f"networks/{network_id}/activity/history",
            auth_token=auth_token,
            params={"period": period},
        )

    async def get_activity_categories(self, network_id: str) -> Dict[str, Any]:
        """DEPRECATED — endpoint returns 404. See :class:`ActivityAPI` docstring."""
        warnings.warn(
            f"ActivityAPI.get_activity_categories: {ACTIVITY_DEPRECATION_MSG}",
            DeprecationWarning,
            stacklevel=2,
        )
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting activity categories for network %s", network_id)
        return await self.get(
            f"networks/{network_id}/activity/categories",
            auth_token=auth_token,
        )
