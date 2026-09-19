"""Base API client for Eero API interactions."""

from __future__ import annotations

import asyncio
import json
import re
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlsplit

import aiohttp
from aiohttp import ClientSession

if TYPE_CHECKING:
    from .auth import AuthAPI

from ..const import (
    DEFAULT_ACCEPT_LANGUAGE,
    DEFAULT_USER_AGENT,
    GET_RETRY_DELAY_SECONDS,
    MAX_RESPONSE_BYTES,
)
from ..errors import exception_for_error
from ..exceptions import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroNetworkException,
    EeroTimeoutException,
    EeroValidationException,
)
from ..logging import get_secure_logger

_LOGGER = get_secure_logger(__name__)

# Printable ASCII (space through tilde) with no CR/LF. This is a stricter
# subset of what HTTP technically allows, chosen to keep header injection
# impossible regardless of downstream transport quirks.
_HEADER_VALUE_RE = re.compile(r"^[\x20-\x7E]*$")

# HTTP methods that write state. These are never retried by the core for any
# reason -- a duplicate write could trigger unintended side effects upstream
# (see the mesh-reboot note in the DNS write path). GET is the only method
# eligible for the bounded transport-error/5xx retry below.
_WRITE_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})

# Header names that only the credential builder may set. A caller-supplied
# header of one of these names (case-insensitive) is rejected outright so a
# domain module or downstream caller can never smuggle a credential into a
# request -- intentionally or via a copy-pasted header dict -- bypassing the
# host/scheme gate in ``_build_credentials``.
_FORBIDDEN_CALLER_HEADER_NAMES = frozenset({"x-user-token", "cookie", "authorization"})


class RequestEncoding(str, Enum):
    """The body encoding applied to a single request.

    Exactly one of these is active per request, derived from which body
    carrier the caller supplied to ``_request``:

    * ``JSON`` -- caller passed ``json=<obj>``; aiohttp serializes it and
      sets ``Content-Type: application/json``.
    * ``FORM`` -- caller passed ``data=<mapping>``; aiohttp URL-encodes it
      and sets ``Content-Type: application/x-www-form-urlencoded``.
    * ``EMPTY_JSON_STRING`` -- caller passed ``encoding=RequestEncoding.
      EMPTY_JSON_STRING`` with no ``json=``/``data=``; the two-character
      body ``""`` is sent with ``Content-Type: application/json``. This is
      the shape the API accepts for its parameterless POST operations.
    * ``NONE`` -- no body carrier was supplied (e.g. a GET, or a POST whose
      body is carried entirely by ``params=``).
    """

    JSON = "json"
    FORM = "form"
    EMPTY_JSON_STRING = "empty_json_string"
    NONE = "none"


def _error_body_summary(response_text: str, envelope: Optional[Dict[str, Any]]) -> str:
    """Build a leak-safe summary of an error response body for exception messages.

    The raw body text and the envelope's ``data`` field are never embedded.
    When the body parsed as a JSON object, the summary is built from
    ``meta.code``/``meta.error`` only. Otherwise it is a fixed label plus
    the body's byte length.

    Args:
        response_text: The raw response body (used only for its length when
            it did not parse as JSON).
        envelope: The parsed response envelope, or ``None``.

    Returns:
        A summary string safe to embed in an exception message.
    """
    if envelope is not None:
        meta = envelope.get("meta")
        meta = meta if isinstance(meta, dict) else {}
        return f"meta.code={meta.get('code')!r}, meta.error={meta.get('error')!r}"
    return f"<non-JSON response body, {len(response_text.encode('utf-8'))} bytes>"


