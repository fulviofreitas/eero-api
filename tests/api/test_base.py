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

from eero.api.base import AuthenticatedAPI, BaseAPI, RequestEncoding, build_request_headers
from eero.const import DEFAULT_ACCEPT_LANGUAGE, DEFAULT_USER_AGENT, MAX_RESPONSE_BYTES
from eero.exceptions import (
    EeroAccessDeniedException,
    EeroAPIException,
    EeroAuthenticationException,
    EeroClientBlockedException,
    EeroFeatureUnavailableException,
    EeroNetworkException,
    EeroNotFoundException,
    EeroPremiumRequiredException,
    EeroRateLimitException,
    EeroTimeoutException,
    EeroValidationException,
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
    async def test_request_with_auth_token_sets_header_and_legacy_cookie(
        self, api_with_session, mock_session
    ):
        """Test that an auth token on the API host sets X-User-Token and the legacy cookie.

        The credential must never be written to the shared cookie jar -- it is
        passed per-request via the ``cookies=`` kwarg instead.
        """
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        await api_with_session.get("/endpoint", auth_token="test_token")

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["headers"]["X-User-Token"] == "test_token"
        assert call_kwargs["cookies"] == {"s": "test_token"}
        mock_session.cookie_jar.update_cookies.assert_not_called()

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

        with pytest.raises(EeroAuthenticationException, match="unrecognised error string"):
            await api_with_session.get("/endpoint")

    @pytest.mark.asyncio
    async def test_404_raises_not_found_exception(self, api_with_session, mock_session):
        """Test that 404 status raises EeroNotFoundException, regardless of body."""
        mock_response = create_mock_response(404, None, "Not found")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroNotFoundException) as exc_info:
            await api_with_session.get("/endpoint")

        assert exc_info.value.resource_type is None
        assert exc_info.value.resource_id is None

    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_exception(self, api_with_session, mock_session):
        """Test that 429 status raises EeroRateLimitException."""
        mock_response = create_mock_response(429, None, "Too Many Requests")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroRateLimitException, match="unrecognised error string"):
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

        Streaming via iter_chunked accumulates the running total per chunk; a
        body of exactly MAX_RESPONSE_BYTES never exceeds the ceiling and must
        not raise.
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
    async def test_response_delivered_in_multiple_chunks_is_fully_read(
        self, api_with_session, mock_session
    ):
        """Regression: a body delivered across many TCP chunks must be read in full.

        The previous implementation used ``content.read(N)``, which returns
        only what is currently buffered and truncates large responses mid-JSON.
        This test reproduces the failure mode by feeding a body that spans
        many 64 KiB chunks and asserts the full payload is parsed correctly.
        """
        # Build a payload large enough to span dozens of 64 KiB chunks. Each
        # device entry is ~1 KiB, so 5000 entries comfortably exceeds the
        # chunk boundary that triggered the original truncation bug.
        devices = [
            {"url": f"/2.2/networks/n/devices/d{i}", "mac": f"aa:bb:cc:dd:ee:{i:02x}"}
            for i in range(5000)
        ]
        payload = api_success_response(devices)
        body = json.dumps(payload).encode("utf-8")
        assert len(body) > 65536  # spans at least 2 chunks
        assert len(body) < MAX_RESPONSE_BYTES

        mock_response = create_mock_response(200, body_bytes=body)
        mock_session.request.return_value = mock_response

        result = await api_with_session.get("/endpoint")

        assert len(result["data"]) == 5000
        assert result["data"][0]["mac"] == "aa:bb:cc:dd:ee:00"
        assert result["data"][-1]["url"] == "/2.2/networks/n/devices/d4999"

    @pytest.mark.asyncio
    async def test_response_exceeding_limit_raises_api_exception(
        self, api_with_session, mock_session
    ):
        """Test that a response body larger than MAX_RESPONSE_BYTES raises EeroAPIException.

        Streaming via iter_chunked aborts as soon as the running total exceeds
        the cap, so an oversized body trips the guard partway through the body.
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
    async def test_302_without_location_raises_api_exception(self, api_with_session, mock_session):
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
    async def test_allow_redirects_true_override_is_rejected(self, api_with_session, mock_session):
        """A caller may never re-enable redirect following.

        aiohttp strips Authorization and Cookie on a cross-origin redirect
        but not the SDK's own X-User-Token header, so the core refuses to
        let allow_redirects=True reach the transport at all.
        """
        with pytest.raises(EeroValidationException, match="allow_redirects"):
            await api_with_session.get("/endpoint", allow_redirects=True)

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_allow_redirects_false_override_is_a_no_op(self, api_with_session, mock_session):
        """Explicitly passing allow_redirects=False is accepted (it matches the forced default)."""
        mock_response = create_mock_response(200, api_success_response({}))
        mock_session.request.return_value = mock_response

        await api_with_session.get("/endpoint", allow_redirects=False)

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs.get("allow_redirects") is False


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

        with pytest.raises(EeroAuthenticationException, match="error.session.refresh"):
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

        with pytest.raises(EeroAuthenticationException, match="error.session.refresh"):
            await api_with_hook.get("/endpoint")

        assert mock_session.request.call_count == 2
        api_with_hook._refresh_hook.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_401_without_session_refresh_signal_raises_immediately(self, mock_session):
        """A plain 401 (no refresh signal) must raise without calling the hook."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")
        hook = AsyncMock(return_value=True)
        api._refresh_hook = hook

        mock_response = create_mock_response(401, None, "Unauthorized")
        mock_session.request.return_value = mock_response

        with pytest.raises(EeroAuthenticationException, match="unrecognised error string"):
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

        with pytest.raises(EeroAuthenticationException, match="error.session.refresh"):
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

        with pytest.raises(EeroAuthenticationException, match="unrecognised error string"):
            await api.get("/endpoint")

        hook.assert_not_awaited()
        assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_replay_rebuilds_headers_and_cookies_from_scratch(
        self, api_with_hook, mock_session
    ):
        """The replay must not reuse the first attempt's headers/cookies object.

        Both calls carry a fresh, correctly-built header set for the
        (possibly new) token -- never the literal headers/cookies kwargs
        captured before the refresh.
        """
        success_payload = api_success_response({"ok": True})
        first_response = create_mock_response(401, self.SESSION_REFRESH_BODY)
        second_response = create_mock_response(200, success_payload)
        mock_session.request.side_effect = [first_response, second_response]

        await api_with_hook.get("/endpoint", auth_token="original_token")

        assert mock_session.request.call_count == 2
        first_kwargs = mock_session.request.call_args_list[0][1]
        second_kwargs = mock_session.request.call_args_list[1][1]
        # Distinct header dict instances -- the replay rebuilds, not reuses.
        assert first_kwargs["headers"] is not second_kwargs["headers"]
        assert second_kwargs["headers"]["X-User-Token"] == "original_token"
        assert second_kwargs["cookies"] == {"s": "original_token"}

    @pytest.mark.asyncio
    async def test_replay_uses_token_provider_when_set(self, api_with_hook, mock_session):
        """When a token provider is wired, the replay sources its token from it."""
        api_with_hook._token_provider = AsyncMock(return_value="refreshed_token")
        success_payload = api_success_response({"ok": True})
        first_response = create_mock_response(401, self.SESSION_REFRESH_BODY)
        second_response = create_mock_response(200, success_payload)
        mock_session.request.side_effect = [first_response, second_response]

        await api_with_hook.get("/endpoint", auth_token="original_token")

        api_with_hook._token_provider.assert_awaited_once()
        second_kwargs = mock_session.request.call_args_list[1][1]
        assert second_kwargs["headers"]["X-User-Token"] == "refreshed_token"
        assert second_kwargs["cookies"] == {"s": "refreshed_token"}

    @pytest.mark.asyncio
    async def test_replay_falls_back_to_original_token_without_provider(
        self, api_with_hook, mock_session
    ):
        """With no token provider wired, the replay falls back to the original auth_token."""
        assert api_with_hook._token_provider is None
        success_payload = api_success_response({"ok": True})
        first_response = create_mock_response(401, self.SESSION_REFRESH_BODY)
        second_response = create_mock_response(200, success_payload)
        mock_session.request.side_effect = [first_response, second_response]

        await api_with_hook.get("/endpoint", auth_token="original_token")

        second_kwargs = mock_session.request.call_args_list[1][1]
        assert second_kwargs["headers"]["X-User-Token"] == "original_token"


