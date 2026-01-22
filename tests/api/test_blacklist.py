"""Tests for BlacklistAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.blacklist import BlacklistAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestBlacklistAPIInit:
    """Tests for BlacklistAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = BlacklistAPI(auth_api)
        assert api._auth_api is auth_api


class TestBlacklistAPIGetBlacklist:
    """Tests for get_blacklist method."""

    @pytest.fixture
    def blacklist_api(self, mock_session):
        """Create a BlacklistAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return BlacklistAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_blacklist_returns_raw_response(self, blacklist_api, mock_session):
        """Test get_blacklist returns raw response."""
        blacklist_data = [{"device_id": "device123", "mac": "AA:BB:CC:DD:EE:FF"}]
        mock_response = create_mock_response(200, api_success_response(blacklist_data))
        mock_session.request.return_value = mock_response

        result = await blacklist_api.get_blacklist("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_blacklist_not_authenticated(self, blacklist_api):
        """Test get_blacklist raises when not authenticated."""
        blacklist_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await blacklist_api.get_blacklist("network_123")


class TestBlacklistAPIAddToBlacklist:
    """Tests for add_to_blacklist method."""

    @pytest.fixture
    def blacklist_api(self, mock_session):
        """Create a BlacklistAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return BlacklistAPI(auth_api)

    @pytest.mark.asyncio
    async def test_add_to_blacklist_returns_raw_response(self, blacklist_api, mock_session):
        """Test add_to_blacklist returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await blacklist_api.add_to_blacklist("network_123", "device123")

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_add_to_blacklist_not_authenticated(self, blacklist_api):
        """Test add_to_blacklist raises when not authenticated."""
        blacklist_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await blacklist_api.add_to_blacklist("network_123", "device123")


class TestBlacklistAPIRemoveFromBlacklist:
    """Tests for remove_from_blacklist method."""

    @pytest.fixture
    def blacklist_api(self, mock_session):
        """Create a BlacklistAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return BlacklistAPI(auth_api)

    @pytest.mark.asyncio
    async def test_remove_from_blacklist_returns_raw_response(self, blacklist_api, mock_session):
        """Test remove_from_blacklist returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await blacklist_api.remove_from_blacklist("network_123", "device123")

        assert "meta" in result
