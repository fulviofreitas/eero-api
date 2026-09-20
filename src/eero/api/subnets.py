"""Subnet configuration and per-subnet content-filter API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by
downstream clients.

`set_config` and `set_content_filters` forward the caller's mapping to the
API unchanged -- neither field, key, nor value is validated here. The
declared ``SubnetConfig`` fields are: ``dedicated_subnet``, ``enabled``,
``open_network``, ``name``, ``network_id``, ``password``, ``rate_limit_pct``,
``subnet_id``, ``subnet_kind``, ``subnet_type``, ``wan_access``.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Template for the content-filters sub-resource of a single subnet.
_SUBNET_CONTENT_FILTERS_TEMPLATE = (
    "networks/{{id}}/subnets_config/{subnet_id}/dns_policies/content_filters"
)

#: Template for deleting a single subnet's configuration by type.
_SUBNET_TYPE_TEMPLATE = "networks/{{id}}/subnets_config/{subnet_type}"


class SubnetsAPI(AuthenticatedAPI):
    """Subnet configuration and per-subnet content-filter API for Eero.

    All methods return raw, unmodified JSON responses from the Eero Cloud
    API. Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the SubnetsAPI.

        Args:
            auth_api: Authentication API instance.
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_config(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get the network's subnets configuration - returns raw Eero API response.

        GETs the network's ``subnets_config`` sub-resource. This is a
        verified read.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``subnets_config`` link is
                used instead of the default template. Read only; never
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

        url = sub_resource_url(
            network_id,
            "networks/{id}/subnets_config",
            link="subnets_config",
            parent=as_envelope(parent),
        )
        _LOGGER.debug("Getting subnets configuration for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def set_config(self, network_id: str, config: Mapping[str, Any]) -> Dict[str, Any]:
        """Create or edit a subnet configuration - returns raw Eero API response.

        Issues a JSON PUT to the network's ``subnets_config`` sub-resource
        with ``config`` forwarded unchanged. See the module docstring for
        the declared ``SubnetConfig`` field names; this method performs no
        validation of ``config``'s keys or values. The ``password`` value,
        when present, is never logged.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_config` first, and
            only issue this write when the stored configuration differs
            from the desired one. Never retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            config: The subnet configuration, forwarded to the API
                unchanged.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/subnets_config")
        warn_uncharacterised_write(_LOGGER, "set subnet configuration for network")
        return await self.put(url, auth_token=auth_token, json=dict(config))

    async def delete_subnet(self, network_id: str, subnet_type: str) -> Dict[str, Any]:
        """Delete a subnet's configuration - returns raw Eero API response.

        Issues a DELETE to the network's ``subnets_config/{subnet_type}``
        sub-resource.

        .. warning::
            This write has not been confirmed against a live network. Never
            retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            subnet_type: The subnet type to delete, as returned in
                `get_config`'s ``subnet_type`` field.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, _SUBNET_TYPE_TEMPLATE.format(subnet_type=subnet_type))
        warn_uncharacterised_write(_LOGGER, "delete subnet for network")
        return await self.delete(url, auth_token=auth_token)

    async def set_content_filters(
        self, network_id: str, filters: Mapping[str, Any]
    ) -> Dict[str, Any]:
        """Set content filters for one or more subnets - returns raw Eero API response.

        Issues a JSON PUT to the network's
        ``subnets_config/dns_policies/content_filters`` sub-resource. The
        API declares ``content_filters`` and ``subnets`` as the fields for
        this endpoint; ``filters`` is forwarded to the API unchanged, with
        no validation of its keys or values.

        .. warning::
            This write has not been confirmed against a live network. Follow
            the read-compare-skip discipline: read `get_content_filters`
            first, and only issue this write when the stored configuration
            differs from the desired one. Never retry a failed write in a
            loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            filters: The content-filters payload, forwarded to the API
                unchanged.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/subnets_config/dns_policies/content_filters")
        warn_uncharacterised_write(_LOGGER, "set subnet content filters for network")
        return await self.put(url, auth_token=auth_token, json=dict(filters))

    async def get_content_filters(self, network_id: str, subnet_id: str) -> Dict[str, Any]:
        """Get content filters for a subnet - returns raw Eero API response.

        GETs the network's
        ``subnets_config/{subnet_id}/dns_policies/content_filters``
        sub-resource. This is a verified read.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            subnet_id: The subnet's bare ID, as returned in `get_config`'s
                ``subnet_id`` field.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, _SUBNET_CONTENT_FILTERS_TEMPLATE.format(subnet_id=subnet_id))
        _LOGGER.debug("Getting content filters for subnet %s on network %s", subnet_id, network_id)
        return await self.get(url, auth_token=auth_token)
