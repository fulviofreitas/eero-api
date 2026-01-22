"""Tests for OUICheckAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.ouicheck import OUICheckAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


class TestOUICheckAPIInit:
    """Tests for OUICheckAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        api = OUICheckAPI(auth_api)
        assert api._auth_api is auth_api


class TestOUICheckAPIGetOUICheck:
    """Tests for get_ouicheck method."""

    @pytest.fixture
    def ouicheck_api(self, mock_session):
        """Create an OUICheckAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return OUICheckAPI(auth_api)

    @pytest.mark.asyncio
    async def test_get_ouicheck_returns_raw_response(self, ouicheck_api, mock_session):
        """Test get_ouicheck returns raw response."""
        oui_data = {"vendor": "Apple", "mac": "AA:BB:CC:DD:EE:FF"}
        mock_response = create_mock_response(200, api_success_response(oui_data))
        mock_session.request.return_value = mock_response

        result = await ouicheck_api.get_ouicheck("network_123")

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_ouicheck_not_authenticated(self, ouicheck_api):
        """Test get_ouicheck raises when not authenticated."""
        ouicheck_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await ouicheck_api.get_ouicheck("network_123")


class TestOUICheckAPIRunOUICheck:
    """Tests for run_ouicheck method."""

    @pytest.fixture
    def ouicheck_api(self, mock_session):
        """Create an OUICheckAPI with mocked auth."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token")
        return OUICheckAPI(auth_api)

    @pytest.mark.asyncio
    async def test_run_ouicheck_returns_raw_response(self, ouicheck_api, mock_session):
        """Test run_ouicheck returns raw response."""
        mock_response = create_mock_response(200, {"meta": {"code": 200}, "data": {}})
        mock_session.request.return_value = mock_response

        result = await ouicheck_api.run_ouicheck("network_123")

        assert "meta" in result
