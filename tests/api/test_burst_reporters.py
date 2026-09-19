"""Tests for BurstReportersAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.burst_reporters import BurstReportersAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import create_mock_response


class TestBurstReportersAPIInit:
    """Tests for BurstReportersAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = BurstReportersAPI(auth_api)
        assert api._auth_api is auth_api


class TestBurstReportersAPICreateReporter:
    """Tests for create_burst_reporter method."""

    @pytest.fixture
    def burst_api(self, mock_session):
        """Create a BurstReportersAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return BurstReportersAPI(auth_api)

    @pytest.mark.asyncio
    async def test_create_burst_reporter_returns_raw_response(self, burst_api, mock_session):
        """Test create_burst_reporter returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        reporter_data = {"type": "burst"}
        result = await burst_api.create_burst_reporter("network_123", reporter_data)

        assert "meta" in result

    @pytest.mark.asyncio
    async def test_create_burst_reporter_not_authenticated(self, burst_api):
        """Test create_burst_reporter raises when not authenticated."""
        burst_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await burst_api.create_burst_reporter("network_123", {})
