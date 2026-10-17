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

The network-level switches `set_network_ad_block` (``dns_policies/adblock``)
and `set_network_block_malware` (``dns_policies/network``) are literal
sub-paths of the network URL that no envelope publishes as a link; they are
exposed because a downstream integration has sent them for years, and they
remain uncharacterised writes.

Still not exposed: the profile-level content-filter settings
(``dns_policies/profiles/{id}``, the ten boolean category toggles such as
``safe_search_enabled``), pending a live read-back.

Removal on the list-mutation endpoints below is expressed through the
API's own ``is_delete`` field on a PUT -- there is no DELETE verb for these
resources.
"""

from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlsplit

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._params import resolve_nested_url, resolve_network_url
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI, id_from_url
from .links import sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Body keys the network-level ``dns_policies/network`` switch accepts. The
#: API silently discards unknown keys with a 200, so this is checked
#: client-side before any request.
_NETWORK_DNS_POLICY_KEYS = frozenset({"block_malware"})


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
    allow/block lists, per-profile blocked applications, and the
    network-level ad-block and malware switches. All methods
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

        A profile path/URL (e.g. ``/2.2/networks/{network}/profiles/{id}``)
        cannot be mapped onto the ``dns_policies/profiles/{id}`` sub-tree by
        substitution -- the two resource families share only the trailing
        id. ``profile_id`` is therefore first normalised to that trailing
        id via ``id_from_url`` (a no-op for an already-bare id), then
        validated and appended as a literal path segment.

        Args:
            network_id: ID of the network the profile belongs to.
            profile_id: The profile's bare ID, path, or absolute URL.

        Returns:
            The absolute URL of the profile's applications resource.
        """
        return resolve_nested_url(
            network_id,
            id_from_url(profile_id),
            prefix="dns_policies/profiles",
            suffix="/applications",
        )

    def _profile_applications_blocked_url(self, network_id: str, profile_id: str) -> str:
        """Resolve a profile's blocked-applications resource URL.

        See `_profile_applications_url` for why ``profile_id`` is first
        normalised to its trailing id via ``id_from_url``.

        Args:
            network_id: ID of the network the profile belongs to.
            profile_id: The profile's bare ID, path, or absolute URL.

        Returns:
            The absolute URL of the profile's blocked-applications resource.
        """
        return resolve_nested_url(
            network_id,
            id_from_url(profile_id),
            prefix="dns_policies/profiles",
            suffix="/applications/blocked",
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

    def _profile_paths(self, network_id: str, profiles: List[str]) -> List[str]:
        """Normalise profile references to host-relative profile paths.

        The ad-block endpoint takes profile references as host-relative
        paths (``/2.2/networks/{network}/profiles/{profile}``), not ids.
        Each entry may be a bare id, an API-returned path, or an absolute
        URL on the API host. `resolve_nested_url` validates each entry
        (rejecting a path that belongs to another network or another
        resource family) and returns an absolute URL, whose path is taken.

        Args:
            network_id: ID of the network the profiles belong to.
            profiles: The profile references to normalise.

        Returns:
            The host-relative profile paths, in the order given.

        Raises:
            EeroValidationException: If an entry is not a valid profile
                reference for this network.
        """
        return [
            urlsplit(
                resolve_nested_url(
                    network_id, profile, prefix="profiles", version=API_VERSION_DEFAULT
                )
            ).path
            for profile in profiles
        ]

    async def set_network_ad_block(
        self,
        network_id: str,
        enabled: bool,
        *,
        profiles: Optional[List[str]] = None,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Switch ad blocking on or off, network-wide or per profile - returns raw Eero API response.

        POSTs a JSON body to the network's ``dns_policies/adblock``
        resource: ``{"enable": enabled}``, plus ``"profiles"`` when
        ``profiles`` is supplied. The ``profiles`` list REPLACES the
        previous list; an empty list with ``enabled=True`` means
        network-wide. Omit ``profiles`` for the network-wide switch.

        This path is a literal sub-path of the network URL that no envelope
        publishes as a link; it is not in the observed spec and is exposed
        because a downstream integration has sent it for years.

        .. warning::
            This write has not been confirmed against a live network, and it
            is a premium (Eero Plus / Eero Secure) feature. ``capable: true``
            in the network's ``premium_dns`` block alone does not mean the
            DNS-policy subsystem is enabled. Follow the read-compare-skip
            discipline: read `get_network` (``premium_dns``) first, and only
            issue this write when the stored state differs from the desired
            one. Never retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to switch ad blocking on, False to switch it off.
            profiles: Optional profile references the switch applies to, each
                a bare id, an API-returned path, or an absolute URL; they
                are sent as ``/2.2/networks/{network}/profiles/{profile}``
                paths. Replaces the previous list. Omitted from the request
                when ``None``; an empty list is sent as ``[]``.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its own ``url`` is used as the base
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If a profile reference is not valid for
                this network
            EeroPremiumRequiredException: If the network is not on Eero
                Plus/Secure
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        payload: Dict[str, Any] = {"enable": enabled}
        if profiles is not None:
            payload["profiles"] = self._profile_paths(network_id, profiles)

        base_url = resolve_network_url(network_id, parent, version=API_VERSION_DEFAULT)
        url = f"{base_url}/dns_policies/adblock"
        warn_uncharacterised_write(_LOGGER, "set network ad block for network")
        return await self.post(url, auth_token=auth_token, json=payload)

    async def _set_network_dns_policy(
        self,
        network_id: str,
        key: str,
        value: bool,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST one boolean switch to the network's ``dns_policies/network`` resource.

        The API silently discards unknown body keys with a 200, so ``key``
        is checked against `_NETWORK_DNS_POLICY_KEYS` before any request.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            key: The switch to set; one of `_NETWORK_DNS_POLICY_KEYS`.
            value: The desired state of the switch.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its own ``url`` is used as the base
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``key`` is not a known switch
            EeroPremiumRequiredException: If the network is not on Eero
                Plus/Secure
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        if key not in _NETWORK_DNS_POLICY_KEYS:
            raise EeroValidationException(
                "key", f"must be one of {sorted(_NETWORK_DNS_POLICY_KEYS)}, got {key!r}"
            )

        base_url = resolve_network_url(network_id, parent, version=API_VERSION_DEFAULT)
        url = f"{base_url}/dns_policies/network"
        warn_uncharacterised_write(_LOGGER, f"set network DNS policy {key} for network")
        return await self.post(url, auth_token=auth_token, json={key: value})

    async def set_network_block_malware(
        self,
        network_id: str,
        enabled: bool,
        *,
        parent: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Switch malware blocking on or off for the network - returns raw Eero API response.

        POSTs ``{"block_malware": enabled}`` to the network's
        ``dns_policies/network`` resource.

        This path is a literal sub-path of the network URL that no envelope
        publishes as a link; it is not in the observed spec and is exposed
        because a downstream integration has sent it for years.

        .. warning::
            This write has not been confirmed against a live network, and it
            is a premium (Eero Plus / Eero Secure) feature. ``capable: true``
            in the network's ``premium_dns`` block alone does not mean the
            DNS-policy subsystem is enabled. Follow the read-compare-skip
            discipline: read `get_network` (``premium_dns``) first, and only
            issue this write when the stored state differs from the desired
            one. Never retry a failed write in a loop.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            enabled: True to block malware, False to stop blocking it.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its own ``url`` is used as the base
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroPremiumRequiredException: If the network is not on Eero
                Plus/Secure
            EeroAPIException: If the API returns an error
        """
        return await self._set_network_dns_policy(
            network_id, "block_malware", enabled, parent=parent
        )
