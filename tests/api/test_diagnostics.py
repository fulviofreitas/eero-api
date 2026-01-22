"""Unit tests for the DiagnosticsAPI module."""

from unittest.mock import AsyncMock, patch

import pytest

from eero.api.diagnostics import DiagnosticsAPI
from eero.exceptions import EeroAuthenticationException


class TestDiagnosticsAPIInitialization:
    """Tests for DiagnosticsAPI initialization."""

    def test_initialization_with_auth_api(self, mock_auth_api):
        """Test DiagnosticsAPI initializes with auth API."""
        api = DiagnosticsAPI(mock_auth_api)
        assert api._auth_api == mock_auth_api


class TestGetDiagnostics:
    """Tests for get_diagnostics method."""

    async def test_get_diagnostics_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test get_diagnostics returns raw API response."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        diagnostics_data = {
            "network_health": "good",
            "internet_status": "connected",
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(diagnostics_data)
            result = await api.get_diagnostics("network123")

            assert "meta" in result
            assert "data" in result
            mock_get.assert_called_once_with(
                "networks/network123/diagnostics",
                auth_token="test_token",
            )

    async def test_get_diagnostics_not_authenticated(self, mock_auth_api):
        """Test get_diagnostics raises exception when not authenticated."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_diagnostics("network123")


class TestRunDiagnostics:
    """Tests for run_diagnostics method."""

    async def test_run_diagnostics_returns_raw_response(self, mock_auth_api, mock_api_response):
        """Test run_diagnostics returns raw API response."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        run_result = {
            "status": "completed",
            "started_at": "2024-01-15T10:00:00Z",
        }

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_api_response(run_result)
            result = await api.run_diagnostics("network123")

            assert "meta" in result
            assert "data" in result
            mock_post.assert_called_once_with(
                "networks/network123/diagnostics",
                auth_token="test_token",
                json={},
            )

    async def test_run_diagnostics_not_authenticated(self, mock_auth_api):
        """Test run_diagnostics raises exception when not authenticated."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.run_diagnostics("network123")
