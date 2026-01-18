"""SQM/QoS API for Eero (Smart Queue Management)."""

import logging
from typing import Any, Dict, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from .auth import AuthAPI
from .base import AuthenticatedAPI

_LOGGER = logging.getLogger(__name__)


class SqmAPI(AuthenticatedAPI):
    """SQM/QoS API for Eero.

    Manages Smart Queue Management (SQM) settings for traffic
    optimization and Quality of Service (QoS) configuration.
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the SqmAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_sqm_settings(self, network_id: str) -> Dict[str, Any]:
        """Get SQM/QoS settings for a network.

        Args:
            network_id: ID of the network

        Returns:
            Dictionary containing SQM settings:
            - enabled: bool - Whether SQM is enabled
            - upload_bandwidth: int - Upload bandwidth in Mbps
            - download_bandwidth: int - Download bandwidth in Mbps
            - mode: str - SQM mode (auto, manual)

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Getting SQM settings for network %s", network_id)

        response = await self.get(
            f"networks/{network_id}",
            auth_token=auth_token,
        )

        data = response.get("data", {})

        sqm_settings = {
            "enabled": False,
            "upload_bandwidth": None,
            "download_bandwidth": None,
            "mode": "auto",
        }

        # Check for SQM settings in different formats
        if "sqm" in data:
            sqm = data["sqm"]
            if isinstance(sqm, dict):
                sqm_settings["enabled"] = sqm.get("enabled", False)
                sqm_settings["upload_bandwidth"] = sqm.get("upload_bandwidth")
                sqm_settings["download_bandwidth"] = sqm.get("download_bandwidth")
                sqm_settings["mode"] = sqm.get("mode", "auto")
            elif isinstance(sqm, bool):
                sqm_settings["enabled"] = sqm

        # Check for bandwidth_control
        if "bandwidth_control" in data:
            bc = data["bandwidth_control"]
            if isinstance(bc, dict):
                sqm_settings["enabled"] = bc.get("enabled", sqm_settings["enabled"])
                sqm_settings["upload_bandwidth"] = bc.get(
                    "upload", sqm_settings["upload_bandwidth"]
                )
                sqm_settings["download_bandwidth"] = bc.get(
                    "download", sqm_settings["download_bandwidth"]
                )

        # Check for qos settings
        if "qos" in data:
            qos = data["qos"]
            if isinstance(qos, dict):
                sqm_settings["enabled"] = qos.get("enabled", sqm_settings["enabled"])

        return sqm_settings

    async def set_sqm_enabled(self, network_id: str, enabled: bool) -> bool:
        """Enable or disable SQM (Smart Queue Management).

        Args:
            network_id: ID of the network
            enabled: True to enable SQM, False to disable

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug(
            "%s SQM for network %s",
            "Enabling" if enabled else "Disabling",
            network_id,
        )

        response = await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"sqm": {"enabled": enabled}},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def set_sqm_bandwidth(
        self,
        network_id: str,
        upload_mbps: Optional[int] = None,
        download_mbps: Optional[int] = None,
    ) -> bool:
        """Set SQM bandwidth limits.

        Args:
            network_id: ID of the network
            upload_mbps: Upload bandwidth limit in Mbps
            download_mbps: Download bandwidth limit in Mbps

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        sqm_payload: Dict[str, Any] = {"enabled": True}

        if upload_mbps is not None:
            sqm_payload["upload_bandwidth"] = upload_mbps

        if download_mbps is not None:
            sqm_payload["download_bandwidth"] = download_mbps

        _LOGGER.debug(
            "Setting SQM bandwidth for network %s: up=%s, down=%s",
            network_id,
            upload_mbps,
            download_mbps,
        )

        response = await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"sqm": sqm_payload},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def configure_sqm(
        self,
        network_id: str,
        enabled: bool,
        upload_mbps: Optional[int] = None,
        download_mbps: Optional[int] = None,
    ) -> bool:
        """Configure SQM settings in one call.

        Args:
            network_id: ID of the network
            enabled: True to enable SQM, False to disable
            upload_mbps: Upload bandwidth limit in Mbps
            download_mbps: Download bandwidth limit in Mbps

        Returns:
            True if the operation was successful

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        sqm_payload: Dict[str, Any] = {"enabled": enabled}

        if enabled:
            if upload_mbps is not None:
                sqm_payload["upload_bandwidth"] = upload_mbps
            if download_mbps is not None:
                sqm_payload["download_bandwidth"] = download_mbps

        _LOGGER.debug("Configuring SQM for network %s: %s", network_id, sqm_payload)

        response = await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"sqm": sqm_payload},
        )

        return bool(response.get("meta", {}).get("code") == 200)

    async def set_sqm_auto(self, network_id: str) -> bool:
        """Set SQM to automatic mode (auto-detect bandwidth).

        Args:
            network_id: ID of the network

        Returns:
            True if the operation was successful
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        _LOGGER.debug("Setting SQM to auto mode for network %s", network_id)

        response = await self.put(
            f"networks/{network_id}",
            auth_token=auth_token,
            json={"sqm": {"enabled": True, "mode": "auto"}},
        )

        return bool(response.get("meta", {}).get("code") == 200)
