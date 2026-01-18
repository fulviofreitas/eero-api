"""Insights API for Eero."""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class InsightsAPI(AuthenticatedAPI):
    """Insights API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the InsightsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_insights(self, network_id: str) -> Dict[str, Any]:
        """Get network insights.

        Args:
            network_id: ID of the network to get insights for

        Returns:
            Insights data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting insights for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/insights",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def get_insight(self, network_id: str, insight_id: str) -> Dict[str, Any]:
        """Get a specific network insight.

        Args:
            network_id: ID of the network
            insight_id: ID of the insight to get

        Returns:
            Insight data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting insight {insight_id} for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/insights/{insight_id}",
            auth_token=auth_token,
        )

        return response.get("data", {})