# ========================== AuthenticatedAPI Refresh Hook Wiring Tests ==========================


class TestAuthenticatedAPIRefreshHookWiring:
    """Tests that AuthenticatedAPI correctly wires _refresh_hook to auth_api.refresh_session."""

    @pytest.fixture
    def mock_auth_api(self, mock_session):
        """Create a mock AuthAPI with a refresh_session method."""
        auth_api = MagicMock()
        auth_api.session = mock_session
        auth_api.refresh_session = AsyncMock(return_value=True)
        auth_api.get_auth_token = AsyncMock(return_value="provider_token")
        return auth_api

    def test_refresh_hook_is_wired_to_auth_api_refresh_session(self, mock_auth_api):
        """AuthenticatedAPI._refresh_hook must be auth_api.refresh_session after construction."""
        api = AuthenticatedAPI(mock_auth_api, base_url="https://api.example.com")

        assert api._refresh_hook is mock_auth_api.refresh_session

    def test_token_provider_is_wired_to_auth_api_get_auth_token(self, mock_auth_api):
        """AuthenticatedAPI._token_provider must be auth_api.get_auth_token after construction."""
        api = AuthenticatedAPI(mock_auth_api, base_url="https://api.example.com")

        assert api._token_provider is mock_auth_api.get_auth_token

    def test_base_api_refresh_hook_defaults_to_none(self):
        """BaseAPI._refresh_hook must default to None (no auto-refresh unless wired)."""
        api = BaseAPI(base_url="https://api.example.com")

        assert api._refresh_hook is None

    def test_base_api_token_provider_defaults_to_none(self):
        """BaseAPI._token_provider must default to None (fall back to auth_token)."""
        api = BaseAPI(base_url="https://api.example.com")

        assert api._token_provider is None


