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

    @pytest.mark.asyncio
    async def test_create_burst_reporter_uses_default_template(self, burst_api, mock_session):
        """Test create_burst_reporter builds the URL from the template with no parent."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await burst_api.create_burst_reporter("network_123", {"type": "burst"})

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.2/networks/network_123/burst_reporters")
        assert call_args.kwargs["json"] == {"type": "burst"}

    @pytest.mark.asyncio
    async def test_create_burst_reporter_prefers_parent_link(self, burst_api, mock_session):
        """Test create_burst_reporter uses the network's published burst_reporters link."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"burst_reporters": "/2.3/networks/network_123/burst_reporters"}}

        await burst_api.create_burst_reporter("network_123", {"type": "burst"}, parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/burst_reporters")
