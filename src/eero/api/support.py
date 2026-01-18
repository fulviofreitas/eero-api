"""Support API for Eero."""

import logging
from typing import Any, Dict

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class SupportAPI(AuthenticatedAPI):
    """Support API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the SupportAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_support(self, network_id: str) -> Dict[str, Any]:
        """Get network support information.

        Args:
            network_id: ID of the network to get support info for

        Returns:
            Support data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting support for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/support",
            auth_token=auth_token,
        )

        return response.get("data", {})

    async def create_support_ticket(
        self, network_id: str, ticket_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a support ticket.

        Args:
            network_id: ID of the network
            ticket_data: Support ticket data

        Returns:
            Created ticket data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Creating support ticket for network {network_id}: {ticket_data}")

        response = await self.post(
            f"networks/{network_id}/support",
            auth_token=auth_token,
            json=ticket_data,
        )

        return response.get("data", {})
