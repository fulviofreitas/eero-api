"""Tests for BurstReportersAPI module."""

import logging
import warnings
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

    @pytest.fixture
    def ok_response(self, mock_session):
        """Queue a generic success response on the mocked session."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

    @pytest.mark.asyncio
    async def test_no_data_sends_empty_json_string_body(self, burst_api, mock_session, ok_response):
        """Test the request body is the two-character string "" with a JSON content type."""
        await burst_api.create_burst_reporter("network_123")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.kwargs["data"] == '""'
        assert "json" not in call_args.kwargs
        assert call_args.kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_no_data_does_not_emit_deprecation_warning(
        self, burst_api, mock_session, ok_response
    ):
        """Test omitting reporter_data emits no DeprecationWarning."""
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            await burst_api.create_burst_reporter("network_123")

    @pytest.mark.asyncio
    async def test_data_is_forwarded_as_json_and_deprecated(
        self, burst_api, mock_session, ok_response
    ):
        """Test a non-empty reporter_data is forwarded as json= with a DeprecationWarning."""
        with pytest.warns(DeprecationWarning, match="9.0.0"):
            await burst_api.create_burst_reporter("network_123", {"type": "burst"})

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"type": "burst"}
        assert "data" not in call_args.kwargs

    @pytest.mark.asyncio
    async def test_empty_data_sends_empty_json_string_and_deprecated(
        self, burst_api, mock_session, ok_response
    ):
        """Test an empty reporter_data sends the "" body and still warns."""
        with pytest.warns(DeprecationWarning, match="9.0.0"):
            await burst_api.create_burst_reporter("network_123", {})

        call_args = mock_session.request.call_args
        assert call_args.kwargs["data"] == '""'
        assert "json" not in call_args.kwargs
        assert call_args.kwargs["headers"]["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_deprecation_warning_points_at_caller(self, burst_api, ok_response):
        """Test the DeprecationWarning is attributed to the calling module."""
        with pytest.warns(DeprecationWarning) as record:
            await burst_api.create_burst_reporter("network_123", {"type": "burst"})

        assert record[0].filename == __file__

    @pytest.mark.asyncio
    async def test_uses_default_template(self, burst_api, mock_session, ok_response):
        """Test the URL is built from the template with no parent."""
        await burst_api.create_burst_reporter("network_123")

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.2/networks/network_123/burst_reporters")

    @pytest.mark.asyncio
    async def test_prefers_parent_link(self, burst_api, mock_session, ok_response):
        """Test the network's published burst_reporters link wins over the template."""
        parent = {"resources": {"burst_reporters": "/2.3/networks/network_123/burst_reporters"}}

        await burst_api.create_burst_reporter("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/burst_reporters")

    @pytest.mark.asyncio
    async def test_next_burst_envelope_passes_through(self, burst_api, mock_session):
        """Test the next_burst response envelope is returned unchanged."""
        envelope = {"meta": {"code": 200}, "data": {"next_burst": "2026-10-17T10:00:00Z"}}
        mock_session.request.return_value = create_mock_response(200, envelope)

        result = await burst_api.create_burst_reporter("network_123")

        assert result == envelope

    @pytest.mark.asyncio
    async def test_does_not_warn_as_uncharacterised(
        self, burst_api, mock_session, ok_response, caplog
    ):
        """Test the live-verified write (2026-10-20) no longer logs the uncharacterised warning."""
        with caplog.at_level(logging.WARNING):
            await burst_api.create_burst_reporter("network_123")

        assert not any("not been fully characterised" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_deprecated_body_still_warns_as_uncharacterised(
        self, burst_api, mock_session, ok_response, caplog
    ):
        """Test a non-empty reporter_data body keeps the warning: only the "" body was verified."""
        with caplog.at_level(logging.WARNING), pytest.warns(DeprecationWarning):
            await burst_api.create_burst_reporter("network_123", {"type": "burst"})

        assert any(
            "request live-usage burst with a deprecated body for network" in m
            and "not been fully characterised" in m
            for m in caplog.messages
        )
        assert not any("network_123" in m for m in caplog.messages if "characterised" in m)

    @pytest.mark.asyncio
    async def test_not_authenticated(self, burst_api, mock_session):
        """Test create_burst_reporter raises before any request when not authenticated."""
        burst_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await burst_api.create_burst_reporter("network_123")

        mock_session.request.assert_not_called()