def _log_error_body(
    log_fn: Callable[..., None],
    prefix: str,
    response_text: str,
    envelope: Optional[Dict[str, Any]],
) -> None:
    """Log an error response body without ever emitting the raw body text.

    The parsed envelope is logged through the secure logger (which redacts
    sensitive field names) when the body was JSON; otherwise only a fixed
    label plus the body's byte length is logged.

    Args:
        log_fn: A bound ``SecureLoggerAdapter`` method (e.g. ``_LOGGER.debug``)
            so redaction of positional arguments is applied.
        prefix: Short context label for the log line.
        response_text: The raw response body (used only for its length when
            it did not parse as JSON).
        envelope: The parsed response envelope, or ``None``.
    """
    if envelope is not None:
        log_fn("%s response body: %s", prefix, envelope)
    else:
        log_fn(
            "%s response body: <non-JSON, %s bytes>",
            prefix,
            len(response_text.encode("utf-8")),
        )


def _validate_header_value(name: str, value: str) -> None:
    """Validate that a header value is safe to send.

    Args:
        name: The header name, used only for the error message.
        value: The header value to validate.

    Raises:
        EeroValidationException: If ``value`` is not a string, or contains
            characters outside printable ASCII (which also excludes CR/LF,
            ruling out header injection).
    """
    if not isinstance(value, str) or not _HEADER_VALUE_RE.match(value):
        raise EeroValidationException(name, "header value must be printable ASCII with no CR/LF")


