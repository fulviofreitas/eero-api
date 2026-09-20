"""DNS Policies API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

This family is a premium (Eero Plus / Eero Secure) feature and replaces the
profile-level content-filter, block-list, and blocked-applications fields
that ``ProfilesAPI`` used to write -- those fields never persisted on a
profile (see ``profiles.py``); this resource family is where content
filtering, domain allow/block lists, and per-profile application blocking
actually live.

Two read operations are live-verified: `get_advanced_content_filter` and
`get_profile_applications`. Every write in this module is unverified: its
request shape follows the API's own field declarations, but no write here
has been confirmed against a live network. Each write logs one warning via
`warn_uncharacterised_write` before it is issued; follow the read-compare-
skip discipline and never retry a failed write in a loop.

Not exposed by this module: network-level and profile-level DNS-policy
*settings* (the twelve boolean content-category toggles such as
``ad_block``, ``block_malware``, ``safe_search_enabled``, and the matching
ad-block on/off switches). The network envelope's ``premium_dns`` field and
its ``resources`` object carry no link to these settings endpoints, and a
profile's own ``premium_dns``/``resources`` fields are equally silent --
there is no field anywhere in either envelope this SDK can read to build
the request URL, so hardcoding a guessed literal path would be unverifiable
and is deliberately avoided. The operations left unexposed for this reason
are: reading or writing a network's DNS-policy settings, updating a
network's ad-block settings, and the profile equivalents of all three.
Removal on the list-mutation endpoints below is expressed through the
API's own ``is_delete`` field on a PUT -- there is no DELETE verb for these
resources.
"""

from typing import Any, Dict, List, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI
from .links import resource_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Template for a network-scoped profile-applications resource.
_PROFILE_APPLICATIONS_TEMPLATE = "networks/{network}/dns_policies/profiles/{{id}}/applications"

#: Template for a network-scoped profile's blocked-applications resource.
_PROFILE_APPLICATIONS_BLOCKED_TEMPLATE = (
    "networks/{network}/dns_policies/profiles/{{id}}/applications/blocked"
)


def _payload(required: Dict[str, Any], **optional: Any) -> Dict[str, Any]:
    """Build a request body from required fields plus only the supplied optional ones.

    Args:
        required: Fields that are always present in the body.
        optional: Fields included only when their value is not ``None``.

    Returns:
        A new dict containing ``required`` plus every ``optional`` entry
        whose value is not ``None``.
    """
    payload = dict(required)
    for key, value in optional.items():
        if value is not None:
            payload[key] = value
    return payload


