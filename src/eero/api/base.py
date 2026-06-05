"""Base API client for Eero API interactions."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, Optional

import aiohttp
from aiohttp import ClientSession

if TYPE_CHECKING:
    from .auth import AuthAPI

from ..const import DEFAULT_HEADERS, MAX_RESPONSE_BYTES
from ..exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroNetworkException,
    EeroRateLimitException,
    EeroTimeoutException,
    EeroValidationException,
)

_LOGGER = logging.getLogger(__name__)


def id_from_url(id_or_url: str) -> str:
    """Extract the trailing numeric / opaque ID from an Eero API URL or bare ID.

    Accepts either a bare identifier (e.g. ``"12345"`` or ``"p_abc"``) or a
    URL fragment as returned by the API (e.g. ``"/2.2/networks/12345"``,
    ``"/2.2/networks/12345/profiles/p_abc"``).  In all cases the trailing
    path segment is returned unchanged.

    Args:
        id_or_url: A bare ID or an API URL / URL fragment.

    Returns:
        The trailing path segment of the input.

    Raises:
        EeroValidationException: If the input is empty or not a string.
    """
    if not isinstance(id_or_url, str) or not id_or_url:
        raise EeroValidationException("id_or_url", "must be a non-empty string")
    # Strip any trailing slash, then return the last path segment.
    stripped = id_or_url.rstrip("/")
    return stripped.rsplit("/", 1)[-1]


class BaseAPI:
    """Base API client for interacting with RESTful APIs."""

    def __init__(
        self,
        session: Optional[ClientSession] = None,
        cookie_file: Optional[str] = None,
        base_url: str = "",
    ) -> None:
        """Initialize the BaseAPI.

        Args:
            session: Optional aiohttp ClientSession to use for requests
            cookie_file: Optional path to a file for storing authentication cookies
            base_url: Base URL for API endpoints
        """
        self._session = session
        self._cookie_file = cookie_file
        self._base_url = base_url
        self._headers = DEFAULT_HEADERS.copy()
        self._should_close_session = False
        self._refresh_hook: Optional[Callable[[], Awaitable[bool]]] = None

    async def __aenter__(self) -> "BaseAPI":
        """Enter async context manager."""
        if self._session is None:
            self._session = ClientSession()
            self._should_close_session = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context manager."""
        if self._should_close_session and self._session:
            await self._session.close()

    @property
    def session(self) -> ClientSession:
        """Get the active aiohttp session.

        Note: ClientSession must be created within an async context.
        Use `async with BaseAPI() as api:` to ensure proper session management.

        Raises:
            RuntimeError: If session is accessed before entering async context
        """
        if self._session is None:
            raise RuntimeError(
                "ClientSession not initialized. Use 'async with' context manager "
                "or call __aenter__() to initialize the session."
            )
        return self._session

    async def _request(
        self,
        method: str,
        url: str,
        auth_token: Optional[str] = None,
        *,
        _refresh_retried: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """Make a request to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: API endpoint URL
            auth_token: Optional authentication token
            _refresh_retried: Internal flag — True when this call is already a
                retry after a server-driven session refresh.  Prevents infinite
                loops if the retry itself receives a refresh signal.
            **kwargs: Additional parameters to pass to the request

        Returns:
            JSON response data

        Raises:
            EeroAuthenticationException: If not authenticated
            EeroAPIException: If the API returns an error
            EeroRateLimitException: If rate limited
            EeroNetworkException: If there's a network error
            EeroTimeoutException: If request times out
        """
        # Set default timeout if not provided
        if "timeout" not in kwargs:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=30)

        # Add authentication token if provided
        if auth_token:
            cookies = {"s": auth_token}
            self.session.cookie_jar.update_cookies(cookies)
            _LOGGER.debug("Added auth cookie for request")

        # Make a full URL if a relative path was provided
        if not url.startswith(("http://", "https://")):
            url = f"{self._base_url.rstrip('/')}/{url.lstrip('/')}"

        # Defensive session-cookie hardening: disable automatic redirect
        # following so that any 3xx response is inspected before cookies
        # travel to a potentially different host.
        kwargs.setdefault("allow_redirects", False)

        # Enhanced request logging
        _LOGGER.debug("Request: %s %s", method, url)

        try:
            async with self.session.request(method, url, **kwargs) as response:
                _LOGGER.debug("Response status: %s", response.status)

                # Defensive session-cookie hardening: refuse any redirect
                # outright.  Because allow_redirects=False is set above,
                # aiohttp never follows redirects automatically; any 3xx that
                # reaches this point is surfaced as an EeroAPIException so the
                # session cookie is never forwarded to an unintended host.
                if 300 <= response.status < 400:
                    location = response.headers.get("Location", "")
                    _LOGGER.warning(
                        "Redirect response %s blocked (Location: %s)",
                        response.status,
                        location or "<none>",
                    )
                    raise EeroAPIException(
                        response.status,
                        f"Redirect not followed: {response.status}"
                        + (f" -> {location}" if location else " (no Location header)"),
                    )

                # Read at most MAX_RESPONSE_BYTES + 1 bytes so that exceeding
                # the limit is detectable without buffering an unbounded body.
                raw_bytes = await response.content.read(MAX_RESPONSE_BYTES + 1)
                if len(raw_bytes) > MAX_RESPONSE_BYTES:
                    raise EeroAPIException(
                        response.status,
                        f"Response body exceeded max size of {MAX_RESPONSE_BYTES} bytes",
                    )

                response_text = raw_bytes.decode("utf-8")

                # All 2xx status codes are success responses
                if 200 <= response.status < 300:
                    # 204 No Content has no body
                    if response.status == 204 or not response_text.strip():
                        return {}
                    try:
                        return json.loads(response_text)
                    except Exception as e:
                        _LOGGER.error("Error parsing JSON response: %s", e)
                        raise EeroAPIException(
                            response.status, f"Invalid JSON response: {response_text}"
                        )
                elif response.status == 401:
                    # Use debug level - callers handle auth errors appropriately
                    _LOGGER.debug("Authentication failed: %s", response.status)

                    # Check for a server-driven session-refresh signal.
                    # The server signals "session still valid but must be refreshed"
                    # via {"meta": {"error": "error.session.refresh", ...}}.
                    # When detected, transparently refresh the session and retry
                    # the original request once.  The one-shot guard (_refresh_retried)
                    # prevents looping if the retry itself receives the same signal.
                    if not _refresh_retried and self._refresh_hook is not None:
                        try:
                            body = json.loads(response_text)
                            server_error = body.get("meta", {}).get("error")
                        except Exception:
                            body = None
                            server_error = None

                        if server_error == "error.session.refresh":
                            _LOGGER.debug(
                                "Server requested session refresh; refreshing and retrying"
                            )
                            refreshed = await self._refresh_hook()
                            if refreshed:
                                return await self._request(
                                    method,
                                    url,
                                    auth_token,
                                    _refresh_retried=True,
                                    **kwargs,
                                )
                            # Refresh failed — fall through to raise below.
                            _LOGGER.debug("Session refresh returned False; raising auth exception")

                    raise EeroAuthenticationException(f"Authentication failed: {response_text}")
                elif response.status == 404:
                    # Use debug level for 404s to reduce noise in CLI output
                    _LOGGER.debug("Resource not found at %s", url)
                    raise EeroAPIException(
                        response.status,
                        f"Resource not found: {response_text}. URL: {url}",
                    )
                elif response.status == 429:
                    raise EeroRateLimitException("Rate limit exceeded")
                else:
                    _LOGGER.error("API error %s: %s", response.status, response_text)
                    raise EeroAPIException(response.status, response_text)
        except asyncio.TimeoutError as err:
            _LOGGER.error("Request to %s timed out", url)
            raise EeroTimeoutException("Request timed out") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error: %s for URL: %s", err, url)
            raise EeroNetworkException(f"Network error: {err}") from err

    async def get(self, url: str, auth_token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Make a GET request to the API.

        Args:
            url: API endpoint URL
            auth_token: Optional authentication token
            **kwargs: Additional parameters to pass to the request

        Returns:
            JSON response data
        """
        return await self._request("GET", url, auth_token, **kwargs)

    async def post(self, url: str, auth_token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Make a POST request to the API.

        Args:
            url: API endpoint URL
            auth_token: Optional authentication token
            **kwargs: Additional parameters to pass to the request

        Returns:
            JSON response data
        """
        return await self._request("POST", url, auth_token, **kwargs)

    async def put(self, url: str, auth_token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Make a PUT request to the API.

        Args:
            url: API endpoint URL
            auth_token: Optional authentication token
            **kwargs: Additional parameters to pass to the request

        Returns:
            JSON response data
        """
        return await self._request("PUT", url, auth_token, **kwargs)

    async def delete(self, url: str, auth_token: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Make a DELETE request to the API.

        Args:
            url: API endpoint URL
            auth_token: Optional authentication token
            **kwargs: Additional parameters to pass to the request

        Returns:
            JSON response data
        """
        return await self._request("DELETE", url, auth_token, **kwargs)


class AuthenticatedAPI(BaseAPI):
    """Base class for APIs that require authentication.

    This class delegates session management to the AuthAPI instance,
    allowing sub-APIs to be initialized before the async context is entered.
    """

    def __init__(self, auth_api: "AuthAPI", base_url: str = "") -> None:
        """Initialize the AuthenticatedAPI.

        Args:
            auth_api: Authentication API instance that manages the session
            base_url: Base URL for API endpoints
        """
        # Pass None for session - we'll delegate to auth_api
        super().__init__(session=None, cookie_file=None, base_url=base_url)
        self._auth_api = auth_api
        # Wire the server-driven session-refresh hook so that any 401 carrying
        # the "error.session.refresh" signal causes a transparent refresh+retry.
        # AuthAPI itself intentionally does NOT set this hook — its own
        # refresh_session method calls _request, and we must not create an
        # infinite loop if the refresh endpoint also returns 401-with-signal.
        self._refresh_hook = auth_api.refresh_session

    @property
    def session(self) -> ClientSession:
        """Get the active aiohttp session from the auth API.

        Delegates to the auth API's session property, which ensures
        proper session lifecycle management.

        Returns:
            The active ClientSession

        Raises:
            RuntimeError: If session is accessed before async context is entered
        """
        return self._auth_api.session