def build_request_headers(
    *,
    accept_language: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Build the outbound header set for a single request.

    This is the single place in the SDK that constructs request headers.
    ``Content-Type`` is deliberately never set here -- it is determined per
    request by the active :class:`RequestEncoding` (see ``_request``).

    Args:
        accept_language: Value for the ``X-Accept-Language`` header.
        extra_headers: Optional caller-supplied headers for this call. Values
            override the SDK defaults of the same name; all values (SDK and
            caller-supplied) are validated.

    Returns:
        A new header dictionary. Passing this as ``headers=`` to an aiohttp
        session request only overrides the names present in the returned
        dict on a session created with its own default headers -- aiohttp
        merges request-level headers with session-level defaults by name.

    Raises:
        EeroValidationException: If any header value is not printable ASCII
            without CR/LF.
    """
    _validate_header_value("X-Accept-Language", accept_language)

    headers: Dict[str, str] = {
        "Accept": "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
        "X-Accept-Language": accept_language,
    }

    if extra_headers:
        for name, value in extra_headers.items():
            _validate_header_value(name, value)
        headers.update(extra_headers)

    return headers


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


def _parse_envelope(text: str) -> Optional[Dict[str, Any]]:
    """Best-effort parse of a response body as a JSON object.

    Args:
        text: The raw response body.

    Returns:
        The parsed JSON object, or ``None`` when the body is empty, not
        valid JSON, or not a JSON object.
    """
    if not text.strip():
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _error_code_from_envelope(envelope: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extract ``meta.error`` from a parsed response envelope.

    Args:
        envelope: The parsed response envelope, or ``None``.

    Returns:
        The string value of ``envelope["meta"]["error"]`` when present, else
        ``None``.
    """
    if not isinstance(envelope, dict):
        return None
    meta = envelope.get("meta")
    if not isinstance(meta, dict):
        return None
    error = meta.get("error")
    return error if isinstance(error, str) else None


class BaseAPI:
    """Base API client for interacting with RESTful APIs."""

    def __init__(
        self,
        session: Optional[ClientSession] = None,
        cookie_file: Optional[str] = None,
        base_url: str = "",
        *,
        send_legacy_cookie: bool = True,
        accept_language: str = DEFAULT_ACCEPT_LANGUAGE,
        get_retries: int = 0,
    ) -> None:
        """Initialize the BaseAPI.

        Args:
            session: Optional aiohttp ClientSession to use for requests.
            cookie_file: Optional path to a file for storing authentication
                cookies.
            base_url: Base URL for API endpoints. Its hostname is the
                "configured API host" -- credentials are only ever attached
                to requests resolving to this exact hostname.
            send_legacy_cookie: When True (default), also send the session
                token as the legacy ``s=<token>`` cookie, per request, on
                requests to the configured API host. The cookie is never
                written to the shared session cookie jar.
            accept_language: Value sent as ``X-Accept-Language`` on every
                request. Validated as printable ASCII with no CR/LF.
            get_retries: Number of additional attempts for GET requests that
                fail with a transport error or a 5xx response. 0 (default)
                disables retrying. Never applies to POST/PUT/DELETE/PATCH.
        """
        self._session = session
        self._cookie_file = cookie_file
        self._base_url = base_url
        parsed_base = urlsplit(base_url) if base_url else None
        self._api_host = parsed_base.hostname if parsed_base else None
        self._api_scheme = parsed_base.scheme if parsed_base else None
        self._should_close_session = False
        self._refresh_hook: Optional[Callable[[], Awaitable[bool]]] = None
        # Optional zero-argument async token provider, wired by
        # AuthenticatedAPI from the auth layer. Used only to source the
        # token for the post-refresh replay in ``_request`` so a stale token
        # captured in the original call's closure is never blindly reused;
        # falls back to the originally supplied auth_token when unset.
        self._token_provider: Optional[Callable[[], Awaitable[Optional[str]]]] = None
        self._send_legacy_cookie = send_legacy_cookie
        _validate_header_value("X-Accept-Language", accept_language)
        self._accept_language = accept_language
        self._get_retries = get_retries

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

    def _resolve_url(self, url: str) -> str:
        """Resolve a possibly-relative URL against the configured base URL."""
        if url.startswith(("http://", "https://")):
            return url
        return f"{self._base_url.rstrip('/')}/{url.lstrip('/')}"

    def _classify_encoding(
        self,
        json_body: Any,
        data_body: Any,
        encoding: Optional[RequestEncoding],
    ) -> RequestEncoding:
        """Determine which single body carrier a request is using.

        Args:
            json_body: The value of a ``json=`` kwarg, or ``None``.
            data_body: The value of a ``data=`` kwarg, or ``None``.
            encoding: An explicit ``RequestEncoding`` marker, or ``None``.

        Returns:
            The resolved ``RequestEncoding`` for the request.

        Raises:
            EeroValidationException: If more than one body carrier was
                supplied.
        """
        carriers_supplied = (
            (json_body is not None)
            + (data_body is not None)
            + (encoding is not None and encoding != RequestEncoding.NONE)
        )
        if carriers_supplied > 1:
            raise EeroValidationException(
                "body",
                "only one of json=, data=, or encoding=RequestEncoding.EMPTY_JSON_STRING "
                "may be supplied",
            )
        if json_body is not None:
            return RequestEncoding.JSON
        if data_body is not None:
            return RequestEncoding.FORM
        if encoding == RequestEncoding.EMPTY_JSON_STRING:
            return RequestEncoding.EMPTY_JSON_STRING
        return RequestEncoding.NONE

    def _build_credentials(
        self,
        url: str,
        auth_token: Optional[str],
    ) -> tuple[Dict[str, str], Optional[Dict[str, str]]]:
        """Determine the credential header and legacy cookie for a request.

        The session token is only ever attached -- as the ``X-User-Token``
        header, and optionally as the legacy ``s=<token>`` cookie -- to
        requests whose resolved hostname exactly matches the configured API
        host AND whose resolved scheme exactly matches the API host's
        scheme (normally ``https``). A request to any other host, or to the
        right host over the wrong scheme (e.g. a plain-http downgrade), is
        sent with no credential at all and logs a warning. This is the only
        place in the SDK that writes the ``X-User-Token``/``Cookie``
        credential; caller-supplied headers may never set them (see
        ``_FORBIDDEN_CALLER_HEADER_NAMES``).

        Args:
            url: The fully-resolved absolute request URL.
            auth_token: The session token, or ``None``.

        Returns:
            A tuple of (extra headers, per-request cookies). The cookies
            dict is ``None`` unless the legacy cookie is being sent; it is
            passed to aiohttp's per-request ``cookies=`` kwarg, never to the
            shared cookie jar.
        """
        if not auth_token:
            return {}, None

        parsed = urlsplit(url)
        request_host = parsed.hostname
        host_matches = (
            bool(request_host)
            and bool(self._api_host)
            and ((request_host or "").lower() == (self._api_host or "").lower())
        )
        scheme_matches = (
            bool(parsed.scheme)
            and bool(self._api_scheme)
            and (parsed.scheme.lower() == (self._api_scheme or "").lower())
        )
        if not (host_matches and scheme_matches):
            _LOGGER.warning(
                "Refusing to attach session credential to request for %s: %s://%s",
                "foreign host" if not host_matches else "non-matching scheme",
                parsed.scheme or "<unknown>",
                request_host or "<unknown>",
            )
            return {}, None

        headers = {"X-User-Token": auth_token}
        cookies = {"s": auth_token} if self._send_legacy_cookie else None
        return headers, cookies

    async def _request(
        self,
        method: str,
        url: str,
        auth_token: Optional[str] = None,
        *,
        encoding: Optional[RequestEncoding] = None,
        _refresh_retried: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Make a single request attempt to the API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH).
            url: API endpoint URL, absolute or relative to ``base_url``.
            auth_token: Optional session token. Attached as the
                ``X-User-Token`` header (and, when enabled, the legacy
                ``s=`` cookie) only when the request resolves to the
                configured API host.
            encoding: Optional explicit body encoding marker. Use
                ``RequestEncoding.EMPTY_JSON_STRING`` to send the two-byte
                ``""`` body some parameterless POSTs require. Mutually
                exclusive with ``json=``/``data=``.
            _refresh_retried: Internal flag — True when this call is already
                a retry after a server-driven session refresh. Prevents
                infinite loops if the retry itself receives a refresh
                signal. This replay is distinct from the bounded GET retry:
                it fires at most once, for any HTTP method, only after a
                successful re-authentication -- it is not a retry of a
                failed write.
            **kwargs: Additional parameters forwarded to the aiohttp
                request. ``json=`` and ``data=`` select the body encoding;
                ``params=`` is independent of encoding; ``headers=`` may
                supply extra per-call headers (validated, and overriding
                SDK defaults of the same name).

        Returns:
            The raw, unmodified JSON response envelope (``{}`` for a 204 or
            empty body).

        Raises:
            EeroValidationException: If more than one body carrier is
                supplied, a header value is invalid, or the API reports a
                recognised validation error (HTTP 400).
            EeroAuthenticationException: If authentication fails (HTTP 401).
            EeroAccessDeniedException: If the API denies access (HTTP 403
                with a recognised access-denied error).
            EeroNotFoundException: If the resource is not found (HTTP 404).
            EeroPremiumRequiredException: If the API reports the feature
                requires an Eero Plus subscription, on any HTTP status.
            EeroFeatureUnavailableException: If the API reports the feature
                is unavailable, on any HTTP status.
            EeroClientBlockedException: If the API rejects this client
                version, on any HTTP status.
            EeroAPIException: If the API returns any other error.
            EeroRateLimitException: If rate limited (HTTP 429, or a
                recognised rate-limit error on another status).
            EeroNetworkException: If there's a network error.
            EeroTimeoutException: If the request times out.
        """
        json_body = kwargs.get("json")
        data_body = kwargs.get("data")
        resolved_encoding = self._classify_encoding(json_body, data_body, encoding)

        if resolved_encoding is RequestEncoding.EMPTY_JSON_STRING:
            kwargs["data"] = '""'

        # Set default timeout if not provided.  ``sock_read`` bounds the wait
        # for any single chunk so a slow-trickle ("slowloris") upstream fails
        # fast even when a caller raises ``total``.
        if "timeout" not in kwargs:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=30, sock_read=10)

        # Make a full URL if a relative path was provided
        url = self._resolve_url(url)

        credential_headers, legacy_cookies = self._build_credentials(url, auth_token)
        if auth_token:
            _LOGGER.debug("Resolved credential placement for request")

        caller_headers = kwargs.pop("headers", None)
        extra_headers: Dict[str, str] = {**credential_headers}
        if resolved_encoding is RequestEncoding.EMPTY_JSON_STRING:
            extra_headers["Content-Type"] = "application/json"
        if caller_headers:
            for name, value in caller_headers.items():
                if name.lower() in _FORBIDDEN_CALLER_HEADER_NAMES:
                    raise EeroValidationException(
                        name,
                        "caller-supplied headers may not set a credential header; "
                        "the credential builder is the only writer of this name",
                    )
                _validate_header_value(name, value)
            extra_headers.update(caller_headers)

        kwargs["headers"] = build_request_headers(
            accept_language=self._accept_language,
            extra_headers=extra_headers,
        )

        if legacy_cookies is not None:
            kwargs["cookies"] = legacy_cookies

        # Defensive session-cookie hardening: redirect following is always
        # refused. aiohttp strips Authorization/Cookie on cross-origin
        # redirects but NOT the SDK's own X-User-Token header, so a caller
        # is never permitted to re-enable it -- any 3xx is inspected before
        # any credential could travel to a potentially different host.
        if kwargs.get("allow_redirects") is True:
            raise EeroValidationException(
                "allow_redirects",
                "must not be overridden by the caller; the core always refuses redirects",
            )
        kwargs["allow_redirects"] = False

        # Enhanced request logging
        _LOGGER.debug("Request: %s %s", method, url)

        try:
            async with self.session.request(method, url, **kwargs) as response:
                _LOGGER.debug("Response status: %s", response.status)

                # Defensive session-cookie hardening: refuse any redirect
                # outright.  Because allow_redirects=False is set above,
                # aiohttp never follows redirects automatically; any 3xx that
                # reaches this point is surfaced as an EeroAPIException so the
                # session credential is never forwarded to an unintended host.
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

                # Stream the body in chunks so the full response is read even
                # when delivered over multiple TCP segments, while still
                # enforcing the max-size cap.  ``StreamReader.read(n)`` returns
                # only what is currently buffered (not necessarily n bytes), so
                # using it directly truncates large responses.
                chunks: List[bytes] = []
                total = 0
                async for chunk in response.content.iter_chunked(65536):
                    total += len(chunk)
                    if total > MAX_RESPONSE_BYTES:
                        raise EeroAPIException(
                            response.status,
                            f"Response body exceeded max size of {MAX_RESPONSE_BYTES} bytes",
                        )
                    chunks.append(chunk)
                raw_bytes = b"".join(chunks)

                response_text = raw_bytes.decode("utf-8")

                # All 2xx status codes are success responses
                if 200 <= response.status < 300:
                    # 204 No Content has no body
                    if response.status == 204 or not response_text.strip():
                        return {}
                    try:
                        return json.loads(response_text)
                    except Exception as e:
                        _LOGGER.error(
                            "Error parsing JSON response (%s bytes): %s",
                            len(response_text.encode("utf-8")),
                            e,
                        )
                        raise EeroAPIException(
                            response.status,
                            f"Invalid JSON response "
                            f"({len(response_text.encode('utf-8'))} bytes)",
                        )

                envelope = _parse_envelope(response_text)
                error_code = _error_code_from_envelope(envelope)

                if response.status == 401:
                    # Use debug level - callers handle auth errors appropriately
                    _LOGGER.debug("Authentication failed: %s", response.status)
                    _log_error_body(_LOGGER.debug, "Authentication failed", response_text, envelope)

                    # Check for a server-driven session-refresh signal.
                    # The server signals "session still valid but must be refreshed"
                    # via {"meta": {"error": "error.session.refresh", ...}}.
                    # When detected, transparently refresh the session and retry
                    # the original request once.  The one-shot guard (_refresh_retried)
                    # prevents looping if the retry itself receives the same signal.
                    # This replay is not subject to the write-retry prohibition:
                    # it is a single replay of the original call after a
                    # successful re-authentication, not a retry of a failure.
                    if not _refresh_retried and self._refresh_hook is not None:
                        if error_code == "error.session.refresh":
                            _LOGGER.debug(
                                "Server requested session refresh; refreshing and retrying"
                            )
                            refreshed = await self._refresh_hook()
                            if refreshed:
                                # Rebuild the replay from scratch: drop this
                                # attempt's headers/cookies so no stale
                                # credential or header is ever replayed
                                # verbatim, and source the replay token from
                                # the token provider (falling back to the
                                # originally supplied auth_token when no
                                # provider is wired).
                                replay_kwargs = {
                                    key: value
                                    for key, value in kwargs.items()
                                    if key not in ("headers", "cookies")
                                }
                                replay_token = auth_token
                                if self._token_provider is not None:
                                    replay_token = await self._token_provider()
                                return await self._request(
                                    method,
                                    url,
                                    replay_token,
                                    encoding=encoding,
                                    _refresh_retried=True,
                                    **replay_kwargs,
                                )
                            # Refresh failed — fall through to raise below.
                            _LOGGER.debug("Session refresh returned False; raising auth exception")

                    raise EeroAuthenticationException(
                        f"Authentication failed: {_error_body_summary(response_text, envelope)}",
                        envelope=envelope,
                        error_code=error_code,
                    )
                elif response.status == 404:
                    # Use debug level for 404s to reduce noise in CLI output
                    _LOGGER.debug("Resource not found at %s", url)
                    _log_error_body(_LOGGER.debug, "Resource not found", response_text, envelope)
                    raise exception_for_error(
                        response.status,
                        f"Resource not found: {_error_body_summary(response_text, envelope)}. "
                        f"URL: {url}",
                        envelope=envelope,
                        error_code=error_code,
                    )
                elif response.status == 429:
                    _log_error_body(_LOGGER.debug, "Rate limited", response_text, envelope)
                    raise exception_for_error(
                        response.status,
                        "Rate limit exceeded",
                        envelope=envelope,
                        error_code=error_code,
                    )
                else:
                    # Single classification point for every other non-2xx,
                    # non-3xx, non-401/404/429 status: see
                    # eero.errors.exception_for_error for the full precedence
                    # rules (status-independent groups, then status code).
                    _log_error_body(
                        _LOGGER.error, f"API error {response.status}", response_text, envelope
                    )
                    raise exception_for_error(
                        response.status,
                        _error_body_summary(response_text, envelope),
                        envelope=envelope,
                        error_code=error_code,
                    )
        except asyncio.TimeoutError as err:
            _LOGGER.error("Request to %s timed out", url)
            raise EeroTimeoutException("Request timed out") from err
        except aiohttp.ClientError as err:
            _LOGGER.error("Network error: %s for URL: %s", err, url)
            raise EeroNetworkException(f"Network error: {err}") from err

    async def _request_with_get_retry(
        self,
        method: str,
        url: str,
        auth_token: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Dispatch a request, applying the bounded GET-only retry policy.

        This is the single place the core decides whether to retry. Writes
        (POST/PUT/DELETE/PATCH) are always attempted exactly once here,
        regardless of ``get_retries`` -- the core never retries a write for
        any reason. GET requests that fail with a transport error
        (:class:`EeroNetworkException`/:class:`EeroTimeoutException`) or a
        5xx :class:`EeroAPIException` are retried up to ``get_retries``
        additional times, with a short fixed delay between attempts.
        Client errors (400/401/403/404/409, and 429) are never retried.

        Args:
            method: HTTP method.
            url: API endpoint URL.
            auth_token: Optional session token.
            **kwargs: Forwarded to ``_request``.

        Returns:
            The raw, unmodified JSON response envelope.
        """
        max_attempts = 1 if method in _WRITE_METHODS else (self._get_retries + 1)
        attempt = 0
        while True:
            attempt += 1
            try:
                return await self._request(method, url, auth_token, **kwargs)
            except (EeroNetworkException, EeroTimeoutException):
                if attempt >= max_attempts:
                    raise
            except EeroAPIException as err:
                if attempt >= max_attempts or err.status_code < 500:
                    raise
            _LOGGER.warning(
                "Retrying GET %s after transient failure (attempt %s/%s)",
                url,
                attempt + 1,
                max_attempts,
            )
            await asyncio.sleep(GET_RETRY_DELAY_SECONDS)

    async def get(
        self, url: str, auth_token: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Make a GET request to the API.

        Args:
            url: API endpoint URL.
            auth_token: Optional session token; see ``_request`` for
                credential-placement rules.
            **kwargs: Additional parameters forwarded to the request (for
                example ``params=``). Eligible for the bounded ``get_retries``
                retry policy configured at construction time.

        Returns:
            The raw, unmodified JSON response envelope from the API.
        """
        return await self._request_with_get_retry("GET", url, auth_token, **kwargs)

    async def post(
        self, url: str, auth_token: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Make a POST request to the API. Never retried by the core.

        Args:
            url: API endpoint URL.
            auth_token: Optional session token; see ``_request`` for
                credential-placement rules.
            **kwargs: Additional parameters forwarded to the request, for
                example ``json=``, ``data=``, or ``encoding=``.

        Returns:
            The raw, unmodified JSON response envelope from the API.
        """
        return await self._request_with_get_retry("POST", url, auth_token, **kwargs)

    async def put(
        self, url: str, auth_token: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Make a PUT request to the API. Never retried by the core.

        Args:
            url: API endpoint URL.
            auth_token: Optional session token; see ``_request`` for
                credential-placement rules.
            **kwargs: Additional parameters forwarded to the request, for
                example ``json=``, ``data=``, or ``encoding=``.

        Returns:
            The raw, unmodified JSON response envelope from the API.
        """
        return await self._request_with_get_retry("PUT", url, auth_token, **kwargs)

    async def delete(
        self, url: str, auth_token: Optional[str] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """Make a DELETE request to the API. Never retried by the core.

        Args:
            url: API endpoint URL.
            auth_token: Optional session token; see ``_request`` for
                credential-placement rules.
            **kwargs: Additional parameters forwarded to the request.

        Returns:
            The raw, unmodified JSON response envelope from the API.
        """
        return await self._request_with_get_retry("DELETE", url, auth_token, **kwargs)


class AuthenticatedAPI(BaseAPI):
    """Base class for APIs that require authentication.

    This class delegates session management to the AuthAPI instance,
    allowing sub-APIs to be initialized before the async context is entered.
    """

    def __init__(
        self,
        auth_api: "AuthAPI",
        base_url: str = "",
        *,
        send_legacy_cookie: bool = True,
        accept_language: str = DEFAULT_ACCEPT_LANGUAGE,
        get_retries: int = 0,
    ) -> None:
        """Initialize the AuthenticatedAPI.

        Args:
            auth_api: Authentication API instance that manages the session.
            base_url: Base URL for API endpoints.
            send_legacy_cookie: See ``BaseAPI.__init__``.
            accept_language: See ``BaseAPI.__init__``.
            get_retries: See ``BaseAPI.__init__``.
        """
        # Pass None for session - we'll delegate to auth_api
        super().__init__(
            session=None,
            cookie_file=None,
            base_url=base_url,
            send_legacy_cookie=send_legacy_cookie,
            accept_language=accept_language,
            get_retries=get_retries,
        )
        self._auth_api = auth_api
        # Wire the server-driven session-refresh hook so that any 401 carrying
        # the "error.session.refresh" signal causes a transparent refresh+retry.
        # AuthAPI itself intentionally does NOT set this hook — its own
        # refresh_session method calls _request, and we must not create an
        # infinite loop if the refresh endpoint also returns 401-with-signal.
        self._refresh_hook = auth_api.refresh_session
        # Wire the token provider so the post-refresh replay in ``_request``
        # sources its token from the auth layer rather than replaying the
        # token captured in the original call's closure.
        self._token_provider = auth_api.get_auth_token

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
