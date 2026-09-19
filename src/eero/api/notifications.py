"""Notifications API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._params import resolve_network_url
from ._writes import warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI, RequestEncoding

_LOGGER = get_secure_logger(__name__)


class NotificationsAPI(AuthenticatedAPI):
    """Notifications API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the NotificationsAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_settings(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get the network's notification settings -- returns raw Eero API response.

        Operation: GET ``networks/{id}/notifications``. The response's
        ``data`` field carries one boolean per event key, e.g.
        ``"network.updated"``, ``"device.new"``, ``"permissions.updates"``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one. Preferred over `network_id` to resolve the base URL
                when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{resolve_network_url(network_id, parent)}/notifications"
        _LOGGER.debug("Getting notification settings for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def set_settings(
        self,
        network_id: str,
        settings: Mapping[str, bool],
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Set the network's notification settings -- returns raw Eero API response.

        Issues a JSON PUT of ``settings`` to ``networks/{id}/notifications``
        exactly as supplied. Each key is a per-event boolean named as the
        API declares it, e.g. ``"network.updated"``, ``"device.new"``,
        ``"permissions.updates"``, ``"backup.internet.status.change"``; keys
        containing dots are sent verbatim (the API's own field names use
        dots). No validation is performed beyond requiring a mapping --
        the SDK does not enforce a closed set of event keys.

        .. warning::
            This write's side effects have not been confirmed against a
            live network. Follow the read-compare-skip discipline: call
            `get_settings` first and only issue this write when the stored
            configuration differs from the desired one. Do not retry on
            failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            settings: The caller-supplied per-event boolean mapping, sent
                as-is as the JSON request body.
            parent: The network's own cached envelope, if the caller has
                one. Preferred over `network_id` to resolve the base URL
                when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{resolve_network_url(network_id, parent)}/notifications"
        warn_uncharacterised_write(_LOGGER, f"set notification settings for network {network_id}")
        return await self.put(url, auth_token=auth_token, json=dict(settings))

    async def has_unread(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Check whether the network has unread notifications -- raw response.

        Operation: GET ``networks/{id}/notifications/has_unread``. Returns a
        ``has_unread`` boolean field in ``data``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one. Preferred over `network_id` to resolve the base URL
                when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{resolve_network_url(network_id, parent)}/notifications/has_unread"
        _LOGGER.debug("Checking unread notifications for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def mark_read(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Mark the network's notifications as read -- returns raw Eero API response.

        Issues a POST with the two-character body ``""`` -- the shape the
        API accepts for this parameterless operation -- to
        ``networks/{id}/notifications/mark_read``.

        .. warning::
            This write's side effects have not been confirmed against a
            live network. Follow the read-compare-skip discipline: call
            `has_unread` first and skip the write when there is nothing
            unread. Do not retry on failure.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one. Preferred over `network_id` to resolve the base URL
                when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{resolve_network_url(network_id, parent)}/notifications/mark_read"
        warn_uncharacterised_write(_LOGGER, f"mark notifications read for network {network_id}")
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )

    async def get_history(
        self,
        network_id: str,
        *,
        timestamp: Optional[str] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Get the network's notification history -- returns raw Eero API response.

        Operation: GET ``networks/{id}/notifications_history`` with the
        optional query parameter ``timestamp``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            timestamp: Optional pagination cursor, sent as the ``timestamp``
                query parameter. Omitted from the request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one. Preferred over `network_id` to resolve the base URL
                when supplied. Never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = f"{resolve_network_url(network_id, parent)}/notifications_history"
        params: Dict[str, str] = {}
        if timestamp is not None:
            params["timestamp"] = timestamp

        _LOGGER.debug("Getting notification history for network %s", network_id)
        return await self.get(url, auth_token=auth_token, params=params)

    async def set_push_settings(self, settings: Mapping[str, bool]) -> Dict[str, Any]:
        """Set the account's push notification settings -- returns raw Eero API response.

        Issues a JSON PUT of ``settings`` to ``/2.2/account/push_settings``
        exactly as supplied. The API declares this body as a
        ``PushSettings`` object; the account-level push toggles it accepts
        are ``networkOffline`` and ``nodeOffline`` (both booleans). No
        validation beyond requiring a mapping is performed -- the SDK does
        not enforce a closed set of keys.

        .. warning::
            This write's side effects have not been confirmed against a
            live account. Follow the read-compare-skip discipline where
            possible and do not retry on failure.

        Args:
            settings: The caller-supplied push-settings mapping, sent as-is
                as the JSON request body.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated.
            EeroAPIException: If the API returns an error.
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        warn_uncharacterised_write(_LOGGER, "set account push settings")
        return await self.put("account/push_settings", auth_token=auth_token, json=dict(settings))


__all__ = ["NotificationsAPI"]
