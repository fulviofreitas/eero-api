"""Port Forwards API for Eero."""

import logging
from typing import Any, Dict, List

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class ForwardsAPI(AuthenticatedAPI):
    """Port Forwards API for Eero."""

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ForwardsAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_forwards(self, network_id: str) -> List[Dict[str, Any]]:
        """Get port forwards.

        Args:
            network_id: ID of the network to get forwards from

        Returns:
            List of port forwards

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Getting forwards for network {network_id}")

        response = await self.get(
            f"networks/{network_id}/forwards",
            auth_token=auth_token,
        )

        # Handle different response formats
        data = response.get("data", [])
        if isinstance(data, list):
            # Data is directly a list of forwards
            forwards_data = data
        elif isinstance(data, dict) and "data" in data:
            # Data is a dictionary with a nested data field
            forwards_data = data.get("data", [])
        else:
            # Fallback to empty list
            forwards_data = []

        return forwards_data

    async def create_forward(self, network_id: str, forward_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a port forward.

        Args:
            network_id: ID of the network
            forward_data: Forward data (external_port, internal_port, device_id, etc.)

        Returns:
            Created forward data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Creating forward for network {network_id}: {forward_data}")

        response = await self.post(
            f"networks/{network_id}/forwards",
            auth_token=auth_token,
            json=forward_data,
        )

        return response.get("data", {})

    async def update_forward(
        self, network_id: str, forward_id: str, forward_data: Dict[str, Any]
    ) -> bool:
        """Update a port forward.

        Args:
            network_id: ID of the network
            forward_id: ID of the forward to update
            forward_data: Updated forward data

        Returns:
            True if update was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Updating forward {forward_id} for network {network_id}: {forward_data}")

        response = await self.put(
            f"networks/{network_id}/forwards/{forward_id}",
            auth_token=auth_token,
            json=forward_data,
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def delete_forward(self, network_id: str, forward_id: str) -> bool:
        """Delete a port forward.

        Args:
            network_id: ID of the network
            forward_id: ID of the forward to delete

        Returns:
            True if deletion was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(f"Deleting forward {forward_id} for network {network_id}")

        response = await self.delete(
            f"networks/{network_id}/forwards/{forward_id}",
            auth_token=auth_token,
        )

        return bool(response.get("meta", {}).get("code") == 200)
