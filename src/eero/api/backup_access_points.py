"""Backup access points (backup Wi-Fi networks) API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.
"""

from typing import Any, Dict, List, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._params import resolve_nested_url
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI, RequestEncoding
from .links import resource_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)


class BackupAccessPointsAPI(AuthenticatedAPI):
    """Backup access points (backup Wi-Fi networks) API for Eero.

    Backup access points are alternate Wi-Fi networks an eero falls back to
    when its primary uplink is unavailable. All methods return raw,
    unmodified JSON responses from the Eero Cloud API. Response format:
    {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the BackupAccessPointsAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def list(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """List backup access points for a network - returns raw Eero API response.

        GETs the network's ``backup_access_points`` sub-resource. This is a
        verified read.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published
                ``backup_access_points`` link is used instead of the default
                template. Read only; never mutated.

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
            "networks/{id}/backup_access_points",
            link="backup_access_points",
            parent=as_envelope(parent),
        )
        _LOGGER.debug("Listing backup access points for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def add(
        self,
        network_id: str,
        *,
        ssid: str,
        password: str,
        uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a backup access point - returns raw Eero API response.

        Issues a JSON POST to the network's ``backup_access_points``
        sub-resource with ``ssid``, ``password``, and, when supplied,
        ``uuid``. The password value is never logged; the field name
        ``password`` is redacted by the secure logger by convention.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            ssid: The backup network's SSID, e.g. ``"example-ssid"``.
            password: The backup network's password. Never logged.
            uuid: An optional client-supplied identifier for the backup
                network. Omitted from the request when ``None``.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/backup_access_points")
        payload: Dict[str, Any] = {"ssid": ssid, "password": password}
        if uuid is not None:
            payload["uuid"] = uuid

        warn_uncharacterised_write(_LOGGER, "add backup access point for network")
        return await self.post(url, auth_token=auth_token, json=payload)

    async def update(
        self,
        network_id: str,
        backup_network_id: str,
        *,
        ssid: Optional[str] = None,
        password: Optional[str] = None,
        enabled: Optional[bool] = None,
        uuid: Optional[str] = None,
        connectivity: Optional[Mapping[str, Any]] = None,
        created: Optional[str] = None,
        last_updated_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update a backup access point - returns raw Eero API response.

        Issues a JSON PUT to the network's
        ``backup_access_points/{backup_network_id}`` sub-resource with
        exactly the fields supplied. The password value is never logged.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `list` first, and only
            issue this write when the stored entry differs from the desired
            one. Never retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            backup_network_id: The backup access point's bare ID.
            ssid: The backup network's SSID. Omitted from the request when
                ``None``.
            password: The backup network's password. Never logged. Omitted
                from the request when ``None``.
            enabled: Whether the backup network is enabled. Omitted from the
                request when ``None``.
            uuid: The backup network's identifier. Omitted from the request
                when ``None``.
            connectivity: The backup network's connectivity status,
                forwarded to the API unchanged. Omitted from the request
                when ``None``.
            created: The backup network's creation timestamp. Omitted from
                the request when ``None``.
            last_updated_at: The backup network's last-updated timestamp.
                Omitted from the request when ``None``.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {}
        if ssid is not None:
            payload["ssid"] = ssid
        if password is not None:
            payload["password"] = password
        if enabled is not None:
            payload["enabled"] = enabled
        if uuid is not None:
            payload["uuid"] = uuid
        if connectivity is not None:
            payload["connectivity"] = connectivity
        if created is not None:
            payload["created"] = created
        if last_updated_at is not None:
            payload["last_updated_at"] = last_updated_at

        url = resolve_nested_url(network_id, backup_network_id, prefix="backup_access_points")
        warn_uncharacterised_write(
            _LOGGER,
            "update backup access point for network",
        )
        return await self.put(url, auth_token=auth_token, json=payload)

    async def delete_backup_access_point(
        self, network_id: str, backup_network_id: str
    ) -> Dict[str, Any]:
        """Delete a backup access point - returns raw Eero API response.

        Issues a DELETE to the network's
        ``backup_access_points/{backup_network_id}`` sub-resource.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            backup_network_id: The backup access point's bare ID.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resolve_nested_url(network_id, backup_network_id, prefix="backup_access_points")
        warn_uncharacterised_write(
            _LOGGER,
            "delete backup access point for network",
        )
        return await self.delete(url, auth_token=auth_token)

    async def rearrange(self, network_id: str, order: List[str]) -> Dict[str, Any]:
        """Reorder backup access points - returns raw Eero API response.

        Issues a JSON POST to the network's
        ``backup_access_points/rearrange`` sub-resource with
        ``{"rearranged_ids": order}``.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            order: The backup access point IDs in the desired order.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/backup_access_points/rearrange")
        warn_uncharacterised_write(_LOGGER, "rearrange backup access points for network")
        return await self.post(url, auth_token=auth_token, json={"rearranged_ids": order})

    async def discover_ssids(self, network_id: str) -> Dict[str, Any]:
        """Get the status of a backup-network SSID discovery scan - returns raw Eero API response.

        GETs the network's ``backup_access_points/ssid_discovery``
        sub-resource. This is a verified read.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/backup_access_points/ssid_discovery")
        _LOGGER.debug("Getting SSID discovery status for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def start_ssid_discovery(self, network_id: str) -> Dict[str, Any]:
        """Start a backup-network SSID discovery scan - returns raw Eero API response.

        Issues a POST with the two-character body ``""`` -- the API
        declares no request fields for this parameterless operation -- to
        the network's ``backup_access_points/ssid_discovery`` sub-resource.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/backup_access_points/ssid_discovery")
        warn_uncharacterised_write(_LOGGER, "start SSID discovery for network")
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )

    async def connectivity_check(self, network_id: str) -> Dict[str, Any]:
        """Start a backup-network connectivity check - returns raw Eero API response.

        Issues a POST with the two-character body ``""`` -- the API
        declares no request fields for this parameterless operation -- to
        the network's ``backup_access_points/connectivity_check``
        sub-resource.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/backup_access_points/connectivity_check")
        warn_uncharacterised_write(_LOGGER, "start backup connectivity check for network")
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )
