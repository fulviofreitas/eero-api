"""Tests for OUICheckAPI module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from eero.api.ouicheck import OUICheckAPI
from eero.exceptions import EeroAuthenticationException, EeroValidationException

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
        oui_data = {"vendor": "ExampleVendor"}
        mock_session.request.return_value = create_mock_response(
            200, api_success_response(oui_data)
        )

        result = await ouicheck_api.get_ouicheck(
            "network_123", serial="serial_example", version="1.0.0-example"
        )

        assert "meta" in result
        assert "data" in result

    @pytest.mark.asyncio
    async def test_get_ouicheck_sends_serial_and_version_query_params(
        self, ouicheck_api, mock_session
    ):
        """Test both required query parameters are sent, and no request body."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await ouicheck_api.get_ouicheck(
            "network_123", serial="serial_example", version="1.0.0-example"
        )

        call_args = mock_session.request.call_args
        assert call_args[0][0] == "GET"
        assert call_args[0][1].endswith("networks/network_123/ouicheck")
        assert call_args[1]["params"] == {
            "serial": "serial_example",
            "version": "1.0.0-example",
        }
        assert "json" not in call_args[1] or call_args[1]["json"] is None

    @pytest.mark.asyncio
    async def test_get_ouicheck_requires_serial_and_version_kwargs(self, ouicheck_api):
        """Test serial and version are required keyword-only arguments."""
        with pytest.raises(TypeError):
            await ouicheck_api.get_ouicheck("network_123")  # type: ignore[call-arg]

        with pytest.raises(TypeError):
            await ouicheck_api.get_ouicheck("network_123", serial="serial_example")  # type: ignore[call-arg]

        with pytest.raises(TypeError):
            await ouicheck_api.get_ouicheck("network_123", version="1.0.0-example")  # type: ignore[call-arg]

    @pytest.mark.parametrize(
        "serial, version",
        [
            ("", "1.0.0-example"),
            ("serial_example", ""),
            (None, "1.0.0-example"),
            ("serial_example", None),
        ],
    )
    @pytest.mark.asyncio
    async def test_get_ouicheck_rejects_empty_or_non_string_values(
        self, ouicheck_api, mock_session, serial, version
    ):
        """Test empty or non-string serial/version is rejected before any request."""
        with pytest.raises(EeroValidationException):
            await ouicheck_api.get_ouicheck("network_123", serial=serial, version=version)
        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_ouicheck_not_authenticated(self, ouicheck_api):
        """Test get_ouicheck raises when not authenticated."""
        ouicheck_api._auth_api.get_auth_token = AsyncMock(return_value=None)

        with pytest.raises(EeroAuthenticationException, match="Not authenticated"):
            await ouicheck_api.get_ouicheck(
                "network_123", serial="serial_example", version="1.0.0-example"
            )
