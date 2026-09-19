"""Tests for MembersAPI module."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.base import RequestEncoding
from eero.api.members import MembersAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response


class TestMembersAPIInit:
    """Tests for MembersAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = MembersAPI(auth_api)
        assert api._auth_api is auth_api


@pytest.fixture
def members_api(mock_session):
    """Create a MembersAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return MembersAPI(auth_api)


class TestGetMembers:
    """Tests for get_members."""

    @pytest.mark.asyncio
    async def test_returns_raw_envelope(self, members_api, mock_session):
        """Test the raw envelope is returned unchanged."""
        data = {"members": [{"user_name": "example"}]}
        envelope = api_success_response(data)
        mock_session.request.return_value = create_mock_response(200, envelope)

        result = await members_api.get_members("network_123")

        assert result == envelope

    @pytest.mark.asyncio
    async def test_uses_literal_path_by_default(self, members_api, mock_session):
        """Test the default template is used with no parent."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.get_members("network_123")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/networks/network_123/members")

    @pytest.mark.asyncio
    async def test_prefers_parent_link(self, members_api, mock_session):
        """Test a published parent link is preferred over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"resources": {"members": "/2.3/networks/network_123/members"}}

        await members_api.get_members("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/members")

    @pytest.mark.asyncio
    async def test_not_authenticated(self, members_api):
        """Test raises when not authenticated."""
        members_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await members_api.get_members("network_123")


class TestGetInvites:
    """Tests for get_invites."""

    @pytest.mark.asyncio
    async def test_url_and_verb(self, members_api, mock_session):
        """Test the literal path and verb."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.get_invites("network_123")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/networks/network_123/invites")

    @pytest.mark.asyncio
    async def test_not_authenticated(self, members_api):
        """Test raises when not authenticated."""
        members_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await members_api.get_invites("network_123")


