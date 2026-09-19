"""Tests for PermissionsAPI module.

Tests cover:
- Getting the caller's permissions on a network (raw response)
- Parent-link (network self-url) preference
- Not-authenticated handling
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.permissions import PermissionsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def permissions_api(mock_session):
    """Create a PermissionsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return PermissionsAPI(auth_api)


class TestPermissionsAPIInit:
    """Tests for PermissionsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = PermissionsAPI(auth_api)

        assert api._auth_api is auth_api


class TestPermissionsAPIGetPermissions:
    """Tests for get_permissions method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "network_id,expected_suffix",
        [
            ("network_123", "/2.2/networks/network_123/permissions"),
            ("/2.2/networks/network_123", "/2.2/networks/network_123/permissions"),
            (
                "https://api-user.e2ro.com/2.2/networks/network_123",
                "/2.2/networks/network_123/permissions",
            ),
        ],
    )
    async def test_get_permissions_accepts_id_path_or_url(
        self, permissions_api, mock_session, network_id, expected_suffix
    ):
        """Test get_permissions accepts a bare id, a path, or an absolute URL."""
        mock_session.request.return_value = create_mock_response(
            200,
            api_success_response({"permissions": {"network.admin_invites": True}, "role": "OWNER"}),
        )

        result = await permissions_api.get_permissions(network_id)

        assert result["data"]["role"] == "OWNER"
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith(expected_suffix)

    @pytest.mark.asyncio
    async def test_get_permissions_prefers_parent_self_url(self, permissions_api, mock_session):
        """Test get_permissions uses the parent's own url over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"url": "/2.3/networks/network_123"}

        await permissions_api.get_permissions("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/permissions")

    @pytest.mark.asyncio
    async def test_get_permissions_not_authenticated(self, permissions_api):
        """Test get_permissions raises when not authenticated."""
        permissions_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await permissions_api.get_permissions("network_123")
