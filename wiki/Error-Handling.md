# 🚨 Error Handling

Every error the SDK raises inherits from `EeroException` — here's the full tree, what triggers each one, and how to handle them.

---

## Exception Hierarchy

All exceptions are defined in `src/eero/exceptions.py` and inherit directly from `EeroException` (the hierarchy is flat — there are no deeper subclasses):

```text
Exception
└── EeroException
    ├── EeroAuthenticationException
    ├── EeroRateLimitException
    ├── EeroNetworkException
    ├── EeroAPIException
    ├── EeroTimeoutException
    ├── EeroNotFoundException
    ├── EeroPremiumRequiredException
    ├── EeroFeatureUnavailableException
    └── EeroValidationException
```

> **Note**: Only `EeroException`, `EeroAPIException`, `EeroAuthenticationException`, `EeroNetworkException`, `EeroRateLimitException`, `EeroTimeoutException`, and `EeroValidationException` are exported from the top-level `eero` package. `EeroNotFoundException`, `EeroPremiumRequiredException`, and `EeroFeatureUnavailableException` are defined but **not** re-exported — import them explicitly from `eero.exceptions` if you need them:
> ```python
> from eero.exceptions import EeroNotFoundException, EeroPremiumRequiredException
> ```

---

## Exception Reference

| Exception | When it's raised | Attributes |
|---|---|---|
| `EeroException` | Base class — not raised directly by the SDK | `message` |
| `EeroAuthenticationException` | HTTP 401 from any request (see [status mapping](#http-status--exception-mapping) below) | `message` (inherited) |
| `EeroRateLimitException` | HTTP 429 | `message` (inherited) |
| `EeroNetworkException` | Any `aiohttp.ClientError` (DNS failure, connection reset, TLS error, etc.) | `message` (inherited) |
| `EeroAPIException` | Blocked redirect (3xx), oversized response body, invalid JSON on a 2xx, HTTP 404, or any other non-2xx/401/429 status | `status_code`, `message` |
| `EeroTimeoutException` | `asyncio.TimeoutError` (request exceeded the configured timeout) | `message` (inherited) |
| `EeroNotFoundException` | **Never raised by this SDK** — see the warning below | `resource_type`, `resource_id` |
| `EeroPremiumRequiredException` | **Never raised by this SDK** — defined for forward compatibility | `feature` |
| `EeroFeatureUnavailableException` | **Never raised by this SDK** — defined for forward compatibility | `feature`, `reason` |
| `EeroValidationException` | Local input validation only — raised before any network call. Sites: `id_from_url()` given an empty/non-string ID; `set_session_token()` / `AuthAPI.set_session_token()` given an empty/non-string token; the DNS write methods given a malformed IP literal, an address of the wrong family, a zone-scoped address, more than 2 servers for one family, an unrecognised DNS mode, or `mode="custom"` without servers | `field`, `message` |

> ⚠️ **Warning:** `EeroNotFoundException`, `EeroPremiumRequiredException`, and `EeroFeatureUnavailableException` exist in `eero.exceptions` but are **dead code from the SDK's own perspective** — nothing in `src/eero/` currently raises them. A 404 from the Eero Cloud API is surfaced as `EeroAPIException` with `status_code == 404`, not `EeroNotFoundException`. Don't write an `except EeroNotFoundException:` block expecting it to ever fire against this SDK version — check `EeroAPIException.status_code == 404` instead.

---

## HTTP Status → Exception Mapping

This is exactly what `BaseAPI._request()` in `src/eero/api/base.py` does — no more, no less:

| HTTP status | Exception raised | Notes |
|---|---|---|
| `200`–`299` | *(none — success)* | `204` or an empty body returns `{}`; invalid JSON on a 2xx raises `EeroAPIException` |
| `300`–`399` | `EeroAPIException` | Redirects are never followed (`allow_redirects=False`) and are always rejected as an error, to stop the session cookie leaking to another host |
| `401` | `EeroAuthenticationException` | Before raising, the SDK checks for a server-driven `{"meta": {"error": "error.session.refresh"}}` signal and transparently refreshes + retries once; the exception is only raised if there's no refresh hook, no signal, or the refresh itself fails |
| `404` | `EeroAPIException` (`status_code=404`) | **Not** `EeroNotFoundException` — see the warning above |
| `429` | `EeroRateLimitException` | See [Caching and Rate Limits](Caching-and-Rate-Limits) |
| `403` | `EeroAPIException` (`status_code=403`) | **No dedicated exception.** 403 falls straight into the generic `else` branch alongside every other unmapped status (400, 500, 502, …) |
| everything else | `EeroAPIException` (`status_code=<actual>`) | The generic fallback branch |
| response body > `MAX_RESPONSE_BYTES` | `EeroAPIException` | Raised mid-stream, before the body is fully buffered |
| `asyncio.TimeoutError` | `EeroTimeoutException` | Request exceeded the timeout (see [Configuration](Configuration)) |
| `aiohttp.ClientError` | `EeroNetworkException` | Connection-level failures, wrapped with `from err` |

> ⚠️ **Warning:** There is no `EeroForbiddenException`. If you're searching for why a 403 didn't raise a dedicated type, this is why — catch `EeroAPIException` and check `.status_code == 403`.

---

## `is_auth_error()`

Every `EeroException` has an `is_auth_error()` method so you can branch on "should I re-authenticate?" without checking exception types one by one:

```python
try:
    await client.get_networks()
except EeroException as err:
    if err.is_auth_error():
        await client.login("you@example.com")
        await client.verify(input("Code: "))
    else:
        raise
```

- `EeroException.is_auth_error()` — always `False` (the default).
- `EeroAuthenticationException.is_auth_error()` — always `True`.
- `EeroAPIException.is_auth_error()` — `True` only when `status_code == 401`. In practice this rarely fires, because a 401 response is intercepted earlier in `_request()` and raised as `EeroAuthenticationException` instead — the check exists defensively in case `EeroAPIException(401, ...)` is ever constructed directly.
- All other subclasses inherit the base `False`.

---

## ⚠️ Naming Warning

> ⚠️ **Warning:** Every exception in this SDK ends in **`Exception`**, never `Error`. If you're searching the codebase or your own traceback for a name and coming up empty, check for these common wrong guesses:
>
> | Wrong (doesn't exist) | Right |
> |---|---|
> | `EeroError` | `EeroException` |
> | `EeroAuthError` / `EeroAuthenticationError` | `EeroAuthenticationException` |
> | `EeroAPIError` | `EeroAPIException` |
> | `EeroRateLimitError` | `EeroRateLimitException` |
> | `EeroTimeoutError` | `EeroTimeoutException` |
> | `EeroForbiddenException` / `EeroForbiddenError` | *(doesn't exist — see [403](#http-status--exception-mapping))* |
>
> These `*Error` names have never existed in any release — earlier versions of this wiki documented them incorrectly, so code copied from it will fail at import. If you're upgrading from a pre-v2.0 release and your `except` clauses reference the deleted model classes, see [Migration](Migration).

---

## Practical Patterns

### Catching broadly

```python
from eero import EeroException

try:
    await client.get_networks()
except EeroException as err:
    print(f"Eero API call failed: {err.message}")
```

### Catching narrowly

```python
from eero import EeroAPIException, EeroAuthenticationException, EeroRateLimitException

try:
    await client.get_devices()
except EeroAuthenticationException:
    print("Session expired — need to log in again")
except EeroRateLimitException:
    print("Rate limited — back off")
except EeroAPIException as err:
    print(f"API error {err.status_code}: {err.message}")
```

### Re-authenticating on `EeroAuthenticationException`

```python
from eero import EeroAuthenticationException

try:
    await client.get_account()
except EeroAuthenticationException:
    await client.login("you@example.com")
    await client.verify(input("Code: "))
    await client.get_account()  # retry
```

### Retry with exponential backoff

```python
import asyncio
from eero import EeroNetworkException, EeroRateLimitException, EeroTimeoutException

async def get_networks_with_retry(client, max_attempts: int = 5):
    for attempt in range(max_attempts):
        try:
            return await client.get_networks()
        except (EeroRateLimitException, EeroTimeoutException, EeroNetworkException):
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

### Handling optional/premium features

```python
from eero.exceptions import EeroPremiumRequiredException, EeroFeatureUnavailableException

try:
    await client.get_premium_status()
except (EeroPremiumRequiredException, EeroFeatureUnavailableException):
    # Reserved for forward compatibility — not currently raised by this SDK.
    # A real premium-gated call today surfaces as EeroAPIException; check status_code.
    print("Feature unavailable")
```

---

## Error Body Truncation

Upstream error response bodies are capped at `MAX_ERROR_BODY_CHARS` (512 characters, defined in `src/eero/const.py`) before being embedded into an exception message or log line:

```python
MAX_ERROR_BODY_CHARS: Final[int] = 512
```

If the body exceeds the cap, the message is cut and suffixed with `... [truncated, <n> chars total]`. This means **the full upstream error body is not available on the exception** — only the first 512 characters. If you need the complete raw body for debugging, you'll need to intercept the response at a lower level (e.g. wrap the `aiohttp.ClientSession`) rather than relying on the exception message.

---

## 🔗 Related Pages

- [Migration](Migration) — upgrading exception-handling code from pre-v2.0 releases
- [Caching and Rate Limits](Caching-and-Rate-Limits) — avoiding `EeroRateLimitException` in the first place
- [Configuration](Configuration) — request timeouts that feed `EeroTimeoutException`
- [Troubleshooting](Troubleshooting) — common issues & fixes
- [Logging and Security](Logging-and-Security) — `SecureLoggerAdapter` and safe debug logging of failed requests
