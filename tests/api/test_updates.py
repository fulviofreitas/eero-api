"""Tests for UpdatesAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.updates import UpdatesAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestUpdatesAPIInit:
    """Tests for UpdatesAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = UpdatesAPI(auth_api)
        assert api._auth_api is auth_api


class TestUpdatesAPIGetUpdates:
    """Tests for get_updates method."""

    @pytest.fixture
    def updates_api(self, mock_session):
        """Create an UpdatesAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return UpdatesAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_updates_returns_raw_response(self, updates_api, mock_session):
        """Test get_updates returns raw response."""
        updates_data = {"available": True, "current_version": "6.15.0"}
        mock_response = create_mock_response(200, api_success_response(updates_data))
        mock_session.request.return_value = mock_response

        result = await updates_api.get_updates("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_updates_not_authenticated(self, updates_api):
        """Test get_updates raises when not authenticated."""
        updates_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await updates_api.get_updates("network_123")
