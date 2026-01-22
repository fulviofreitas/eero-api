"""Tests for ACCompatAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.ac_compat import ACCompatAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestACCompatAPIInit:
    """Tests for ACCompatAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = ACCompatAPI(auth_api)
        assert api._auth_api is auth_api


class TestACCompatAPIGetACCompat:
    """Tests for get_ac_compat method."""

    @pytest.fixture
    def ac_compat_api(self, mock_session):
        """Create an ACCompatAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ACCompatAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_ac_compat_returns_raw_response(self, ac_compat_api, mock_session):
        """Test get_ac_compat returns raw response."""
        compat_data = {"compatible": True, "devices": []}
        mock_response = create_mock_response(200, api_success_response(compat_data))
        mock_session.request.return_value = mock_response

        result = await ac_compat_api.get_ac_compat("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_ac_compat_not_authenticated(self, ac_compat_api):
        """Test get_ac_compat raises when not authenticated."""
        ac_compat_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await ac_compat_api.get_ac_compat("network_123")
