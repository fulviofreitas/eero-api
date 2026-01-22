"""Tests for ThreadAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.thread import ThreadAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestThreadAPIInit:
    """Tests for ThreadAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = ThreadAPI(auth_api)
        assert api._auth_api is auth_api


class TestThreadAPIGetThread:
    """Tests for get_thread method."""

    @pytest.fixture
    def thread_api(self, mock_session):
        """Create a ThreadAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return ThreadAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_thread_returns_raw_response(self, thread_api, mock_session):
        """Test get_thread returns raw response."""
        thread_data = {"enabled": True, "devices": []}
        mock_response = create_mock_response(200, api_success_response(thread_data))
        mock_session.request.return_value = mock_response

        result = await thread_api.get_thread("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_thread_not_authenticated(self, thread_api):
        """Test get_thread raises when not authenticated."""
        thread_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await thread_api.get_thread("network_123")
