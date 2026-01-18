"""Tests for BaseAPI and AuthenticatedAPI classes.

Tests cover:
- HTTP method wrappers (GET, POST, PUT, DELETE)
- Error handling for various HTTP status codes
- Async context manager lifecycle
- Request timeout handling
- URL construction
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from eero.api.base import AuthenticatedAPI, BaseAPI
from eero.exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroNetworkException,
    EeroRateLimitException,
    EeroTimeoutException,
)

from .conftest import api_success_response, create_mock_response


class TestBaseAPI:
    """Tests for BaseAPI class."""

    def test_init_without_session(self):
        """Test initialization without a session."""
        api = BaseAPI(base_url="https://api.example.com")

        assert api._session is None
        assert api._base_url == "https://api.example.com"
        assert api._should_close_session is False

    def test_init_with_session(self, mock_session):
        """Test initialization with an existing session."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")

        assert api._session is mock_session
        assert api._should_close_session is False

    @pytest.mark.asyncio
    async def test_context_manager_creates_session(self):
        """Test that entering context creates a session if none provided."""
        api = BaseAPI(base_url="https://api.example.com")

        with patch("eero.api.base.ClientSession") as mock_client_session:
            mock_session_instance = MagicMock()
            mock_client_session.return_value = mock_session_instance

            await api.__aenter__()

            mock_client_session.assert_called_once()
            assert api._session is mock_session_instance
            assert api._should_close_session is True

    @pytest.mark.asyncio
    async def test_context_manager_uses_existing_session(self, mock_session):
        """Test that entering context uses existing session."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")

        result = await api.__aenter__()

        assert result is api
        assert api._session is mock_session
        assert api._should_close_session is False

    @pytest.mark.asyncio
    async def test_context_manager_closes_created_session(self):
        """Test that exiting context closes session if we created it."""
        api = BaseAPI(base_url="https://api.example.com")

        with patch("eero.api.base.ClientSession") as mock_client_session:
            mock_session_instance = MagicMock()
            mock_session_instance.close = AsyncMock()
            mock_client_session.return_value = mock_session_instance

            await api.__aenter__()
            await api.__aexit__(None, None, None)

            mock_session_instance.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_context_manager_does_not_close_provided_session(self, mock_session):
        """Test that exiting context does not close provided session."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")

        await api.__aenter__()
        await api.__aexit__(None, None, None)

        mock_session.close.assert_not_awaited()

    def test_session_property_raises_without_context(self):
        """Test that session property raises if not in context."""
        api = BaseAPI(base_url="https://api.example.com")

        with pytest.raises(RuntimeError, match="ClientSession not initialized"):
            _ = api.session

    def test_session_property_returns_session(self, mock_session):
        """Test that session property returns the session."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")

        assert api.session is mock_session


class TestBaseAPIRequests:
    """Tests for BaseAPI HTTP request methods."""

    @pytest.fixture
    def api_with_session(self, mock_session):
        """Create a BaseAPI with a mock session."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")
        return api

    @pytest.mark.asyncio
    async def test_get_request_success(self, api_with_session, mock_session):
        """Test successful GET request."""
        expected_data = {"key": "value"}
        mock_response = create_mock_response(200, api_success_response(expected_data))
        mock_session.request.return_value = mock_response

        result = await api_with_session.get("/endpoint")

        assert result["data"] == expected_data
        mock_session.request.assert_called_once()
        call_args = mock_session.request.call_args
        assert call_args[0] == ("GET", "https://api.example.com/endpoint")

    @pytest.mark.asyncio
    async def test_post_request_success(self, api_with_session, mock_session):
        """Test successful POST request."""
        expected_data = {"created": True}
        mock_response = create_mock_response(200, api_success_response(expected_data))
        mock_session.request.return_value = mock_response

        result = await api_with_session.post("/endpoint", json={"name": "test"})

        assert result["data"] == expected_data

    @pytest.mark.asyncio
    async def test_put_request_success(self, api_with_session, mock_session):
        """Test successful PUT request."""
        expected_data = {"updated": True}
        mock_response = create_mock_response(200, api_success_response(expected_data))
        mock_session.request.return_value = mock_response

        result = await api_with_session.put("/endpoint", json={"name": "updated"})

        assert result["data"] == expected_data

    @pytest.mark.asyncio
    async def test_delete_request_success(self, api_with_session, mock_session):
        """Test successful DELETE request."""
        expected_data = {"deleted": True}
        mock_response = create_mock_response(200, api_success_response(expected_data))
        mock_session.request.return_value = mock_response

        result = await api_with_session.delete("/endpoint")

        assert result["data"] == expected_data

    @pytest.mark.asyncio
    async def test_request_with_auth_token(self, api_with_session, mock_session):
        """Test that auth token is added to cookies."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        await api_with_session.get("/endpoint", auth_token="test_token")

        mock_session.cookie_jar.update_cookies.assert_called_with({"s": "test_token"})

    @pytest.mark.asyncio
    async def test_request_with_full_url(self, api_with_session, mock_session):
        """Test request with full URL (not relative path)."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        await api_with_session.get("https://other.api.com/endpoint")

        call_args = mock_session.request.call_args
        assert call_args[0] == ("GET", "https://other.api.com/endpoint")


