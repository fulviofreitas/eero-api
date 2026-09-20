"""Tests for EventsAPI module.

Tests cover:
- Getting app events, network scan, and channel utilization (raw responses)
- Optional query parameters omitted when not supplied
- band/granularity/busy_threshold validation on channel utilization
- Parent-link (network self-url) preference for one method
- Not-authenticated handling on every method
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.events import CHANNEL_UTILIZATION_BANDS, EventsAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def events_api(mock_session):
    """Create an EventsAPI with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return EventsAPI(auth_api)


class TestEventsAPIInit:
    """Tests for EventsAPI initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = EventsAPI(auth_api)

        assert api._auth_api is auth_api


class TestEventsAPIGetAppEvents:
    """Tests for get_app_events method."""

    @pytest.mark.asyncio
    async def test_get_app_events_sends_query_params(self, events_api, mock_session):
        """Test get_app_events GETs app_events with page_size/timestamp."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"events": []})
        )

        await events_api.get_app_events("network_123", page_size=10, timestamp="ts_1")

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/app_events")
        assert call_args.kwargs["params"] == {"page_size": "10", "timestamp": "ts_1"}

    @pytest.mark.asyncio
    async def test_get_app_events_omits_unsupplied_params(self, events_api, mock_session):
        """Test get_app_events sends no query params when none are supplied."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await events_api.get_app_events("network_123")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["params"] == {}

    @pytest.mark.asyncio
    async def test_get_app_events_prefers_parent_self_url(self, events_api, mock_session):
        """Test get_app_events uses the parent's own url over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"url": "/2.3/networks/network_123"}

        await events_api.get_app_events("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/app_events")

    @pytest.mark.asyncio
    async def test_get_app_events_not_authenticated(self, events_api):
        """Test get_app_events raises when not authenticated."""
        events_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await events_api.get_app_events("network_123")


class TestEventsAPIGetNetworkScan:
    """Tests for get_network_scan method."""

    @pytest.mark.asyncio
    async def test_get_network_scan_returns_raw_response(self, events_api, mock_session):
        """Test get_network_scan GETs the network_scan path."""
        mock_session.request.return_value = create_mock_response(
            200, api_success_response({"scan": []})
        )

        result = await events_api.get_network_scan("network_123")

        assert result["data"]["scan"] == []
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/network_scan")

    @pytest.mark.asyncio
    async def test_get_network_scan_not_authenticated(self, events_api):
        """Test get_network_scan raises when not authenticated."""
        events_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await events_api.get_network_scan("network_123")


class TestEventsAPIGetChannelUtilization:
    """Tests for get_channel_utilization method."""

    @pytest.mark.asyncio
    async def test_get_channel_utilization_required_params_only(self, events_api, mock_session):
        """Test get_channel_utilization sends only start/end when nothing else is given."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await events_api.get_channel_utilization(
            "network_123", start="2026-01-01T00:00:00Z", end="2026-01-02T00:00:00Z"
        )

        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/channel_utilization")
        assert call_args.kwargs["params"] == {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
        }

    @pytest.mark.asyncio
    async def test_get_channel_utilization_sends_all_optional_params(
        self, events_api, mock_session
    ):
        """Test get_channel_utilization sends every optional query parameter when given."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await events_api.get_channel_utilization(
            "network_123",
            start="2026-01-01T00:00:00Z",
            end="2026-01-02T00:00:00Z",
            busy_threshold=5,
            eero_id=42,
            band="band_5GHz_low",
            granularity=5,
            gap_data_placeholder=-1,
        )

        call_args = mock_session.request.call_args
        assert call_args.kwargs["params"] == {
            "start": "2026-01-01T00:00:00Z",
            "end": "2026-01-02T00:00:00Z",
            "busy_threshold": "5",
            "eero_id": "42",
            "band": "band_5GHz_low",
            "granularity": "5",
            "gap_data_placeholder": "-1",
        }

    @pytest.mark.asyncio
    @pytest.mark.parametrize("band", CHANNEL_UTILIZATION_BANDS)
    async def test_get_channel_utilization_accepts_every_valid_band(
        self, events_api, mock_session, band
    ):
        """Test get_channel_utilization accepts every declared band value."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await events_api.get_channel_utilization("network_123", start="s", end="e", band=band)

        call_args = mock_session.request.call_args
        assert call_args.kwargs["params"]["band"] == band

    @pytest.mark.asyncio
    async def test_get_channel_utilization_rejects_invalid_band(self, events_api):
        """Test get_channel_utilization rejects a band outside the declared enum."""
        with pytest.raises(EeroValidationException, match="band"):
            await events_api.get_channel_utilization(
                "network_123", start="s", end="e", band="not_a_band"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("granularity", [0, -1, 1.5, "5"])
    async def test_get_channel_utilization_rejects_invalid_granularity(
        self, events_api, granularity
    ):
        """Test get_channel_utilization rejects non-positive-int granularity."""
        with pytest.raises(EeroValidationException, match="granularity"):
            await events_api.get_channel_utilization(
                "network_123", start="s", end="e", granularity=granularity
            )

    @pytest.mark.asyncio
    async def test_get_channel_utilization_rejects_invalid_busy_threshold(self, events_api):
        """Test get_channel_utilization rejects a non-positive-int busy_threshold."""
        with pytest.raises(EeroValidationException, match="busy_threshold"):
            await events_api.get_channel_utilization(
                "network_123", start="s", end="e", busy_threshold=-1
            )

    @pytest.mark.asyncio
    async def test_get_channel_utilization_prefers_parent_self_url(self, events_api, mock_session):
        """Test get_channel_utilization uses the parent's own url over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"url": "/2.3/networks/network_123"}

        await events_api.get_channel_utilization("network_123", start="s", end="e", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/channel_utilization")

    @pytest.mark.asyncio
    async def test_get_channel_utilization_not_authenticated(self, events_api):
        """Test get_channel_utilization raises when not authenticated."""
        events_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await events_api.get_channel_utilization("network_123", start="s", end="e")