# ========================== Credential Placement Tests ==========================


class TestCredentialPlacement:
    """Tests for X-User-Token header and legacy cookie placement.

    The session token must only ever be attached to requests whose resolved
    hostname exactly matches the configured API host, never to a foreign
    host or a foreign host that merely shares a parent domain.
    """

    API_BASE_URL = "https://api.example.com"

    @pytest.fixture
    def api(self, mock_session):
        return BaseAPI(session=mock_session, base_url=self.API_BASE_URL)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("send_legacy_cookie", [True, False])
    async def test_credential_sent_to_api_host(self, mock_session, send_legacy_cookie):
        """X-User-Token is always sent to the API host; the legacy cookie follows the flag."""
        api = BaseAPI(
            session=mock_session,
            base_url=self.API_BASE_URL,
            send_legacy_cookie=send_legacy_cookie,
        )
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.get("/endpoint", auth_token="test_token")

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["headers"]["X-User-Token"] == "test_token"
        if send_legacy_cookie:
            assert call_kwargs["cookies"] == {"s": "test_token"}
        else:
            assert "cookies" not in call_kwargs

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "foreign_url",
        [
            "https://other.example.com/endpoint",
            "https://evil.example.com/endpoint",
            "https://sub.api.example.com/endpoint",
            "https://attacker.example.com.evil.net/endpoint",
        ],
    )
    async def test_no_credential_sent_to_foreign_host(self, api, mock_session, foreign_url):
        """No X-User-Token and no legacy cookie are sent to any non-API host,
        including a host that merely shares the parent domain."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.get(foreign_url, auth_token="test_token")

        call_kwargs = mock_session.request.call_args[1]
        assert "X-User-Token" not in call_kwargs["headers"]
        assert "cookies" not in call_kwargs

    @pytest.mark.asyncio
    async def test_foreign_host_logs_warning(self, api, mock_session, caplog):
        """Sending a credential-bearing request to a foreign host logs a warning."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level("WARNING", logger="eero.api.base"):
            await api.get("https://evil.example.com/endpoint", auth_token="test_token")

        assert any("foreign host" in record.getMessage() for record in caplog.records)

    @pytest.mark.asyncio
    async def test_no_credential_attached_without_auth_token(self, api, mock_session):
        """No credential is attached when no auth_token is supplied."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.get("/endpoint")

        call_kwargs = mock_session.request.call_args[1]
        assert "X-User-Token" not in call_kwargs["headers"]
        assert "cookies" not in call_kwargs

    @pytest.mark.asyncio
    async def test_credential_never_written_to_shared_cookie_jar(self, api, mock_session):
        """The transport never touches the shared cookie jar for credentials."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.get("/endpoint", auth_token="test_token")
        await api.post("https://evil.example.com/endpoint", auth_token="test_token", json={})

        mock_session.cookie_jar.update_cookies.assert_not_called()
        mock_session.cookie_jar.clear.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_credential_on_plain_http_downgrade_to_api_host(self, api, mock_session):
        """A plain-http URL on the API host still gets no credential.

        The resolved scheme must match the configured API host's scheme
        (normally https) in addition to the hostname, so a downgraded URL
        never carries the session token.
        """
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.get("http://api.example.com/endpoint", auth_token="test_token")

        call_kwargs = mock_session.request.call_args[1]
        assert "X-User-Token" not in call_kwargs["headers"]
        assert "cookies" not in call_kwargs

    @pytest.mark.asyncio
    async def test_plain_http_downgrade_logs_warning(self, api, mock_session, caplog):
        """A scheme downgrade on the API host is warned about too."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with caplog.at_level("WARNING", logger="eero.api.base"):
            await api.get("http://api.example.com/endpoint", auth_token="test_token")

        assert any("scheme" in record.getMessage() for record in caplog.records)


# ========================== Forbidden Caller Header Tests ==========================


class TestForbiddenCallerHeaders:
    """Caller-supplied headers may never set a credential-bearing header name.

    The credential builder (``_build_credentials``) is the only writer of
    ``X-User-Token``/``Cookie``/``Authorization``; this holds regardless of
    whether the request even resolves to the API host.
    """

    @pytest.fixture
    def api(self, mock_session):
        return BaseAPI(session=mock_session, base_url="https://api.example.com")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "header_name",
        ["X-User-Token", "x-user-token", "Cookie", "cookie", "Authorization", "authorization"],
    )
    async def test_credential_header_name_rejected_on_api_host(
        self, api, mock_session, header_name
    ):
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with pytest.raises(EeroValidationException):
            await api.get("/endpoint", headers={header_name: "smuggled"})

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("header_name", ["X-User-Token", "Cookie", "Authorization"])
    async def test_credential_header_name_rejected_on_foreign_host(
        self, api, mock_session, header_name
    ):
        """The rejection is unconditional -- it also applies to a foreign host,
        where no credential would have been attached anyway."""
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with pytest.raises(EeroValidationException):
            await api.get("https://evil.example.com/endpoint", headers={header_name: "smuggled"})

        mock_session.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_unrelated_caller_header_still_accepted(self, api, mock_session):
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.get("/endpoint", headers={"X-Custom": "fine"})

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["headers"]["X-Custom"] == "fine"


# ========================== Header Construction Tests ==========================


class TestHeaderConstruction:
    """Tests for the single header-building function and its use in requests."""

    @pytest.fixture
    def api(self, mock_session):
        return BaseAPI(session=mock_session, base_url="https://api.example.com")

    def test_build_request_headers_defaults(self):
        headers = build_request_headers(accept_language=DEFAULT_ACCEPT_LANGUAGE)

        assert headers["Accept"] == "application/json"
        assert headers["User-Agent"] == DEFAULT_USER_AGENT
        assert headers["X-Accept-Language"] == DEFAULT_ACCEPT_LANGUAGE
        assert "Content-Type" not in headers

    def test_build_request_headers_extra_overrides_defaults(self):
        headers = build_request_headers(
            accept_language=DEFAULT_ACCEPT_LANGUAGE,
            extra_headers={"Accept": "application/vnd.custom+json"},
        )

        assert headers["Accept"] == "application/vnd.custom+json"

    def test_build_request_headers_rejects_invalid_accept_language(self):
        with pytest.raises(EeroValidationException):
            build_request_headers(accept_language="en\r\nX-Injected: 1")

    def test_build_request_headers_rejects_invalid_extra_header(self):
        with pytest.raises(EeroValidationException):
            build_request_headers(
                accept_language=DEFAULT_ACCEPT_LANGUAGE,
                extra_headers={"X-Custom": "bad\nvalue"},
            )

    @pytest.mark.asyncio
    async def test_default_headers_present_on_every_request(self, api, mock_session):
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.get("/endpoint")

        headers = mock_session.request.call_args[1]["headers"]
        assert headers["Accept"] == "application/json"
        assert headers["User-Agent"] == DEFAULT_USER_AGENT
        assert headers["X-Accept-Language"] == DEFAULT_ACCEPT_LANGUAGE

    @pytest.mark.asyncio
    async def test_custom_accept_language_is_sent(self, mock_session):
        api = BaseAPI(
            session=mock_session, base_url="https://api.example.com", accept_language="fr-FR"
        )
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.get("/endpoint")

        headers = mock_session.request.call_args[1]["headers"]
        assert headers["X-Accept-Language"] == "fr-FR"

    def test_invalid_accept_language_rejected_at_construction(self, mock_session):
        with pytest.raises(EeroValidationException):
            BaseAPI(
                session=mock_session,
                base_url="https://api.example.com",
                accept_language="bad\r\nvalue",
            )

    @pytest.mark.asyncio
    async def test_invalid_caller_header_rejected(self, api, mock_session):
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        with pytest.raises(EeroValidationException):
            await api.get("/endpoint", headers={"X-Custom": "bad\r\ninjected"})

    @pytest.mark.asyncio
    async def test_caller_supplied_session_default_headers_respected(self):
        """A caller-supplied real aiohttp session's default headers survive
        for names the SDK does not itself set, via aiohttp's own per-request
        vs. session-default header merge -- the SDK never touches them."""
        real_session = aiohttp.ClientSession(headers={"X-Caller-Custom": "value"})
        try:
            mock_response = create_mock_response(200, api_success_response({}))
            real_session.request = MagicMock(return_value=mock_response)  # type: ignore[method-assign]

            api = BaseAPI(session=real_session, base_url="https://api.example.com")
            await api.get("/endpoint")

            call_kwargs = real_session.request.call_args[1]
            # The SDK's own per-request headers never mention X-Caller-Custom.
            assert "X-Caller-Custom" not in call_kwargs["headers"]
            # aiohttp merges request headers with the session's default
            # headers by name, so the caller's header still reaches the wire.
            assert real_session.headers["X-Caller-Custom"] == "value"
        finally:
            await real_session.close()


# ========================== Request Encoding Tests ==========================


class TestRequestEncoding:
    """Tests for the single per-operation body encoding selector."""

    @pytest.fixture
    def api(self, mock_session):
        return BaseAPI(session=mock_session, base_url="https://api.example.com")

    @pytest.mark.asyncio
    async def test_json_encoding_sets_json_kwarg(self, api, mock_session):
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.post("/endpoint", json={"name": "test"})

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["json"] == {"name": "test"}
        assert "data" not in call_kwargs

    @pytest.mark.asyncio
    async def test_form_encoding_sets_data_kwarg(self, api, mock_session):
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.post("/endpoint", data={"name": "test"})

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["data"] == {"name": "test"}
        assert "json" not in call_kwargs

    @pytest.mark.asyncio
    async def test_empty_json_string_encoding_sends_two_byte_body(self, api, mock_session):
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.post("/endpoint", encoding=RequestEncoding.EMPTY_JSON_STRING)

        call_kwargs = mock_session.request.call_args[1]
        assert call_kwargs["data"] == '""'
        assert call_kwargs["headers"]["Content-Type"] == "application/json"
        assert "json" not in call_kwargs

    @pytest.mark.asyncio
    async def test_none_encoding_sends_no_body(self, api, mock_session):
        mock_session.request.return_value = create_mock_response(200, api_success_response({}))

        await api.get("/endpoint", params={"q": "1"})

        call_kwargs = mock_session.request.call_args[1]
        assert "json" not in call_kwargs
        assert "data" not in call_kwargs
        assert call_kwargs["params"] == {"q": "1"}

    @pytest.mark.asyncio
    async def test_json_and_data_together_raises(self, api, mock_session):
        with pytest.raises(EeroValidationException):
            await api.post("/endpoint", json={"a": 1}, data={"b": 2})

    @pytest.mark.asyncio
    async def test_json_and_empty_json_string_together_raises(self, api, mock_session):
        with pytest.raises(EeroValidationException):
            await api.post("/endpoint", json={"a": 1}, encoding=RequestEncoding.EMPTY_JSON_STRING)

    @pytest.mark.asyncio
    async def test_data_and_empty_json_string_together_raises(self, api, mock_session):
        with pytest.raises(EeroValidationException):
            await api.post("/endpoint", data={"a": 1}, encoding=RequestEncoding.EMPTY_JSON_STRING)


# ========================== Write Retry Prohibition Tests ==========================


class TestWriteRetryProhibition:
    """The core must never retry a write, under any failure mode, for any reason."""

    @pytest.fixture
    def api(self, mock_session):
        return BaseAPI(session=mock_session, base_url="https://api.example.com", get_retries=5)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method_name", ["post", "put", "delete"])
    async def test_write_not_retried_on_transport_error(self, api, mock_session, method_name):
        mock_session.request.side_effect = aiohttp.ClientError("boom")

        with pytest.raises(EeroNetworkException):
            await getattr(api, method_name)(
                "/endpoint", json={} if method_name != "delete" else None
            )

        assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method_name", ["post", "put", "delete"])
    async def test_write_not_retried_on_5xx(self, api, mock_session, method_name):
        mock_session.request.return_value = create_mock_response(503, None, "Service Unavailable")

        with pytest.raises(EeroAPIException):
            await getattr(api, method_name)(
                "/endpoint", json={} if method_name != "delete" else None
            )

        assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_write_replay_after_refresh_fires_at_most_once(self, mock_session):
        """A write's post-refresh replay is a single, non-looping event -- not a retry."""
        api = BaseAPI(session=mock_session, base_url="https://api.example.com", get_retries=5)
        api._refresh_hook = AsyncMock(return_value=True)

        refresh_signal = create_mock_response(
            401, {"meta": {"code": 401, "error": "error.session.refresh"}}
        )
        success = create_mock_response(200, api_success_response({"ok": True}))
        mock_session.request.side_effect = [refresh_signal, success]

        result = await api.post("/endpoint", json={"x": 1})

        assert result["data"] == {"ok": True}
        assert mock_session.request.call_count == 2
        api._refresh_hook.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_write_replay_never_loops_on_repeated_refresh_signal(self, mock_session):
        api = BaseAPI(session=mock_session, base_url="https://api.example.com", get_retries=5)
        api._refresh_hook = AsyncMock(return_value=True)

        refresh_signal = create_mock_response(
            401, {"meta": {"code": 401, "error": "error.session.refresh"}}
        )
        mock_session.request.side_effect = [refresh_signal, refresh_signal]

        with pytest.raises(EeroAuthenticationException):
            await api.post("/endpoint", json={"x": 1})

        assert mock_session.request.call_count == 2
        api._refresh_hook.assert_awaited_once()


