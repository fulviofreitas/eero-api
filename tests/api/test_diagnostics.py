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

    async def test_get_diagnostics_success(self, mock_auth_api, mock_api_response):
        """Test successful diagnostics retrieval."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        diagnostics_data = {
            "network_health": "good",
            "internet_status": "connected",
            "latency_ms": 15,
            "packet_loss": 0.0,
            "download_speed": 100.5,
            "upload_speed": 50.2,
        }

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_api_response(diagnostics_data)
            result = await api.get_diagnostics("network123")

            assert result == diagnostics_data
            mock_get.assert_called_once_with(
                "networks/network123/diagnostics",
                auth_token="test_token",
            )

    async def test_get_diagnostics_empty_response(self, mock_auth_api, mock_api_response):
        """Test get_diagnostics returns empty dict for missing data."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        with patch.object(api, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = {}
            result = await api.get_diagnostics("network123")

            assert result == {}

    async def test_get_diagnostics_not_authenticated(self, mock_auth_api):
        """Test get_diagnostics raises exception when not authenticated."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.get_diagnostics("network123")


class TestRunDiagnostics:
    """Tests for run_diagnostics method."""

    async def test_run_diagnostics_success(self, mock_auth_api, mock_api_response):
        """Test successful diagnostics run."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        run_result = {
            "status": "completed",
            "started_at": "2024-01-15T10:00:00Z",
            "completed_at": "2024-01-15T10:00:30Z",
            "results": {
                "internet_connectivity": "pass",
                "dns_resolution": "pass",
                "gateway_ping": "pass",
            },
        }

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_api_response(run_result)
            result = await api.run_diagnostics("network123")

            assert result == run_result
            mock_post.assert_called_once_with(
                "networks/network123/diagnostics",
                auth_token="test_token",
                json={},
            )

    async def test_run_diagnostics_in_progress(self, mock_auth_api, mock_api_response):
        """Test run_diagnostics when diagnostics are in progress."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value="test_token")

        run_result = {
            "status": "in_progress",
            "started_at": "2024-01-15T10:00:00Z",
            "progress": 50,
        }

        with patch.object(api, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_api_response(run_result)
            result = await api.run_diagnostics("network123")

            assert result["status"] == "in_progress"
            assert result["progress"] == 50

    async def test_run_diagnostics_not_authenticated(self, mock_auth_api):
        """Test run_diagnostics raises exception when not authenticated."""
        api = DiagnosticsAPI(mock_auth_api)
        mock_auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await api.run_diagnostics("network123")
