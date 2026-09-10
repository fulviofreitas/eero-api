# 🔧 Troubleshooting

Common issues and their solutions when using the Eero API Python client.

---

## macOS: "operation not permitted" when activating venv

If you see this error when trying to activate the virtual environment:

```
(eval):source:1: operation not permitted: venv/bin/activate
```

This is caused by macOS quarantine attributes on downloaded files. Fix it by running:

```bash
xattr -cr venv
```

> 💡 **Tip:** If using `uv`, you won't encounter this issue as `uv` manages its own environment.

---

## Authentication Issues

### Amazon Login Accounts

If your Eero account uses Amazon for login (Sign in with Amazon), this library may not work directly due to API limitations.

**Workaround:**

1. Have someone in your household create a standard Eero account using email and password (not Amazon login)
2. In the Eero app, invite that account as an admin to your network
3. Use those new credentials to authenticate with this library

```python
async with EeroClient() as client:
    # Use the new email/password account, not your Amazon-linked account
    await client.login("new-admin@example.com")
    code = input("Enter verification code: ")
    await client.verify(code)
```

> **Note**: The invited admin account will have full access to manage the network.

---

### Session Expired

Eero sessions expire after roughly 30 days. If a call raises `EeroAuthenticationException`, clear the stored token and re-authenticate:

```python
from eero import EeroClient
from eero.exceptions import EeroAuthenticationException

async with EeroClient() as client:
    try:
        await client.get_networks()
    except EeroAuthenticationException:
        await client.clear_session_token()
        await client.login("your-email@example.com")
        code = input("Enter verification code: ")
        await client.verify(code)
```

> 💡 **Tip:** `EeroClient` also exposes `login()`/`verify()`/`logout()` directly — there's no need (and no supported way) to reach into `client._api`. Use the public methods only.

### Check Authentication Status

```python
async with EeroClient() as client:
    if client.is_authenticated:
        print("Authenticated")
    else:
        print("Not authenticated - need to login")
```

---

## Network Connection Issues

### No Networks Found

`get_networks()` returns a raw envelope, never a bare list — so `if not networks:` on the response itself will never fire. Check the `data` payload instead:

```python
async with EeroClient() as client:
    response = await client.get_networks()
    networks = response.get("data", {}).get("networks", [])
    if not networks:
        print("No networks found - check your Eero account")
```

> **Note**: If the `/networks` endpoint returns empty, `EeroClient.get_networks()` automatically falls back to extracting networks from the `/account` endpoint (see `src/eero/client.py`). If you're still seeing an empty list after that fallback, verify the account actually has networks associated with it.

### API Timeouts

Request timeouts are **not configurable** — `EeroClient` has no `timeout` constructor argument. Every request uses a fixed `aiohttp.ClientTimeout(total=30, sock_read=10)` (see `src/eero/api/base.py`).

If you're on a slow or unreliable connection, retry with backoff in your own code and catch `EeroTimeoutException`:

```python
import asyncio
from eero import EeroClient
from eero.exceptions import EeroTimeoutException

async def get_networks_with_retry(client: EeroClient, attempts: int = 3):
    for attempt in range(attempts):
        try:
            return await client.get_networks()
        except EeroTimeoutException:
            if attempt == attempts - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

---

## Import Errors

### `ModuleNotFoundError: No module named 'eero'`

```bash
# Install the package
pip install eero-api