# ========================== Bounded GET Retry Tests ==========================


class TestGetRetryPolicy:
    """Tests for the bounded, GET-only retry policy."""

    @pytest.fixture(autouse=True)
    def no_real_sleep(self, monkeypatch):
        """Avoid real delays between retry attempts in tests."""
        monkeypatch.setattr("eero.api.base.asyncio.sleep", AsyncMock(return_value=None))

    @pytest.mark.asyncio
    async def test_get_retries_zero_by_default_on_transport_error(self, mock_session):
        api = BaseAPI(session=mock_session, base_url="https://api.example.com")
        mock_session.request.side_effect = aiohttp.ClientError("boom")

        with pytest.raises(EeroNetworkException):
            await api.get("/endpoint")

        assert mock_session.request.call_count == 1

    @pytest.mark.asyncio
    async def test_get_retries_transport_error_then_succeeds(self, mock_session):
        api = BaseAPI(session=mock_session, base_url="https://api.example.com", get_retries=1)
        success = create_mock_response(200, api_success_response({"ok": True}))
        mock_session.request.side_effect = [aiohttp.ClientError("boom"), success]

        result = await api.get("/endpoint")

        assert result["data"] == {"ok": True}
        assert mock_session.request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_retries_5xx_then_succeeds(self, mock_session):
        api = BaseAPI(session=mock_session, base_url="https://api.example.com", get_retries=2)
        failure = create_mock_response(502, None, "Bad Gateway")
        success = create_mock_response(200, api_success_response({"ok": True}))
        mock_session.request.side_effect = [failure, failure, success]

        result = await api.get("/endpoint")

        assert result["data"] == {"ok": True}
        assert mock_session.request.call_count == 3

    @pytest.mark.asyncio
    async def test_get_retries_bounded_then_raises(self, mock_session):
        api = BaseAPI(session=mock_session, base_url="https://api.example.com", get_retries=2)
        failure = create_mock_response(500, None, "Internal Server Error")
        mock_session.request.side_effect = [failure, failure, failure]

        with pytest.raises(EeroAPIException):
            await api.get("/endpoint")

        assert mock_session.request.call_count == 3

    @pytest.mark.asyncio
    @pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 429])
    async def test_get_never_retries_excluded_statuses(self, mock_session, status):
        api = BaseAPI(session=mock_session, base_url="https://api.example.com", get_retries=3)
        mock_session.request.return_value = create_mock_response(status, None, "error")

        with pytest.raises(
            (
                EeroAPIException,
                EeroAuthenticationException,
                EeroRateLimitException,
                EeroNotFoundException,
            )
        ):
            await api.get("/endpoint")

        assert mock_session.request.call_count == 1


