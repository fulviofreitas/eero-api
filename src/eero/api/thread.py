"""Thread API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

The Thread read goes through the network's published ``thread`` link, like
every other sub-resource. The write operations below all target the literal
``networks/{id}/thread`` path directly (they are not resolved through a
published link) per the API's declared shape for this family.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI, RequestEncoding
from .links import resource_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)


class ThreadAPI(AuthenticatedAPI):
    """Thread API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the ThreadAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_thread(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get Thread status - returns raw Eero API response.

        GETs the network's ``thread`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``thread`` link is used
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
            network_id, "networks/{id}/thread", link="thread", parent=as_envelope(parent)
        )
        _LOGGER.debug("Getting thread status for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def set_thread_enabled(
        self, network_id: str, enabled: bool, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Enable or disable Thread - returns raw Eero API response.

        Issues a JSON PUT (``{"enabled": bool}``) to the literal
        ``networks/{id}/thread`` path.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_thread` first, and
            only issue this write when the stored value differs from the
            desired one.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to enable Thread, False to disable.
            parent: Unused; accepted for signature consistency with the rest
                of this family. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/thread")
        warn_uncharacterised_write(_LOGGER, f"set thread enabled for network {network_id}")
        return await self.put(url, auth_token=auth_token, json={"enabled": enabled})

    async def update_thread(
        self,
        network_id: str,
        *,
        thread_enable: Optional[bool] = None,
        enable_credential_syncing: Optional[bool] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Update Thread configuration - returns raw Eero API response.

        Issues a JSON PUT to the literal ``networks/{id}/thread`` path with
        exactly the keys supplied among ``thread_enable`` and
        ``enable_credential_syncing``.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_thread` first, and
            only issue this write when the stored configuration differs from
            the desired one.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            thread_enable: Optional Thread enable/disable flag. Omitted from
                the request body when ``None``.
            enable_credential_syncing: Optional Thread credential-syncing
                flag. Omitted from the request body when ``None``.
            parent: Unused; accepted for signature consistency with the rest
                of this family. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If neither field is supplied
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, bool] = {}
        if thread_enable is not None:
            payload["thread_enable"] = thread_enable
        if enable_credential_syncing is not None:
            payload["enable_credential_syncing"] = enable_credential_syncing

        if not payload:
            raise EeroValidationException(
                "thread", "at least one of thread_enable, enable_credential_syncing is required"
            )

        url = resource_url(network_id, "networks/{id}/thread")
        warn_uncharacterised_write(_LOGGER, f"update thread config for network {network_id}")
        return await self.put(url, auth_token=auth_token, json=payload)

    async def regenerate_thread_credentials(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Regenerate Thread network credentials - returns raw Eero API response.

        Issues a POST with the two-character body ``""`` to the literal
        ``networks/{id}/thread`` path.

        .. warning::
            This write has not been confirmed against a live network. The
            response is documented to carry a ``network`` key of unknown
            shape -- this method returns it unmodified but logs nothing of
            its contents.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: Unused; accepted for signature consistency with the rest
                of this family. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/thread")
        warn_uncharacterised_write(
            _LOGGER, f"regenerate thread credentials for network {network_id}"
        )
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )
