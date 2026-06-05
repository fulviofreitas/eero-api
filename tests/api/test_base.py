"""Tests for BaseAPI and AuthenticatedAPI classes.

Tests cover:
- HTTP method wrappers (GET, POST, PUT, DELETE)
- Error handling for various HTTP status codes
- Async context manager lifecycle
- Request timeout handling
- URL construction
- Response body size enforcement
- Redirect protection (defensive session-cookie hardening)
- Server-driven session refresh (error.session.refresh signal)
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from eero.api.base import AuthenticatedAPI, BaseAPI
from eero.const import MAX_RESPONSE_BYTES
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

    @pytest.mark.asyncio
    async def test_201_created_is_success(self, api_with_session, mock_session):
        """Test that 201 Created is treated as a success response."""
        expected_data = {"meta": {"code": 201}, "data": {"reboot": True}}
        mock_response = create_mock_response(201, expected_data)
        mock_session.request.return_value = mock_response

        result = await api_with_session.post("/eeros/reboot")

        assert result["meta"]["code"] == 201
        assert result["data"]["reboot"] is True

    @pytest.mark.asyncio
    async def test_204_no_content_returns_empty_dict(self, api_with_session, mock_session):
        """Test that 204 No Content returns an empty dict."""
        mock_response = create_mock_response(204, None, "")
        mock_session.request.return_value = mock_response

        result = await api_with_session.delete("/endpoint")

        assert result == {}

    @pytest.mark.asyncio
    async def test_202_accepted_is_success(self, api_with_session, mock_session):
        """Test that 202 Accepted is treated as a success response."""
        expected_data = {"meta": {"code": 202}, "data": {"pending": True}}
        mock_response = create_mock_response(202, expected_data)
        mock_session.request.return_value = mock_response

        result = await api_with_session.post("/async-operation")

        assert result["meta"]["code"] == 202
        assert result["data"]["pending"] is True


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
        mock_response = create_mock_response(200, body_bytes=b"not valid json")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException, match="Invalid JSON"):
            await api_with_session.get("/endpoint")


class TestBaseAPIResponseSizeLimit:
    """Tests for the response body size cap enforced by BaseAPI._request."""

    @pytest.fixture
    def api_with_session(self, mock_session):
        """Create a BaseAPI with a mock session."""
        return BaseAPI(session=mock_session, base_url="https://api.example.com")

    @pytest.mark.asyncio
    async def test_response_under_limit_succeeds(self, api_with_session, mock_session):
        """Test that a response body smaller than MAX_RESPONSE_BYTES succeeds normally."""
        payload = api_success_response({"key": "value"})
        body = json.dumps(payload).encode("utf-8")
        assert len(body) < MAX_RESPONSE_BYTES

        mock_response = create_mock_response(200, payload, body_bytes=body)
        mock_session.request.return_value = mock_response

        result = await api_with_session.get("/endpoint")

        assert result["data"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_response_exactly_at_limit_succeeds(self, api_with_session, mock_session):
        """Test that a response body of exactly MAX_RESPONSE_BYTES succeeds.

        The read call returns MAX_RESPONSE_BYTES + 1 bytes only when there is
        more data than the limit; a body of exactly MAX_RESPONSE_BYTES bytes is
        therefore within the allowed ceiling and must not raise.
        """
        # Build a JSON payload padded to exactly MAX_RESPONSE_BYTES bytes.
        # The padding is added inside the JSON string value so the result is
        # still valid JSON that can be decoded.
        prefix = b'{"meta": {"code": 200}, "data": {"pad": "'
        suffix = b'"}}'
        pad_length = MAX_RESPONSE_BYTES - len(prefix) - len(suffix)
        body = prefix + (b"x" * pad_length) + suffix
        assert len(body) == MAX_RESPONSE_BYTES

        mock_response = create_mock_response(200, body_bytes=body)
        mock_session.request.return_value = mock_response

        result = await api_with_session.get("/endpoint")

        assert result["meta"]["code"] == 200

    @pytest.mark.asyncio
    async def test_response_exceeding_limit_raises_api_exception(
        self, api_with_session, mock_session
    ):
        """Test that a response body larger than MAX_RESPONSE_BYTES raises EeroAPIException.

        The read helper is configured to return MAX_RESPONSE_BYTES + 1 bytes,
        which is the sentinel value that triggers the size-limit guard.
        """
        oversized_bytes = b"x" * (MAX_RESPONSE_BYTES + 1)
        mock_response = create_mock_response(200, body_bytes=oversized_bytes)
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException) as exc_info:
            await api_with_session.get("/endpoint")

        assert f"exceeded max size of {MAX_RESPONSE_BYTES} bytes" in exc_info.value.message


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


# ========================== Redirect Protection Tests ==========================


class TestBaseAPIRedirectProtection:
    """Tests for defensive session-cookie hardening via redirect blocking.

    Any 3xx response received from the upstream API must be refused so that
    the session cookie is never forwarded to an unintended host.
    """

    @pytest.fixture
    def api_with_session(self, mock_session):
        """Create a BaseAPI with a mock session."""
        return BaseAPI(session=mock_session, base_url="https://api-user.e2ro.com/2.2")

    # ---- 301 Moved Permanently ----

    @pytest.mark.asyncio
    async def test_301_with_location_raises_api_exception(self, api_with_session, mock_session):
        """Test that a 301 redirect with a Location header raises EeroAPIException."""
        mock_response = MagicMock()
        mock_response.status = 301
        mock_response.headers = {"Location": "https://evil.example.com/steal"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException) as exc_info:
            await api_with_session.get("/endpoint")

        assert exc_info.value.status_code == 301
        assert "Redirect not followed" in exc_info.value.message

    # ---- 302 Found ----

    @pytest.mark.asyncio
    async def test_302_cross_origin_location_raises_api_exception(
        self, api_with_session, mock_session
    ):
        """Test that a 302 redirect to a foreign host raises EeroAPIException."""
        mock_response = MagicMock()
        mock_response.status = 302
        mock_response.headers = {"Location": "https://evil.example.com/leak"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException) as exc_info:
            await api_with_session.get("/endpoint")

        assert exc_info.value.status_code == 302
        assert "Redirect not followed" in exc_info.value.message
        assert "evil.example.com" in exc_info.value.message

    # ---- 307 Temporary Redirect ----

    @pytest.mark.asyncio
    async def test_307_raises_api_exception(self, api_with_session, mock_session):
        """Test that a 307 redirect raises EeroAPIException."""
        mock_response = MagicMock()
        mock_response.status = 307
        mock_response.headers = {"Location": "https://attacker.net/capture"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException) as exc_info:
            await api_with_session.get("/endpoint")

        assert exc_info.value.status_code == 307
        assert "Redirect not followed" in exc_info.value.message

    # ---- 308 Permanent Redirect ----

    @pytest.mark.asyncio
    async def test_308_raises_api_exception(self, api_with_session, mock_session):
        """Test that a 308 redirect raises EeroAPIException."""
        mock_response = MagicMock()
        mock_response.status = 308
        mock_response.headers = {"Location": "https://attacker.net/capture"}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException) as exc_info:
            await api_with_session.get("/endpoint")

        assert exc_info.value.status_code == 308
        assert "Redirect not followed" in exc_info.value.message

    # ---- 302 with no Location header ----

    @pytest.mark.asyncio
    async def test_302_without_location_raises_api_exception(
        self, api_with_session, mock_session
    ):
        """Test that a 302 with no Location header raises EeroAPIException."""
        mock_response = MagicMock()
        mock_response.status = 302
        mock_response.headers = {}
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=None)
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAPIException) as exc_info:
            await api_with_session.get("/endpoint")

        assert exc_info.value.status_code == 302
        assert "no Location header" in exc_info.value.message

    # ---- allow_redirects default ----

    @pytest.mark.asyncio
    async def test_allow_redirects_defaults_to_false(self, api_with_session, mock_session):
        """Test that allow_redirects=False is passed to the underlying request call."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        await api_with_session.get("/endpoint")

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs.get("allow_redirects") is False

    @pytest.mark.asyncio
    async def test_allow_redirects_caller_override_is_preserved(
        self, api_with_session, mock_session
    ):
        """Test that an explicit allow_redirects value supplied by the caller is not overwritten."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        await api_with_session.get("/endpoint", allow_redirects=True)

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs.get("allow_redirects") is True


# ========================== Server-Driven Session Refresh Tests ==========================


class TestServerDrivenSessionRefresh:
    """Tests for the server-driven session-refresh path in BaseAPI._request.

    The server signals that a session needs refreshing by returning HTTP 401
    with a body containing {"meta": {"error": "error.session.refresh"}}.
    When this signal is received and a _refresh_hook is set, the client should:
    1. Call the hook to refresh the session.
    2. Retry the original request exactly once.
    3. Return the result of the retried request on success.
    4. Raise EeroAuthenticationException if the hook returns False or if
       the retry itself also receives a 401.
    """

    SESSION_REFRESH_BODY = {"meta": {"code": 401, "error": "error.session.refresh"}}

    @pytest.fixture
    def api_with_hook(self, mock_session):
        """Create a BaseAPI with a mock _refresh_hook set."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")
        api._refresh_hook = AsyncMock(return_value=True)
        return api

    @pytest.mark.asyncio
    async def test_401_with_session_refresh_signal_triggers_refresh_and_retry(
        self, api_with_hook, mock_session
    ):
        """First call returns 401+signal; second call succeeds after refresh."""
        success_payload = api_success_response({"ok": True})
        first_response = create_mock_response(401, self.SESSION_REFRESH_BODY)
        second_response = create_mock_response(200, success_payload)
        mock_session.request.side_effect = [first_response, second_response]

        result = await api_with_hook.get("/endpoint")

        assert mock_session.request.call_count == 2
        api_with_hook._refresh_hook.assert_awaited_once()
        assert result["data"] == {"ok": True}

    @pytest.mark.asyncio
    async def test_401_with_session_refresh_signal_but_hook_returns_false_raises(
        self, api_with_hook, mock_session
    ):
        """When the refresh hook returns False, EeroAuthenticationException is raised."""
        api_with_hook._refresh_hook = AsyncMock(return_value=False)
        mock_response = create_mock_response(401, self.SESSION_REFRESH_BODY)
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAuthenticationException, match="Authentication failed"):
            await api_with_hook.get("/endpoint")

        api_with_hook._refresh_hook.assert_awaited_once()
        assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_401_with_session_refresh_signal_does_not_loop_on_second_failure(
        self, api_with_hook, mock_session
    ):
        """Retry that also returns 401+signal must NOT trigger a second refresh.

        The hook is called exactly once; the request is made exactly twice;
        and EeroAuthenticationException is raised from the retry.
        """
        refresh_response = create_mock_response(401, self.SESSION_REFRESH_BODY)
        mock_session.request.side_effect = [refresh_response, refresh_response]

        with pytest.raises(EeroAuthenticationException, match="Authentication failed"):
            await api_with_hook.get("/endpoint")

        assert mock_session.request.call_count == 2
        api_with_hook._refresh_hook.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_401_without_session_refresh_signal_raises_immediately(
        self, mock_session
    ):
        """A plain 401 (no refresh signal) must raise without calling the hook."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")
        hook = AsyncMock(return_value=True)
        api._refresh_hook = hook

        mock_response = create_mock_response(401, None, "Unauthorized")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAuthenticationException, match="Authentication failed"):
            await api.get("/endpoint")

        hook.assert_not_awaited()
        assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_401_without_refresh_hook_raises_immediately(self, mock_session):
        """When _refresh_hook is None, a 401 raises immediately without any retry."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")
        assert api._refresh_hook is None

        mock_response = create_mock_response(401, self.SESSION_REFRESH_BODY)
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAuthenticationException, match="Authentication failed"):
            await api.get("/endpoint")

        assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_401_with_non_json_body_raises_immediately(self, mock_session):
        """A 401 with a non-JSON body falls through cleanly without a retry."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")
        hook = AsyncMock(return_value=True)
        api._refresh_hook = hook

        mock_response = create_mock_response(401, body_bytes=b"not json at all")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAuthenticationException, match="Authentication failed"):
            await api.get("/endpoint")

        hook.assert_not_awaited()
        assert mock_session.request.call_count == 1


# ========================== AuthenticatedAPI Refresh Hook Wiring Tests ==========================


class TestAuthenticatedAPIRefreshHookWiring:
    """Tests that AuthenticatedAPI correctly wires _refresh_hook to auth_api.refresh_session."""

    @pytest.fixture
    def mock_auth_api(self, mock_session):
        """Create a mock AuthAPI with a refresh_session method."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.refresh_session = AsyncMock(return_value=True)
        return auth_api

    def test_refresh_hook_is_wired_to_auth_api_refresh_session(self, mock_auth_api):
        """AuthenticatedAPI._refresh_hook must be auth_api.refresh_session after construction."""
        api = AuthenticatedAPI(mock_auth_api, base_url="https://api.example.com")

        assert api._refresh_hook is mock_auth_api.refresh_session

    def test_base_api_refresh_hook_defaults_to_none(self):
        """BaseAPI._refresh_hook must default to None (no auto-refresh unless wired)."""
        api = BaseAPI(base_url="https://api.example.com")

        assert api._refresh_hook is None
