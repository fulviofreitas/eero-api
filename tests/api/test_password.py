"""Tests for PasswordAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.password import PasswordAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestPasswordAPIInit:
    """Tests for PasswordAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = PasswordAPI(auth_api)
        assert api._auth_api is auth_api


class TestPasswordAPIGetPassword:
    """Tests for get_password method."""

    @pytest.fixture
    def password_api(self, mock_session):
        """Create a PasswordAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return PasswordAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_password_returns_raw_response(self, password_api, mock_session):
        """Test get_password returns raw response."""
        password_data = {"password": "secure123", "ssid": "MyNetwork"}
        mock_response = create_mock_response(200, api_success_response(password_data))
        mock_session.request.return_value = mock_response

        result = await password_api.get_password("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_password_not_authenticated(self, password_api):
        """Test get_password raises when not authenticated."""
        password_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await password_api.get_password("network_123")
