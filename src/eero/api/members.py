"""Members API for Eero.

IMPORTANT: This module returns RAW responses from the Eero Cloud API.
All data extraction, field mapping, and transformation must be done by downstream clients.

`get_members` is live-verified. Every other operation in this module --
including `get_invites`, a read -- is unverified: reading invites on the
maintainer's own account returned an access-denied response, so neither the
response shape nor any write's side effects have been confirmed against a
live network. Each write logs one warning via `warn_uncharacterised_write`
before it is issued; follow the read-compare-skip discipline and never
retry a failed write in a loop.
"""

from typing import Any, Dict, Mapping, Optional

from ..const import API_ENDPOINT, API_VERSION_DEFAULT
from ..exceptions import EeroAuthenticationException, EeroValidationException
from ..logging import get_secure_logger
from ._writes import as_envelope, warn_uncharacterised_write
from .auth import AuthAPI
from .base import AuthenticatedAPI, RequestEncoding
from .links import resource_url, sub_resource_url

_LOGGER = get_secure_logger(__name__)

#: Template for a single invite resource on the default API version.
_INVITE_TEMPLATE = "networks/{network}/invites/{{id}}"

#: Template for a single admin resource on the default API version.
_ADMIN_TEMPLATE = "networks/{network}/admins/{{id}}"

#: The wire values the API's ``InviteRole`` enum declares.
_INVITE_ROLES = frozenset({"owner", "admin"})


