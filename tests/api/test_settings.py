"""Tests for SettingsAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.settings import SettingsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestSettingsAPIInit:
    """Tests for SettingsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = SettingsAPI(auth_api)
        assert api._auth_api is auth_api


class TestSettingsAPIGetSettings:
    """Tests for get_settings method."""

    @pytest.fixture
    def settings_api(self, mock_session):
        """Create a SettingsAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SettingsAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_settings_returns_raw_response(self, settings_api, mock_session):
        """Test get_settings returns raw response."""
        settings_data = {"timezone": "America/New_York", "locale": "en_US"}
        mock_response = create_mock_response(200, api_success_response(settings_data))
        mock_session.request.return_value = mock_response

        result = await settings_api.get_settings("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_settings_not_authenticated(self, settings_api):
        """Test get_settings raises when not authenticated."""
        settings_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await settings_api.get_settings("network_123")