# ========================== Envelope / error_code Attachment Tests ==========================


class TestEnvelopeAttachment:
    """The raw envelope and meta.error must be attached to raised errors."""

    @pytest.fixture
    def api(self, mock_session):
        return BaseAPI(session=mock_session, base_url="https://api.example.com")

    @pytest.mark.asyncio
    async def test_api_exception_carries_envelope_and_error_code(self, api, mock_session):
        body = {"meta": {"code": 500, "error": "error.something_unrecognised"}, "data": None}
        mock_session.request.return_value = create_mock_response(500, body)

        with pytest.raises(EeroAPIException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.envelope == body
        assert exc_info.value.error_code == "error.something_unrecognised"

    @pytest.mark.asyncio
    async def test_not_found_exception_carries_envelope_and_error_code(self, api, mock_session):
        """A 404 with an unrecognised meta.error still carries envelope/error_code."""
        body = {"meta": {"code": 404, "error": "error.not_found"}, "data": None}
        mock_session.request.return_value = create_mock_response(404, body)

        with pytest.raises(EeroNotFoundException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.envelope == body
        assert exc_info.value.error_code == "error.not_found"

    @pytest.mark.asyncio
    async def test_authentication_exception_carries_envelope_and_error_code(
        self, api, mock_session
    ):
        body = {"meta": {"code": 401, "error": "error.auth"}}
        mock_session.request.return_value = create_mock_response(401, body)

        with pytest.raises(EeroAuthenticationException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.envelope == body
        assert exc_info.value.error_code == "error.auth"

    @pytest.mark.asyncio
    async def test_non_json_body_yields_none_envelope_and_error_code(self, api, mock_session):
        mock_session.request.return_value = create_mock_response(500, None, "not json at all")

        with pytest.raises(EeroAPIException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.envelope is None
        assert exc_info.value.error_code is None

    @pytest.mark.asyncio
    async def test_rate_limit_exception_carries_envelope(self, api, mock_session):
        body = {"meta": {"code": 429, "error": "error.rate_limit"}}
        mock_session.request.return_value = create_mock_response(429, body)

        with pytest.raises(EeroRateLimitException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.envelope == body
        assert exc_info.value.error_code == "error.rate_limit"


# ========================== Error Catalogue Classification Tests ==========================


class TestErrorCatalogueClassification:
    """Tests that the transport picks the right SDK exception per catalogue group.

    One representative status/error_code pair per group in
    ``eero.errors``, plus the status-only fallbacks (free-text 404, 404 with
    no meta.error at all) and case-insensitive matching.
    """

    @pytest.fixture
    def api(self, mock_session):
        """Create a BaseAPI with a mock session."""
        return BaseAPI(session=mock_session, base_url="https://api.example.com")

    @pytest.mark.parametrize(
        "status_code,error_code,expected_class",
        [
            (401, "error.session.expired", EeroAuthenticationException),
            (401, "error.session.invalid", EeroAuthenticationException),
            (401, "error.session.revoked", EeroAuthenticationException),
            (401, "error.session.refresh", EeroAuthenticationException),
            (401, "error.verification.required", EeroAuthenticationException),
            (401, "error.verification.invalid", EeroAuthenticationException),
            (401, "error.login.unknown", EeroAuthenticationException),
            # 401 short-circuits before the status-independent groups are
            # even consulted -- none of these may downgrade an
            # authentication failure to something else.
            (401, "error.premium.user_not_subscribed", EeroAuthenticationException),
            (401, "error.eero.offline", EeroAuthenticationException),
            (401, "error.rate.limit", EeroAuthenticationException),
            (401, "error.app.version.blocked", EeroAuthenticationException),
            (403, "error.access.denied", EeroAccessDeniedException),
            (404, "error.network.not.found", EeroNotFoundException),
            (404, "error.eero.no_serial_found", EeroNotFoundException),
            (429, "error.rate.limit", EeroRateLimitException),
            (500, "error.rate.limit", EeroRateLimitException),
            (400, "error.form.errors", EeroValidationException),
            (400, "error.reservation.ip.invalid", EeroValidationException),
            (402, "error.premium.user_not_subscribed", EeroPremiumRequiredException),
            (403, "error.partner.unavailable", EeroPremiumRequiredException),
            (400, "error.eero.offline", EeroFeatureUnavailableException),
            (403, "error.network.unavailable", EeroFeatureUnavailableException),
            (400, "error.app.version.blocked", EeroClientBlockedException),
            (500, "error.reservation.failed", EeroAPIException),
            (500, "error.stripe.card.declined", EeroAPIException),
            (500, "encryptme.error.email.exists", EeroAPIException),
        ],
    )
    @pytest.mark.asyncio
    async def test_error_code_maps_to_expected_exception_class(
        self, api, mock_session, status_code, error_code, expected_class
    ):
        """Each catalogue group's representative error_code raises the right class."""
        body = {"meta": {"code": status_code, "error": error_code}}
        mock_session.request.return_value = create_mock_response(status_code, body)

        with pytest.raises(expected_class) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.envelope == body
        assert exc_info.value.error_code == error_code

    @pytest.mark.asyncio
    async def test_case_insensitive_matching(self, api, mock_session):
        """A catalogue string is matched regardless of case."""
        body = {"meta": {"code": 403, "error": "ERROR.ACCESS.DENIED"}}
        mock_session.request.return_value = create_mock_response(403, body)

        with pytest.raises(EeroAccessDeniedException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.error_code == "ERROR.ACCESS.DENIED"

    @pytest.mark.asyncio
    async def test_whitespace_trimmed_matching(self, api, mock_session):
        """A catalogue string is matched even with surrounding whitespace."""
        body = {"meta": {"code": 403, "error": "  error.access.denied  "}}
        mock_session.request.return_value = create_mock_response(403, body)

        with pytest.raises(EeroAccessDeniedException):
            await api.get("/endpoint")

    @pytest.mark.asyncio
    async def test_unrecognised_error_code_does_not_change_status_based_class(
        self, api, mock_session
    ):
        """An unrecognised meta.error never changes the class chosen by status."""
        body = {"meta": {"code": 500, "error": "error.something_never_seen_before"}}
        mock_session.request.return_value = create_mock_response(500, body)

        with pytest.raises(EeroAPIException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == "error.something_never_seen_before"

    @pytest.mark.asyncio
    async def test_404_with_free_text_sentence_raises_not_found(self, api, mock_session):
        """A 404 whose meta.error is a free-text sentence still raises EeroNotFoundException."""
        body = {"meta": {"code": 404, "error": "No parameters were given to check."}}
        mock_session.request.return_value = create_mock_response(404, body)

        with pytest.raises(EeroNotFoundException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.error_code == "No parameters were given to check."

    @pytest.mark.asyncio
    async def test_404_with_no_meta_error_raises_not_found(self, api, mock_session):
        """A 404 with no meta.error at all (e.g. an unknown network) still raises EeroNotFoundException."""
        body = {"meta": {"code": 404}}
        mock_session.request.return_value = create_mock_response(404, body)

        with pytest.raises(EeroNotFoundException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.envelope == body
        assert exc_info.value.error_code is None

    @pytest.mark.asyncio
    async def test_404_with_no_body_raises_not_found(self, api, mock_session):
        """A 404 with a completely empty/non-JSON body still raises EeroNotFoundException."""
        mock_session.request.return_value = create_mock_response(404, None, body_bytes=b"")

        with pytest.raises(EeroNotFoundException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.envelope is None
        assert exc_info.value.error_code is None

    @pytest.mark.asyncio
    async def test_403_without_access_denied_string_stays_api_exception(self, api, mock_session):
        """A 403 without the recognised access-denied string stays a plain EeroAPIException."""
        mock_session.request.return_value = create_mock_response(403, None, "Forbidden")

        with pytest.raises(EeroAPIException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.status_code == 403
        assert not isinstance(exc_info.value, EeroAccessDeniedException)

    @pytest.mark.asyncio
    async def test_access_denied_is_not_an_auth_error(self, api, mock_session):
        """EeroAccessDeniedException.is_auth_error() is False -- it is not a 401."""
        body = {"meta": {"code": 403, "error": "error.access.denied"}}
        mock_session.request.return_value = create_mock_response(403, body)

        with pytest.raises(EeroAccessDeniedException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.is_auth_error() is False

    @pytest.mark.asyncio
    async def test_not_found_is_not_an_auth_error(self, api, mock_session):
        """EeroNotFoundException.is_auth_error() is False -- the base default."""
        mock_session.request.return_value = create_mock_response(404, None, "")

        with pytest.raises(EeroNotFoundException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.is_auth_error() is False

    @pytest.mark.asyncio
    async def test_recognised_404_error_embeds_the_catalogue_string(self, api, mock_session):
        """A recognised 404 error_code is embedded verbatim (normalized) in the message."""
        body = {"meta": {"code": 404, "error": "error.network.not.found"}}
        mock_session.request.return_value = create_mock_response(404, body)

        with pytest.raises(EeroNotFoundException) as exc_info:
            await api.get("/endpoint")

        assert "error.network.not.found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_404_message_never_embeds_free_text_or_url(self, api, mock_session):
        """A 404's free-text meta.error and the request URL never reach the message."""
        body = {"meta": {"code": 404, "error": "No parameters were given to check."}}
        mock_session.request.return_value = create_mock_response(404, body)

        with pytest.raises(EeroNotFoundException) as exc_info:
            await api.get("/some/network/path")

        message = str(exc_info.value)
        assert message == "API error 404: unrecognised error string"
        assert "No parameters were given to check." not in message
        assert "some/network/path" not in message
        assert "https://api.example.com" not in message

    @pytest.mark.asyncio
    async def test_unrecognised_error_message_is_fixed_label_only(self, api, mock_session):
        """An unrecognised meta.error yields the fixed label and nothing else."""
        body = {"meta": {"code": 500, "error": "error.something_never_seen_before"}}
        mock_session.request.return_value = create_mock_response(500, body)

        with pytest.raises(EeroAPIException) as exc_info:
            await api.get("/endpoint")

        assert str(exc_info.value) == "API error 500: unrecognised error string"


class TestExceptionMessageSafety:
    """Tests that exception messages never leak response body data or credentials."""

    @pytest.fixture
    def api(self, mock_session):
        """Create a BaseAPI with a mock session."""
        return BaseAPI(session=mock_session, base_url="https://api.example.com")

    @pytest.mark.asyncio
    async def test_message_excludes_body_data_and_credential_shaped_values(self, api, mock_session):
        """str(exc) never contains the envelope's data payload or a credential-shaped value."""
        body = {
            "meta": {"code": 500, "error": "error.reservation.failed"},
            "data": {
                "session_token": "SUPER_SECRET_TOKEN_VALUE",
                "user_token": "ANOTHER_SECRET_TOKEN",
                "detail": "some internal diagnostic string",
            },
        }
        mock_session.request.return_value = create_mock_response(500, body)

        with pytest.raises(EeroAPIException) as exc_info:
            await api.get("/endpoint")

        message = str(exc_info.value)
        assert message == "API error 500: error.reservation.failed"
        assert "SUPER_SECRET_TOKEN_VALUE" not in message
        assert "ANOTHER_SECRET_TOKEN" not in message
        assert "some internal diagnostic string" not in message
        # The data is still available, verbatim, via the envelope attribute --
        # it is only ever excluded from the message text.
        assert exc_info.value.envelope == body

    @pytest.mark.asyncio
    async def test_2xx_body_with_meta_error_shaped_field_returned_unmodified(
        self, api, mock_session
    ):
        """A 2xx body is returned exactly as received, even if it has an error-shaped meta.error.

        Classification only ever applies to non-2xx responses; a success
        status is never second-guessed by inspecting meta.error.
        """
        body = {
            "meta": {"code": 200, "error": "error.session.refresh", "server_time": "now"},
            "data": {"ok": True},
        }
        mock_session.request.return_value = create_mock_response(200, body)

        result = await api.get("/endpoint")

        assert result == body

    @pytest.mark.asyncio
    async def test_non_string_meta_error_degrades_to_none_without_raising(self, api, mock_session):
        """A non-string meta.error (e.g. a list or int) degrades to error_code=None, no crash."""
        body = {"meta": {"code": 500, "error": ["unexpected", "shape"]}}
        mock_session.request.return_value = create_mock_response(500, body)

        with pytest.raises(EeroAPIException) as exc_info:
            await api.get("/endpoint")

        assert exc_info.value.error_code is None
        assert str(exc_info.value) == "API error 500: unrecognised error string"