class TestBaseAPIErrorHandling:
    """Tests for BaseAPI error handling."""

    @pytest.fixture
    def api_with_session(self, mock_session):
        """Create a BaseAPI with a mock session."""
        return BaseAPI(session=mock_session, base_url="https://api.example.com")

    @pytest.mark.asyncio
    async def test_401_raises_authentication_exception(self, api_with_session, mock_session):
        """Test that 401 status raises EeroAuthenticationException."""
        mock_response = create_mock_response(401, None, "Unauthorized")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAuthenticationException, match="Authentication failed"):
            await api_with_session.get("/endpoint")

    @pytest.mark.asyncio
    async def test_404_raises_api_exception(self, api_with_session, mock_session):
        """Test that 404 status raises EeroAPIException."""
        mock_response = create_mock_response(404, None, "Not found")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException) as exc_info:
            await api_with_session.get("/endpoint")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_exception(self, api_with_session, mock_session):
        """Test that 429 status raises EeroRateLimitException."""
        mock_response = create_mock_response(429, None, "Too Many Requests")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroRateLimitException, match="Rate limit exceeded"):
            await api_with_session.get("/endpoint")

    @pytest.mark.asyncio
    async def test_500_raises_api_exception(self, api_with_session, mock_session):
        """Test that 500 status raises EeroAPIException."""
        mock_response = create_mock_response(500, None, "Internal Server Error")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException) as exc_info:
            await api_with_session.get("/endpoint")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_timeout_raises_timeout_exception(self, api_with_session, mock_session):
        """Test that timeout raises EeroTimeoutException."""
        mock_session.request.side_effect = asyncio.TimeoutError()

        with pytest.raises(EeroTimeoutException, match="Request timed out"):
            await api_with_session.get("/endpoint")

    @pytest.mark.asyncio
    async def test_client_error_raises_network_exception(self, api_with_session, mock_session):
        """Test that client errors raise EeroNetworkException."""
        mock_session.request.side_effect = aiohttp.ClientError("Connection failed")

        with pytest.raises(EeroNetworkException, match="Network error"):
            await api_with_session.get("/endpoint")

    @pytest.mark.asyncio
    async def test_invalid_json_raises_api_exception(self, api_with_session, mock_session):
        """Test that invalid JSON response raises EeroAPIException."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.text = AsyncMock(return_value="not valid json")
        mock_response.json = AsyncMock(side_effect=Exception("Invalid JSON"))
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException, match="Invalid JSON"):
            await api_with_session.get("/endpoint")


class TestAuthenticatedAPI:
    """Tests for AuthenticatedAPI class."""

    @pytest.fixture
    def mock_auth_api(self, mock_session):
        """Create a mock AuthAPI."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.get_auth_token = AsyncMock(return_value="auth_token_123")
        return auth_api

    def test_init_delegates_session_to_auth_api(self, mock_auth_api):
        """Test that AuthenticatedAPI delegates session to AuthAPI."""
        api = AuthenticatedAPI(mock_auth_api, base_url="https://api.example.com")

        assert api._auth_api is mock_auth_api
        assert api.session is mock_auth_api.session

    def test_session_property_returns_auth_api_session(self, mock_auth_api, mock_session):
        """Test that session property delegates to auth API."""
        api = AuthenticatedAPI(mock_auth_api, base_url="https://api.example.com")

        result = api.session

        assert result is mock_session
