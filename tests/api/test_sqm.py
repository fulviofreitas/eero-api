"""Tests for SqmAPI module (Smart Queue Management).

Tests cover:
- Getting SQM settings (raw response)
- Enabling/disabling SQM
- Setting bandwidth limits
- Configuring SQM
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.sqm import SqmAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestSqmAPIInit:
    """Tests for SqmAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = SqmAPI(auth_api)

        assert api._auth_api is auth_api


class TestSqmAPIGetSettings:
    """Tests for get_sqm_settings method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_sqm_settings_returns_raw_response(self, sqm_api, mock_session):
        """Test getting SQM settings returns raw response."""
        network_data = {
            "sqm": {
                "enabled": True,
                "upload_bandwidth": 100,
                "download_bandwidth": 500,
            },
        }
        mock_response = create_mock_response(200, api_success_response(network_data))
        mock_session.request.return_value = mock_response

        result = await sqm_api.get_sqm_settings("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_sqm_settings_not_authenticated(self, sqm_api):
        """Test get_sqm_settings raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await sqm_api.get_sqm_settings("network_123")


class TestSqmAPISetEnabled:
    """Tests for set_sqm_enabled method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_enable_sqm_returns_raw_response(self, sqm_api, mock_session):
        """Test enabling SQM returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_enabled("network_123", True)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"sqm": {"enabled": True}}

    @pytest.mark.asyncio
    async def test_set_sqm_enabled_not_authenticated(self, sqm_api):
        """Test set_sqm_enabled raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.set_sqm_enabled("network_123", True)


class TestSqmAPISetBandwidth:
    """Tests for set_sqm_bandwidth method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_upload_bandwidth_returns_raw_response(self, sqm_api, mock_session):
        """Test setting upload bandwidth returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_bandwidth("network_123", upload_mbps=50)

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["enabled"] is True
        assert payload["sqm"]["upload_bandwidth"] == 50

    @pytest.mark.asyncio
    async def test_set_both_bandwidths_returns_raw_response(self, sqm_api, mock_session):
        """Test setting both bandwidths returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_bandwidth("network_123", upload_mbps=100, download_mbps=500)

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["upload_bandwidth"] == 100
        assert payload["sqm"]["download_bandwidth"] == 500

    @pytest.mark.asyncio
    async def test_set_sqm_bandwidth_not_authenticated(self, sqm_api):
        """Test set_sqm_bandwidth raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.set_sqm_bandwidth("network_123", upload_mbps=50)


class TestSqmAPIConfigure:
    """Tests for configure_sqm method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_configure_sqm_returns_raw_response(self, sqm_api, mock_session):
        """Test configuring SQM returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.configure_sqm(
            "network_123",
            enabled=True,
            upload_mbps=100,
            download_mbps=500,
        )

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["enabled"] is True

    @pytest.mark.asyncio
    async def test_configure_sqm_not_authenticated(self, sqm_api):
        """Test configure_sqm raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.configure_sqm("network_123", enabled=True)


class TestSqmAPISetAuto:
    """Tests for set_sqm_auto method."""

    @pytest.fixture
    def sqm_api(self, mock_session):
        """Create a SqmAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return SqmAPI(auth_api)

    @pytest.mark.asyncio
    async def test_set_sqm_auto_returns_raw_response(self, sqm_api, mock_session):
        """Test setting SQM to auto returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await sqm_api.set_sqm_auto("network_123")

        assert "meta" in result
        call_args = mock_session.request.call_args
        payload = call_args.kwargs["json"]
        assert payload["sqm"]["mode"] == "auto"

    @pytest.mark.asyncio
    async def test_set_sqm_auto_not_authenticated(self, sqm_api):
        """Test set_sqm_auto raises when not authenticated."""
        sqm_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await sqm_api.set_sqm_auto("network_123")
