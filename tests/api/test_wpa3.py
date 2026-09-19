"""Tests for Wpa3API module.

Tests cover:
- get_wpa3_per_band: verified read, parent-link preference
- set_wpa3_per_band: mode validation, only-given-keys, the uncharacterised-
  write warning, no-field rejection
- Not-authenticated errors on every method
"""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.wpa3 import Wpa3API
from eero.exceptions import EeroAuthenticationException, EeroValidationException

from .conftest import api_success_response, create_mock_response


@pytest.fixture
def wpa3_api(mock_session):
    """Create a Wpa3API with mocked auth."""
    auth_api = MagicMock()
    auth_api.session = mock_session
    auth_api.get_auth_token = AsyncMock(return_value="auth_token")
    return Wpa3API(auth_api)


class TestWpa3APIInit:
    """Tests for Wpa3API initialization."""

    def test_init_with_auth_api(self, mock_session):
        """Test initialization with AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session

        api = Wpa3API(auth_api)

        assert api._auth_api is auth_api


class TestWpa3APIGetWpa3PerBand:
    """Tests for get_wpa3_per_band method."""

    @pytest.mark.asyncio
    async def test_get_wpa3_per_band_returns_raw_response(self, wpa3_api, mock_session):
        """Test get_wpa3_per_band GETs the wpa3_per_band sub-resource."""
        expected = {"band_2_4_ghz": "WPA2_WPA3", "band_5_ghz": "WPA3", "band_6_ghz": "WPA3"}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(expected)
        )

        result = await wpa3_api.get_wpa3_per_band("network_123")

        assert result["data"] == expected
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "GET"
        assert call_args.args[1].endswith("/2.2/networks/network_123/wpa3_per_band")

    @pytest.mark.asyncio
    async def test_get_wpa3_per_band_prefers_parent_link(self, wpa3_api, mock_session):
        """Test get_wpa3_per_band uses the published link over the template."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))
        parent = {"resources": {"wpa3_per_band": "/2.3/networks/network_123/wpa3_per_band"}}

        await wpa3_api.get_wpa3_per_band("network_123", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/wpa3_per_band")

    @pytest.mark.asyncio
    async def test_get_wpa3_per_band_not_authenticated(self, wpa3_api):
        """Test get_wpa3_per_band raises when not authenticated."""
        wpa3_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await wpa3_api.get_wpa3_per_band("network_123")


class TestWpa3APISetWpa3PerBand:
    """Tests for set_wpa3_per_band method."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mode", ["WPA2", "WPA2_WPA3", "WPA3"])
    async def test_set_wpa3_per_band_sends_only_given_band(
        self, wpa3_api, mock_session, caplog, mode
    ):
        """Test set_wpa3_per_band PUTs only the supplied band and warns."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        with caplog.at_level(logging.WARNING):
            result = await wpa3_api.set_wpa3_per_band("network_123", band_2_4_ghz=mode)

        assert "meta" in result
        call_args = mock_session.request.call_args
        assert call_args.args[0] == "PUT"
        assert call_args.args[1].endswith("/2.2/networks/network_123/wpa3_per_band")
        assert call_args.kwargs["json"] == {"band_2_4_ghz": mode}
        assert any("set per-band WPA3 mode for network" in message for message in caplog.messages)

    @pytest.mark.asyncio
    async def test_set_wpa3_per_band_sends_both_bands(self, wpa3_api, mock_session):
        """Test set_wpa3_per_band PUTs both bands when both are supplied."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )

        await wpa3_api.set_wpa3_per_band("network_123", band_2_4_ghz="WPA2_WPA3", band_5_ghz="WPA3")

        call_args = mock_session.request.call_args
        assert call_args.kwargs["json"] == {"band_2_4_ghz": "WPA2_WPA3", "band_5_ghz": "WPA3"}

    @pytest.mark.asyncio
    async def test_set_wpa3_per_band_rejects_invalid_mode(self, wpa3_api):
        """Test set_wpa3_per_band rejects an undeclared mode value."""
        with pytest.raises(EeroValidationException):
            await wpa3_api.set_wpa3_per_band("network_123", band_2_4_ghz="wpa3")

    @pytest.mark.asyncio
    async def test_set_wpa3_per_band_rejects_no_fields(self, wpa3_api):
        """Test set_wpa3_per_band rejects a call with no band supplied."""
        with pytest.raises(EeroValidationException):
            await wpa3_api.set_wpa3_per_band("network_123")

    @pytest.mark.asyncio
    async def test_set_wpa3_per_band_prefers_parent_link(self, wpa3_api, mock_session):
        """Test set_wpa3_per_band uses the published link over the template."""
        mock_session.request.return_value = create_mock_response(
            200, {"meta": {"code": 200}, "data": {}}
        )
        parent = {"resources": {"wpa3_per_band": "/2.3/networks/network_123/wpa3_per_band"}}

        await wpa3_api.set_wpa3_per_band("network_123", band_5_ghz="WPA3", parent=parent)

        call_args = mock_session.request.call_args
        assert call_args.args[1].endswith("/2.3/networks/network_123/wpa3_per_band")

    @pytest.mark.asyncio
    async def test_set_wpa3_per_band_not_authenticated(self, wpa3_api):
        """Test set_wpa3_per_band raises when not authenticated."""
        wpa3_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException):
            await wpa3_api.set_wpa3_per_band("network_123", band_5_ghz="WPA3")
