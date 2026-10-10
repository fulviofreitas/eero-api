"""Shared helpers for API tests.

Response builders and parametrisation constants for the Eero API layer tests. The fixtures
built on them (``mock_session`` and friends) live in ``tests/conftest.py``; see the note there.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientResponseError

# ==================== Mock Response Helpers ====================


def create_mock_response(
    status: int = 200,
    json_data: Optional[Dict[str, Any]] = None,
    text: str = "",
    raise_for_status: bool = False,
    body_bytes: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
) -> MagicMock:
    """Create a mock aiohttp response.

    Args:
        status: HTTP status code
        json_data: JSON response data
        text: Text response
        raise_for_status: Whether to raise on non-2xx status
        body_bytes: Raw bytes returned by ``response.content.read()``.
            When omitted, the bytes are derived from ``text`` or ``json_data``
            so that existing call sites continue to work without modification.
        headers: Response headers, exposed as ``response.headers``. Defaults to
            no headers.

    Returns:
        Mock response object
    """
    mock_response = MagicMock()
    mock_response.status = status
    mock_response.headers = dict(headers or {})

    # Derive a canonical text representation used for both the legacy
    # ``response.text`` mock and as the default source for body_bytes.
    resolved_text = text or json.dumps(json_data or {})
    mock_response.text = AsyncMock(return_value=resolved_text)
    mock_response.json = AsyncMock(return_value=json_data or {})

    # BaseAPI streams the body via ``response.content.iter_chunked(n)``.  Mock
    # that path by yielding the body in 64 KiB pieces, which mirrors how
    # aiohttp delivers larger responses across multiple TCP segments.
    #
    # ``content.read(n)`` is also mocked to match aiohttp StreamReader
    # semantics: with positive n it returns only what is currently buffered
    # (i.e. the first chunk), NOT n bytes from the full body.  This is the
    # behavior the production bug relied on, so simulating it correctly here
    # means a regression to bounded-read truncation is caught by any test that
    # uses a body larger than one chunk.
    resolved_bytes = body_bytes if body_bytes is not None else resolved_text.encode("utf-8")
    _CHUNK = 65536

    async def _iter_chunked(chunk_size: int = _CHUNK):
        for offset in range(0, len(resolved_bytes), chunk_size):
            yield resolved_bytes[offset : offset + chunk_size]

    async def _read(n: int = -1) -> bytes:
        if n == -1:
            return resolved_bytes
        return resolved_bytes[: min(n, _CHUNK)]

    mock_response.content = MagicMock()
    mock_response.content.read = AsyncMock(side_effect=_read)
    mock_response.content.iter_chunked = MagicMock(side_effect=_iter_chunked)

    if raise_for_status and status >= 400:
        mock_response.raise_for_status = MagicMock(
            side_effect=ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=status,
                message=text,
            )
        )
    else:
        mock_response.raise_for_status = MagicMock()

    # Make it work as an async context manager
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    return mock_response


def api_success_response(data: Any, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create a standard Eero API success response structure.

    Args:
        data: Response data payload
        meta: Optional metadata (defaults to success)

    Returns:
        API response dictionary
    """
    return {
        "meta": meta or {"code": 200, "server_time": datetime.now().isoformat()},
        "data": data,
    }


def api_error_response(code: int, error: str, message: Optional[str] = None) -> Dict[str, Any]:
    """Create a standard Eero API error response structure.

    Args:
        code: Error code
        error: Error type string
        message: Optional error message

    Returns:
        API error response dictionary
    """
    return {
        "meta": {
            "code": code,
            "error": error,
            "message": message or error,
        }
    }


# ==================== Password Validation Parameters ====================

# Values the Wi-Fi password setters must reject before any request.
INVALID_PASSWORDS = [
    pytest.param(None, id="none"),
    pytest.param("", id="empty"),
    pytest.param(False, id="bool"),
    pytest.param(0, id="zero"),
    pytest.param(123, id="number"),
    pytest.param(b"bytes-password", id="bytes"),
    pytest.param([], id="list"),
    pytest.param({}, id="dict"),
]

# Strings the setters must forward unchanged, including the literal "None".
VALID_PASSWORDS = ["ordinary-password", "  preserve spaces  ", "None"]

# Setter method name paired with its resource path under the network.
PASSWORD_WRITES = [
    ("set_network_password", "password"),
    ("set_guest_password", "guestnetwork/password"),
]