# Or install from source
pip install -e .
```

### `ImportError: cannot import name 'EeroAuthenticationError'`

Exception names all end in `Exception`, not `Error` — there is no `EeroAuthenticationError`, only `EeroAuthenticationException`. See [Migration](Migration) for the full pre/post-v2.0 mapping.

### `ModuleNotFoundError: No module named 'eero.models'`

`eero.models` was removed in v2.0.0. Every API method now returns a raw `Dict[str, Any]` envelope instead of Pydantic models. See [Migration](Migration) and [Raw Response Format](Raw-Response-Format).

### `AttributeError: 'dict' object has no attribute 'name'`

You're using attribute access (`network.name`) on a v2.0+ raw response. Use dict access instead (`network["name"]` or `response["data"]["name"]`). See [Raw Response Format](Raw-Response-Format).

### `TypeError: __init__() got an unexpected keyword argument '...'`

`EeroClient.__init__` only accepts `session`, `cookie_file`, `use_keyring`, and `cache_timeout`. There is no `timeout`, `config_path`, or `session_token` constructor argument, and no `connect()`/`close()` methods — use the async context manager (`async with EeroClient() as client:`) for lifecycle management.

---

## Configuration Issues

### Credentials Not Persisting Across Runs

If you construct `EeroClient(use_keyring=False)` without also passing `cookie_file`, credentials silently fall back to in-memory storage and are lost the moment the process exits — there's no error, just a re-login prompt on the next run. Either leave `use_keyring=True` (the default) or pass an explicit `cookie_file` path. See [Credential Storage](Credential-Storage).

### Passing `network_id` as the First Positional Argument

On `EeroClient`, `network_id` is always a **trailing optional keyword argument**, never the first positional. Passing it positionally silently binds it to the wrong parameter instead of raising an error:

```python
# Wrong: network_id lands in the `enabled` parameter
await client.set_upnp(network_id)  # sets enabled=<truthy string>, ignores network_id

# Right
await client.set_upnp(True, network_id=network_id)
```

See [Network Targeting](Network-Targeting) for the full calling convention.

### `EeroRateLimitException` / HTTP 429

The Eero Cloud API allows roughly 100 requests/minute. If you're polling frequently, rely on `EeroClient`'s built-in TTL cache (`cache_timeout`, default 60s) instead of calling with `refresh_cache=True` on every iteration. See [Caching and Rate Limits](Caching-and-Rate-Limits).

### Device or Network Writes Appear to Succeed but Have No Effect

Some write endpoints return `200 OK` but don't persist the change server-side. This is a known upstream quirk of the Eero Cloud API's `/2.2` endpoint for certain device-related writes — `/2.3` is required and is what this SDK already uses for those calls (see `src/eero/const.py`, issue #102). If you're seeing this on a custom request path, double-check you're not bypassing the SDK's endpoint selection.

### `set_device_priority` Does Nothing

`set_device_priority` (and the underlying device-priority endpoint) is a confirmed no-op upstream — it returns `200 OK` and changes nothing (issue #111). Use [SQM](Deprecations) bandwidth controls instead. See [Deprecations](Deprecations).

---

## Debug Mode

For detailed logging when troubleshooting issues, enable Python's standard logging — but be aware of what that exposes.

```python
import logging
from eero.logging import get_secure_logger

logging.basicConfig(level=logging.DEBUG)

_LOGGER = get_secure_logger(__name__)
_LOGGER.debug("Response: %s", {"user_token": "secret123", "status": "ok"})
# Output: Response: {'user_token': 'secr...[REDACTED:9chars]', 'status': 'ok'}
```

> ⚠️ **Warning:** This SDK's own logging goes through `SecureLoggerAdapter`, which automatically redacts sensitive fields (tokens, cookies, passwords — see `src/eero/logging.py`). But calling `logging.basicConfig(level=logging.DEBUG)` also turns on DEBUG logging for third-party libraries like `aiohttp`, which are **not** redacted and can print raw session tokens and cookies to your logs. Scope DEBUG level to your own loggers in production rather than the root logger. See [Logging and Security](Logging-and-Security) for details.

---

## 🔗 Related Pages

- [Python API](Python-API) — API documentation
- [Configuration](Configuration) — Setup options
- [Authentication](Authentication) — Login and session lifecycle
- [Credential Storage](Credential-Storage) — Keyring, file, and memory backends
- [Raw Response Format](Raw-Response-Format) — The envelope shape and why attribute access fails
- [Network Targeting](Network-Targeting) — Correct `network_id` calling convention
- [Caching and Rate Limits](Caching-and-Rate-Limits) — Avoiding `EeroRateLimitException`
- [Migration](Migration) — Upgrading from pre-v2.0 releases
- [Deprecations](Deprecations) — No-op and removed surface
- [Logging and Security](Logging-and-Security) — Safe debug logging
