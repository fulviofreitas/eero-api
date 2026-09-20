"""Tests for DiagnosticsAPI module.

Tests cover:
- Getting diagnostics results (raw response, via the diagnostics link)
- Running diagnostics with exactly the supplied device/symptom keys
- id/path/URL polymorphism and parent-link preference
- The uncharacterised-write warning
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.diagnostics import DiagnosticsAPI
from eero.exceptions import EeroAuthenticationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def diagnostics_api(mock_session):
    """Create a DiagnosticsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return DiagnosticsAPI(auth_api)


class TestDiagnosticsAPIInit:
    """Tests for DiagnosticsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = DiagnosticsAPI(auth_api)

        assert api._auth_api is auth_api


class TestDiagnosticsAPIGetDiagnostics:
    """Tests for get_diagnostics method."""

    @pytest.mark.asyncio
    async def test_get_diagnostics_uses_default_template(self, diagnostics_api, mock_session):
        """Test get_diagnostics GETs the diagnostics link built from the template."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"status": "ok"})
        )

        result = await diagnostics_api.get_diagnostics("network_123")

        assert result["data"]["status"] == "ok"
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/diagnostics")

    @pytest.mark.asyncio
    async def test_get_diagnostics_prefers_parent_link(self, diagnostics_api, mock_session):
        """Test get_diagnostics uses the network's published diagnostics link."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"status": "ok"})
        )
        parent = {"resources": {"diagnostics": "/2.3/networks/network_123/diagnostics"}}

        await diagnostics_api.get_diagnostics("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/diagnostics")

    @pytest.mark.asyncio
    async def test_get_diagnostics_not_authenticated(self, diagnostics_api):
        """Test get_diagnostics raises when not authenticated."""
        diagnostics_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await diagnostics_api.get_diagnostics("network_123")


class TestDiagnosticsAPIRunDiagnostics:
    """Tests for run_diagnostics method."""

    @pytest.mark.asyncio
    async def test_run_diagnostics_sends_empty_object_with_no_args(
        self, diagnostics_api, mock_session, caplog
    ):
        """Test run_diagnostics POSTs an empty JSON object when neither field is given."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await diagnostics_api.run_diagnostics("network_123")

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1].endswith("/2.2/networks/network_123/diagnostics")
        assert call_args.kwargs["json"] == {}
        assert any("run diagnostics for network" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_run_diagnostics_sends_only_supplied_keys(self, diagnostics_api, mock_session):
        """Test run_diagnostics POSTs exactly the device/symptom keys supplied."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await diagnostics_api.run_diagnostics("network_123", device="eero_001", symptom="slow_wifi")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"device": "eero_001", "symptom": "slow_wifi"}

    @pytest.mark.asyncio
    async def test_run_diagnostics_not_authenticated(self, diagnostics_api):
        """Test run_diagnostics raises when not authenticated."""
        diagnostics_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await diagnostics_api.run_diagnostics("network_123")
