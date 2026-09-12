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

> 💡 **Tip:** `EeroClient` also exposes `login()`/`verify()`/`logout()` directly — use these public methods instead of reaching into `client._api` for auth. `client._api.<domain>` is private (not covered by semver) but it IS the documented escape hatch for domain methods that have no `EeroClient` wrapper — see [API Reference](API-Reference).

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
    data = response.get("data") or {}
    networks = data if isinstance(data, list) else (data.get("networks") or data.get("data") or [])
    if not networks:
        print("No networks found - check your Eero account")
```

> **Note**: For a reusable shape-tolerant helper, see [Raw Response Format](Raw-Response-Format#the-networks-shape-specifically).

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

Exception names all end in `Exception`, not `Error` — there is no `EeroAuthenticationError`, only `EeroAuthenticationException`. These classes have never been named `*Error` in any release, so this is a typo rather than a rename to chase; earlier versions of this wiki documented the wrong names. See [Error Handling](Error-Handling) for the full hierarchy.

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

Some write endpoints return `200 OK` but don't persist the change server-side. This is a known upstream quirk of the Eero Cloud API's `/2.2` endpoint for three device writes — `set_device_nickname`, `pause_device`, and `set_device_priority` — where `/2.3` is required and is what this SDK already uses for those calls (see `src/eero/const.py`, issue #102). `block_device` is unaffected — it writes via `/2.2` `POST`/`DELETE /networks/{id}/blacklist` (issue #109). If you're seeing this on a custom request path, double-check you're not bypassing the SDK's endpoint selection.

### `set_device_priority` Does Nothing

`set_device_priority` (and the underlying device-priority endpoint) is a confirmed no-op upstream — it returns `200 OK` and changes nothing (issue #111). Use [SQM](Deprecations) bandwidth controls instead. See [Deprecations](Deprecations).

---

## DNS Issues

### I set custom DNS and nothing changed

**On eero-api < 7.0.0 this is expected — the DNS write methods did nothing.** `set_custom_dns`, `set_dns_mode`, `clear_custom_dns` and `set_dns_caching` sent a `custom_dns` field that does not exist in the API. The backend accepted it with `200 OK` and discarded it (issue #123). Upgrade to v7.0.0 or later.

On v7.0.0+, verify the write landed by reading it back — `get_dns_settings` is never cached, so a read immediately after a write is always fresh:

```python
await client.set_custom_dns(["9.9.9.9"])
data = (await client.get_dns_settings())["data"]
print(data["dns"]["mode"], data["dns"]["custom"]["ips"])
```

### I set IPv6 DNS servers with `set_ipv6_dns` and nothing happened

`set_ipv6_dns` does not set DNS servers. It toggles `ipv6_upstream`, the network-level IPv6 connectivity setting, and always has — the name is misleading (issue #125). Use `set_custom_dns_ipv6()`.

IPv6 DNS works independently of `ipv6_upstream`: the IPv6 servers can be configured and active while `ipv6_upstream` is `false`.

### The servers I read back don't match what I wrote

Two likely causes:

- **IPv6 is stored fully expanded.** `2606:4700:4700::1111` reads back as `2606:4700:4700:0:0:0:0:1111`. Compare via `ipaddress.IPv6Address(a) == ipaddress.IPv6Address(b)`, never string equality.
- **You're reading `dns.custom.ips` while the mode is `automatic`.** Those two are independent: the API retains your servers when custom DNS is switched off. Check `dns.mode` to know what is actually in use, and `dns.parent.ips` for the ISP resolvers being used instead.

### `EeroValidationException` on a DNS call that used to work

Expected on v7.0.0+. Over-limit input (more than 2 servers per address family) used to be silently truncated and now raises. Malformed literals and family mismatches are also rejected locally now. See [Migration](Migration#v6x--v700).

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