class DnsPoliciesAPI(AuthenticatedAPI):
    """DNS Policies API for Eero.

    Manages the advanced content filter, network- and profile-level domain
    allow/block lists, and per-profile blocked applications. All methods
    return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the DnsPoliciesAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    def _profile_applications_url(self, network_id: str, profile_id: str) -> str:
        """Resolve a profile's applications resource URL.

        Args:
            network_id: ID of the network the profile belongs to.
            profile_id: The profile's bare ID, path, or absolute URL.

        Returns:
            The absolute URL of the profile's applications resource.
        """
        return resource_url(profile_id, _PROFILE_APPLICATIONS_TEMPLATE.format(network=network_id))

    def _profile_applications_blocked_url(self, network_id: str, profile_id: str) -> str:
        """Resolve a profile's blocked-applications resource URL.

        Args:
            network_id: ID of the network the profile belongs to.
            profile_id: The profile's bare ID, path, or absolute URL.

        Returns:
            The absolute URL of the profile's blocked-applications resource.
        """
        return resource_url(
            profile_id, _PROFILE_APPLICATIONS_BLOCKED_TEMPLATE.format(network=network_id)
        )

    async def get_advanced_content_filter(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get the network's advanced content filter allow/block lists.

        GETs the network's ``advanced_content_filter`` link. Live-verified.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``advanced_content_filter``
                link is used instead of the default template. Read only;
                never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {"allowed_list": [...],
            "blocked_list": [...]}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroPremiumRequiredException: If the network is not on Eero
                Plus/Secure
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/dns_policies/advanced_content_filter",
            link="advanced_content_filter",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        _LOGGER.debug("Getting advanced content filter for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def allow_domain(
        self,
        network_id: str,
        domain: str,
        *,
        add_cname: Optional[bool] = None,
        reason_to_allow: Optional[int] = None,
        is_delete: Optional[bool] = None,
        keep_profiles: Optional[List[str]] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add (or remove) a domain from the network-wide allow list.

        PUTs a JSON body to the network's ``dns_policies/network/allowed``
        resource. Only ``domain`` plus whichever optional fields are
        supplied are sent; unsupplied optional fields are omitted from the
        request entirely. Set ``is_delete=True`` to remove the domain --
        the API expresses removal on this endpoint through this field, not
        a DELETE verb.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            domain: The domain to allow (or, with ``is_delete=True``, remove
                from the allow list).
            add_cname: Optional; whether to also allow the domain's CNAME
                chain. Omitted from the request when ``None``.
            reason_to_allow: Optional integer reason code. Omitted from the
                request when ``None``.
            is_delete: Optional; ``True`` removes the domain instead of
                adding it. Omitted from the request when ``None``.
            keep_profiles: Optional list of profile IDs/URLs whose own
                allow-list entries should be preserved. Omitted from the
                request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published link is used instead of
                the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {"cnames": [...],
            "profile_list": [...]}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/dns_policies/network/allowed",
            link="dns_policies_network_allowed",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        payload = _payload(
            {"domain": domain},
            add_cname=add_cname,
            reason_to_allow=reason_to_allow,
            is_delete=is_delete,
            keep_profiles=keep_profiles,
        )
        warn_uncharacterised_write(_LOGGER, "allow domain for network")
        return await self.put(url, auth_token=auth_token, json=payload)

    async def allow_cnames(
        self,
        network_id: str,
        domains: List[str],
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Allow a list of CNAME domains network-wide.

        PUTs a JSON body (``{"domains": [...]}``) to the network's
        ``dns_policies/network/allowed/cnames`` resource. This endpoint
        declares only the ``domains`` field -- no ``is_delete`` or
        ``keep_profiles``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            domains: The CNAME domains to allow.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published link is used instead of
                the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/dns_policies/network/allowed/cnames",
            link="dns_policies_network_allowed_cnames",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        warn_uncharacterised_write(_LOGGER, "allow CNAMEs for network")
        return await self.put(url, auth_token=auth_token, json={"domains": domains})

    async def block_domain(
        self,
        network_id: str,
        domain: str,
        *,
        is_delete: Optional[bool] = None,
        keep_profiles: Optional[List[str]] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add (or remove) a domain from the network-wide block list.

        PUTs a JSON body to the network's ``dns_policies/network/blocked``
        resource. Only ``domain`` plus whichever optional fields are
        supplied are sent. Set ``is_delete=True`` to remove the domain from
        the block list instead of adding it -- there is no DELETE verb for
        this resource.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            domain: The domain to block (or, with ``is_delete=True``, remove
                from the block list).
            is_delete: Optional; ``True`` removes the domain instead of
                blocking it. Omitted from the request when ``None``.
            keep_profiles: Optional list of profile IDs/URLs whose own
                block-list entries should be preserved. Omitted from the
                request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published link is used instead of
                the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/dns_policies/network/blocked",
            link="dns_policies_network_blocked",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        payload = _payload({"domain": domain}, is_delete=is_delete, keep_profiles=keep_profiles)
        warn_uncharacterised_write(_LOGGER, "block domain for network")
        return await self.put(url, auth_token=auth_token, json=payload)

    async def allow_domain_for_profiles(
        self,
        network_id: str,
        domain: str,
        *,
        profiles: List[str],
        override: Optional[bool] = None,
        add_cname: Optional[bool] = None,
        reason_to_allow: Optional[int] = None,
        is_delete: Optional[bool] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add (or remove) a domain from one or more profiles' allow lists.

        PUTs a JSON body to the network's ``dns_policies/profiles/allowed``
        resource. ``domain`` and ``profiles`` are always sent; the
        remaining fields are sent only when supplied. Set ``is_delete=True``
        to remove the domain instead of adding it -- there is no DELETE
        verb for this resource.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            domain: The domain to allow (or, with ``is_delete=True``, remove).
            profiles: The profile IDs/URLs the write applies to.
            override: Optional; whether this entry overrides a conflicting
                network-wide entry. Omitted from the request when ``None``.
            add_cname: Optional; whether to also allow the domain's CNAME
                chain. Omitted from the request when ``None``.
            reason_to_allow: Optional integer reason code. Omitted from the
                request when ``None``.
            is_delete: Optional; ``True`` removes the domain instead of
                adding it. Omitted from the request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published link is used instead of
                the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {"cnames": [...],
            "profile_list": [...]}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/dns_policies/profiles/allowed",
            link="dns_policies_profiles_allowed",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        payload = _payload(
            {"domain": domain, "profiles": profiles},
            override=override,
            add_cname=add_cname,
            reason_to_allow=reason_to_allow,
            is_delete=is_delete,
        )
        warn_uncharacterised_write(_LOGGER, "allow domain for profiles on network")
        return await self.put(url, auth_token=auth_token, json=payload)

    async def allow_cnames_for_profiles(
        self,
        network_id: str,
        domains: List[str],
        *,
        profiles: List[str],
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Allow a list of CNAME domains for one or more profiles.

        PUTs a JSON body (``{"domains": [...], "profiles": [...]}``) to the
        network's ``dns_policies/profiles/allowed/cnames`` resource. This
        endpoint declares only ``domains`` and ``profiles``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            domains: The CNAME domains to allow.
            profiles: The profile IDs/URLs the write applies to.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published link is used instead of
                the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/dns_policies/profiles/allowed/cnames",
            link="dns_policies_profiles_allowed_cnames",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        warn_uncharacterised_write(_LOGGER, "allow CNAMEs for profiles on network")
        return await self.put(
            url, auth_token=auth_token, json={"domains": domains, "profiles": profiles}
        )

    async def block_domain_for_profiles(
        self,
        network_id: str,
        domain: str,
        *,
        profiles: List[str],
        is_delete: Optional[bool] = None,
        override: Optional[bool] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Add (or remove) a domain from one or more profiles' block lists.

        PUTs a JSON body to the network's ``dns_policies/profiles/blocked``
        resource. ``domain`` and ``profiles`` are always sent; ``is_delete``
        and ``override`` are sent only when supplied. Set ``is_delete=True``
        to remove the domain instead of blocking it -- there is no DELETE
        verb for this resource.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            domain: The domain to block (or, with ``is_delete=True``, remove).
            profiles: The profile IDs/URLs the write applies to.
            is_delete: Optional; ``True`` removes the domain instead of
                blocking it. Omitted from the request when ``None``.
            override: Optional; whether this entry overrides a conflicting
                network-wide entry. Omitted from the request when ``None``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published link is used instead of
                the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/dns_policies/profiles/blocked",
            link="dns_policies_profiles_blocked",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        payload = _payload(
            {"domain": domain, "profiles": profiles}, is_delete=is_delete, override=override
        )
        warn_uncharacterised_write(_LOGGER, "block domain for profiles on network")
        return await self.put(url, auth_token=auth_token, json=payload)

    async def get_profile_applications(self, network_id: str, profile_id: str) -> Dict[str, Any]:
        """Get the applications a profile can block, and which are blocked.

        GETs ``networks/{id}/dns_policies/profiles/{profile}/applications``.
        Live-verified.

        Args:
            network_id: ID of the network the profile belongs to.
            profile_id: The profile's bare ID, path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}, "data": {"applications": [...],
            "categories_list": [...]}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = self._profile_applications_url(network_id, profile_id)
        _LOGGER.debug(
            "Getting blockable applications for profile %s in network %s",
            profile_id,
            network_id,
        )
        return await self.get(url, auth_token=auth_token)

    async def set_profile_blocked_applications(
        self, network_id: str, profile_id: str, applications: List[str]
    ) -> Dict[str, Any]:
        """Set the applications blocked for a profile.

        PUTs a JSON body (``{"applications": [...]}``) to
        ``networks/{id}/dns_policies/profiles/{profile}/applications/blocked``.
        This replaces the full blocked-applications list for the profile.

        Args:
            network_id: ID of the network the profile belongs to.
            profile_id: The profile's bare ID, path, or absolute URL.
            applications: The application identifiers to block.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = self._profile_applications_blocked_url(network_id, profile_id)
        warn_uncharacterised_write(_LOGGER, "set blocked applications for profile on network")
        return await self.put(url, auth_token=auth_token, json={"applications": applications})