class MembersAPI(AuthenticatedAPI):
    """Members API for Eero.

    Manages network members, invites, and admin promotion/removal. All
    methods return raw, unmodified JSON responses from the Eero Cloud API.
    Response format: {"meta": {...}, "data": {...}}
    """

    def __init__(self, auth_api: AuthAPI) -> None:
        """Initialize the MembersAPI.

        Args:
            auth_api: Authentication API instance
        """
        super().__init__(auth_api, API_ENDPOINT)

    async def get_members(
        self, network_id: str, *, parent: Optional[Mapping[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get the network's members. Live-verified.

        GETs the network's ``members`` link.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            parent: The network's own cached envelope, if the caller has
                one; when supplied, its published ``members`` link is used
                instead of the default template. Read only; never mutated.

        Returns:
            Raw API response: {"meta": {...}, "data": {"members": [...]}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = sub_resource_url(
            network_id,
            "networks/{id}/members",
            link="members",
            parent=as_envelope(parent),
            version=API_VERSION_DEFAULT,
        )
        _LOGGER.debug("Getting members for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def get_invites(self, network_id: str) -> Dict[str, Any]:
        """Get the network's pending invites. Unverified.

        GETs ``networks/{id}/invites``.

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

        url = resource_url(network_id, "networks/{id}/invites", version=API_VERSION_DEFAULT)
        _LOGGER.debug("Getting invites for network %s", network_id)
        return await self.get(url, auth_token=auth_token)

    async def create_invite(self, network_id: str, *, role: str) -> Dict[str, Any]:
        """Create an invite for the network.

        POSTs a JSON body (``{"invite_role": ...}``) to
        ``networks/{id}/invites``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            role: The invited role, ``"owner"`` or ``"admin"``
                (case-insensitive).

        Returns:
            Raw API response: {"meta": {...}, "data": {"invite_id": ...,
            "invite_role": ..., "invite_url": ...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If ``role`` is not ``"owner"`` or
                ``"admin"``
            EeroAPIException: If the API returns an error
        """
        normalised_role = role.strip().lower() if isinstance(role, str) else ""
        if normalised_role not in _INVITE_ROLES:
            raise EeroValidationException(
                "role", f"must be one of {sorted(_INVITE_ROLES)!r}, got {role!r}"
            )

        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(network_id, "networks/{id}/invites", version=API_VERSION_DEFAULT)
        warn_uncharacterised_write(_LOGGER, "create invite for network")
        return await self.post(url, auth_token=auth_token, json={"invite_role": normalised_role})

    async def update_invite(
        self, network_id: str, invite_id: str, *, invite_nickname: str
    ) -> Dict[str, Any]:
        """Rename a pending invite.

        PUTs a JSON body (``{"invite_nickname": ...}``) to
        ``networks/{id}/invites/{invite}``.

        Args:
            network_id: ID of the network the invite belongs to.
            invite_id: The invite's bare ID, path, or absolute URL.
            invite_nickname: The new nickname for the invite.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(invite_id, _INVITE_TEMPLATE.format(network=network_id))
        warn_uncharacterised_write(_LOGGER, "update invite for network")
        return await self.put(url, auth_token=auth_token, json={"invite_nickname": invite_nickname})

    async def delete_invite(self, network_id: str, invite_id: str) -> Dict[str, Any]:
        """Cancel a pending invite.

        DELETEs ``networks/{id}/invites/{invite}``.

        Args:
            network_id: ID of the network the invite belongs to.
            invite_id: The invite's bare ID, path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(invite_id, _INVITE_TEMPLATE.format(network=network_id))
        warn_uncharacterised_write(_LOGGER, "delete invite for network")
        return await self.delete(url, auth_token=auth_token)

    async def respond_to_invite(
        self,
        network_id: str,
        *,
        accept: bool,
        invite_id: Optional[str] = None,
        invite_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Accept or decline an external or promotion invite.

        POSTs a JSON body to ``networks/{id}/invites/response``. Exactly one
        of ``invite_id`` (a promotion invite, already scoped to this
        network) or ``invite_code`` (an external invite, identified by its
        shared code) must be supplied.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            accept: ``True`` to accept the invite, ``False`` to decline it.
            invite_id: The promotion invite's ID. Mutually exclusive with
                ``invite_code``.
            invite_code: The external invite's code. Mutually exclusive
                with ``invite_id``.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroValidationException: If neither or both of ``invite_id``/
                ``invite_code`` are supplied
            EeroAPIException: If the API returns an error
        """
        if (invite_id is None) == (invite_code is None):
            raise EeroValidationException(
                "invite_id", "exactly one of invite_id or invite_code must be supplied"
            )

        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(
            network_id, "networks/{id}/invites/response", version=API_VERSION_DEFAULT
        )
        payload: Dict[str, Any] = {"accept": accept}
        if invite_id is not None:
            payload["invite_id"] = invite_id
        else:
            payload["invite_code"] = invite_code

        warn_uncharacterised_write(_LOGGER, "respond to invite for network")
        return await self.post(url, auth_token=auth_token, json=payload)

    async def cancel_pending_admin(self, network_id: str) -> Dict[str, Any]:
        """Cancel all pending admin-promotion invites for the network.

        POSTs the two-character body ``""`` to
        ``networks/{id}/invites/cancel_pending_admin``, the shape the API
        accepts for this parameterless operation.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(
            network_id, "networks/{id}/invites/cancel_pending_admin", version=API_VERSION_DEFAULT
        )
        warn_uncharacterised_write(_LOGGER, "cancel pending admin invites for network")
        return await self.post(
            url, auth_token=auth_token, encoding=RequestEncoding.EMPTY_JSON_STRING
        )

    async def promote_member(self, network_id: str, member_id: str) -> Dict[str, Any]:
        """Promote a member to admin.

        POSTs a JSON body (``{"member_id": ...}``) to
        ``networks/{id}/member_promotion``.

        Args:
            network_id: A bare network ID, API-returned path, or absolute URL.
            member_id: The member's ID.

        Returns:
            Raw API response: {"meta": {...}, "data": {"invite_id": ...,
            "member_user_name": ...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(
            network_id, "networks/{id}/member_promotion", version=API_VERSION_DEFAULT
        )
        warn_uncharacterised_write(_LOGGER, "promote member for network")
        return await self.post(url, auth_token=auth_token, json={"member_id": member_id})

    async def remove_admin(self, network_id: str, user_id: str) -> Dict[str, Any]:
        """Remove an admin from the network.

        DELETEs ``networks/{id}/admins/{user}``.

        Args:
            network_id: ID of the network the admin belongs to.
            user_id: The admin user's ID.

        Returns:
            Raw API response: {"meta": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        url = resource_url(user_id, _ADMIN_TEMPLATE.format(network=network_id))
        warn_uncharacterised_write(_LOGGER, "remove admin from network")
        return await self.delete(url, auth_token=auth_token)

    async def query_invite(self, invite_code: str) -> Dict[str, Any]:
        """Look up an external invite by its code.

        POSTs a JSON body (``{"invite_code": ...}``) to ``/2.2/inviteQuery``.
        Not network-scoped: this endpoint resolves an invite code to the
        network and role it grants access to. The invite code is never
        logged.

        Args:
            invite_code: The invite code to look up.

        Returns:
            Raw API response: {"meta": {...}, "data": {...}}

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
        """
        auth_token = await self._auth_api.get_auth_token()
        if not auth_token:
            raise EeroAuthenticationException("Not authenticated")

        warn_uncharacterised_write(_LOGGER, "query invite by code")
        return await self.post(
            "inviteQuery", auth_token=auth_token, json={"invite_code": invite_code}
        )


__all__ = ["MembersAPI"]
