"""Tests for SupportAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.support import SupportAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestSupportAPIInit:
    """Tests for SupportAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = SupportAPI(auth_api)
        assert api._auth_api is auth_api


class TestSupportAPIGetSupport:
    """Tests for get_support method."""

    @pytest.fixture
    def support_api(self, mock_session):
        """Create a SupportAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SupportAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_support_returns_raw_response(self, support_api, mock_session):
        """Test get_support returns raw response."""
        support_data = {"phone": "+1234567890", "email": "support@eero.com"}
        mock_response = create_mock_response(200, api_success_response(support_data))
        mock_session.request.return_value = mock_response

        result = await support_api.get_support("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_support_not_authenticated(self, support_api):
        """Test get_support raises when not authenticated."""
        support_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await support_api.get_support("network_123")

    @pytest.mark.asyncio
    async def test_get_support_pins_to_2_2_even_with_2_3_parent_link(
        self, support_api, mock_session
    ):
        """get_support always hits 2.2, even when the parent envelope publishes a 2.3 link.

        2.3's ``support`` shape (a ``contacts`` array) differs from 2.2's flat
        object; see issue #135.
        """
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response
        parent = {"resources": {"support": "/2.3/networks/network_123/support"}}

        await support_api.get_support("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.2/networks/network_123/support")
        assert "/2.3/" not in call_args.args[1]


class TestSupportAPIRequestSupport:
    """Tests for request_support method."""

    @pytest.fixture
    def support_api(self, mock_session):
        """Create a SupportAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SupportAPI(auth_api)

    @pytest.mark.asyncio
    async def test_request_support_returns_raw_response(self, support_api, mock_session):
        """Test request_support returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await support_api.request_support("network_123", {"issue": "test"})

        assert "meta" in result