class TestCreateInvite:
    """Tests for create_invite."""

    @pytest.mark.parametrize("role,wire_value", [("owner", "owner"), ("Admin", "admin")])
    @pytest.mark.asyncio
    async def test_sends_invite_role(self, members_api, mock_session, role, wire_value):
        """Test the request body and casing normalisation."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.create_invite("network_123", role=role)

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.kwargs["json"] == {"invite_role": wire_value}
        assert call_args.args[1].endswith("/networks/network_123/invites")

    @pytest.mark.asyncio
    async def test_rejects_invalid_role(self, members_api):
        """Test an unrecognised role raises validation error."""
        with pytest.raises(EeroValidationException):
            await members_api.create_invite("network_123", role="superuser")

    @pytest.mark.asyncio
    async def test_warns_uncharacterised_write(self, members_api, mock_session, caplog):
        """Test the write logs the unconfirmed-write warning."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await members_api.create_invite("network_123", role="admin")

        assert any("create invite for network" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_not_authenticated(self, members_api):
        """Test raises when not authenticated."""
        members_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await members_api.create_invite("network_123", role="admin")


class TestUpdateInvite:
    """Tests for update_invite."""

    @pytest.mark.asyncio
    async def test_sends_invite_nickname(self, members_api, mock_session):
        """Test the request body and URL."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.update_invite("network_123", "invite_1", invite_nickname="Kid")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.kwargs["json"] == {"invite_nickname": "Kid"}
        assert call_args.args[1].endswith("/networks/network_123/invites/invite_1")

    @pytest.mark.asyncio
    async def test_warns_uncharacterised_write(self, members_api, mock_session, caplog):
        """Test the write logs the unconfirmed-write warning."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await members_api.update_invite("network_123", "invite_1", invite_nickname="Kid")

        assert any("update invite" in m for m in caplog.messages)


class TestDeleteInvite:
    """Tests for delete_invite."""

    @pytest.mark.asyncio
    async def test_deletes_by_url(self, members_api, mock_session):
        """Test the verb and URL."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.delete_invite("network_123", "invite_1")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "DELETE"
        assert call_args.args[1].endswith("/networks/network_123/invites/invite_1")

    @pytest.mark.asyncio
    async def test_warns_uncharacterised_write(self, members_api, mock_session, caplog):
        """Test the write logs the unconfirmed-write warning."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await members_api.delete_invite("network_123", "invite_1")

        assert any("delete invite" in m for m in caplog.messages)


class TestRespondToInvite:
    """Tests for respond_to_invite."""

    @pytest.mark.asyncio
    async def test_sends_invite_id_variant(self, members_api, mock_session):
        """Test the invite_id body variant."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.respond_to_invite("network_123", accept=True, invite_id="invite_1")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.kwargs["json"] == {"accept": True, "invite_id": "invite_1"}
        assert call_args.args[1].endswith("/networks/network_123/invites/response")

    @pytest.mark.asyncio
    async def test_sends_invite_code_variant(self, members_api, mock_session):
        """Test the invite_code body variant."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.respond_to_invite("network_123", accept=False, invite_code="code_abc")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"accept": False, "invite_code": "code_abc"}

    @pytest.mark.parametrize(
        "invite_id,invite_code",
        [(None, None), ("invite_1", "code_abc")],
    )
    @pytest.mark.asyncio
    async def test_requires_exactly_one_identifier(self, members_api, invite_id, invite_code):
        """Test neither-nor-both raises a validation error."""
        with pytest.raises(EeroValidationException):
            await members_api.respond_to_invite(
                "network_123", accept=True, invite_id=invite_id, invite_code=invite_code
            )


class TestCancelPendingAdmin:
    """Tests for cancel_pending_admin."""

    @pytest.mark.asyncio
    async def test_sends_empty_json_string_body(self, members_api, mock_session):
        """Test the parameterless POST uses the empty-JSON-string body shape."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.cancel_pending_admin("network_123")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/networks/network_123/invites/cancel_pending_admin")
        assert call_args.kwargs["data"] == '""'

    @pytest.mark.asyncio
    async def test_warns_uncharacterised_write(self, members_api, mock_session, caplog):
        """Test the write logs the unconfirmed-write warning."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await members_api.cancel_pending_admin("network_123")

        assert any("cancel pending admin invites" in m for m in caplog.messages)


class TestPromoteMember:
    """Tests for promote_member."""

    @pytest.mark.asyncio
    async def test_sends_member_id(self, members_api, mock_session):
        """Test the request body and URL."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.promote_member("network_123", "member_1")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.kwargs["json"] == {"member_id": "member_1"}
        assert call_args.args[1].endswith("/networks/network_123/member_promotion")

    @pytest.mark.asyncio
    async def test_warns_uncharacterised_write(self, members_api, mock_session, caplog):
        """Test the write logs the unconfirmed-write warning."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await members_api.promote_member("network_123", "member_1")

        assert any("promote member for network" in m for m in caplog.messages)


class TestRemoveAdmin:
    """Tests for remove_admin."""

    @pytest.mark.asyncio
    async def test_deletes_by_url(self, members_api, mock_session):
        """Test the verb and URL."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.remove_admin("network_123", "user_1")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "DELETE"
        assert call_args.args[1].endswith("/networks/network_123/admins/user_1")

    @pytest.mark.asyncio
    async def test_warns_uncharacterised_write(self, members_api, mock_session, caplog):
        """Test the write logs the unconfirmed-write warning."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.WARNING):
            await members_api.remove_admin("network_123", "user_1")

        assert any("remove admin" in m for m in caplog.messages)


class TestQueryInvite:
    """Tests for query_invite."""

    @pytest.mark.asyncio
    async def test_sends_invite_code_to_top_level_path(self, members_api, mock_session):
        """Test the request body and the network-agnostic URL."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await members_api.query_invite("code_abc")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.kwargs["json"] == {"invite_code": "code_abc"}
        assert call_args.args[1].endswith("/2.2/inviteQuery")

    @pytest.mark.asyncio
    async def test_invite_code_value_never_logged(self, members_api, mock_session, caplog):
        """Test the invite code value never appears in any log record."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level(logging.DEBUG):
            await members_api.query_invite("super-secret-code")

        assert all("super-secret-code" not in record.getMessage() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_not_authenticated(self, members_api):
        """Test raises when not authenticated."""
        members_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await members_api.query_invite("code_abc")


def test_request_encoding_reexport():
    """Sanity check that RequestEncoding is importable from base for tests above."""
    assert RequestEncoding.EMPTY_JSON_STRING.value == "empty_json_string"
