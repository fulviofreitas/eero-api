# ⚙️ Configuration

How `EeroClient` is constructed, where credentials live, and what is (and isn't) configurable.

---

## 📋 Requirements

- Python **>=3.12** (3.13 and 3.14 also supported)
- Dependencies: `aiohttp>=3.8.0`, `pydantic>=2.0.0`, `keyring>=23.0.0`

```bash
pip install eero-api
```

<details>
<summary>📦 Install for development</summary>

```bash
git clone https://github.com/fulviofreitas/eero-api.git
cd eero-api
pip install -e ".[dev]"
```

The `[dev]` extra adds `pytest`, `pytest-asyncio`, `pytest-cov`, `black`, `isort`, `mypy`, `ruff`, `rich`, `click`, and `commitizen`.

</details>

---

## 🏗️ Constructor Reference

`EeroClient` takes exactly seven keyword arguments — nothing else:

```python
from eero import EeroClient

client = EeroClient(
    session=None,             # Optional[aiohttp.ClientSession]
    cookie_file=None,         # Optional[str]
    use_keyring=True,         # bool
    cache_timeout=60,         # int (seconds)
    send_legacy_cookie=True,  # bool (keyword-only)
    accept_language="en-US",  # str  (keyword-only)
    get_retries=0,            # int  (keyword-only)
)
```

| Argument | Type | Default | Purpose |
|---|---|---|---|
| `session` | `Optional[ClientSession]` | `None` | Reuse an existing aiohttp session; otherwise one is created and owned by the client for the lifetime of the `async with` block |
| `cookie_file` | `Optional[str]` | `None` | Explicit path to a JSON credential file (see [File storage](#file-storage)) |
| `use_keyring` | `bool` | `True` | Whether to try the OS keyring for credential storage |
| `cache_timeout` | `int` | `60` | TTL in seconds for the client's in-memory response cache (`account`, `networks`, `network`, `eeros`, `devices`, `profiles`) |
| `send_legacy_cookie` | `bool` | `True` | Also send the session token as a per-request `s=<token>` cookie alongside the `X-User-Token` header. `False` sends the header only. See [Request Headers and Transport](#-request-headers-and-transport) |
| `accept_language` | `str` | `"en-US"` | Value of the `X-Accept-Language` header sent on every request. Must be printable ASCII with no CR/LF; anything else raises `EeroValidationException` at construction time |
| `get_retries` | `int` | `0` | Number of **additional** attempts for a `GET` that fails with a transport error or a `5xx`. `0` disables retrying. Never applies to writes. See [Retry Policy](#-retry-policy) |

The same three keyword-only options exist on `EeroAPI` and `AuthAPI` (and on `BaseAPI` / `AuthenticatedAPI` for anyone composing the transport directly); `EeroClient` forwards them unchanged.

> **Note**: There is no `config_path`, `timeout`, or `session_token` constructor argument. There are no `connect()` / `close()` methods — the async context manager (`async with EeroClient() as client:`) is the only lifecycle API.

---

## 🔐 Credential Storage

Storage backend selection is handled by `create_storage()` in `eero.api.auth_storage`, driven entirely by `use_keyring` and `cookie_file`:

| `use_keyring` | `cookie_file` | Backend selected |
|---|---|---|
| `True` | set | `ChainedStorage` — tries `KeyringStorage` first; `FileStorage(cookie_file)` is consulted only when the keyring holds no record, and the record is then promoted into the keyring and removed from the file. `save()` verifies the keyring write with a read-back and falls through to `FileStorage(cookie_file)` when it doesn't verify — see the note below |
| `True` | `None` (default) | `KeyringStorage` only |
| `False` | set | `FileStorage(cookie_file)` only |
| `False` | `None` | `MemoryStorage` |

> ⚠️ **Warning:** `EeroClient(use_keyring=False)` with no `cookie_file` silently resolves to `MemoryStorage`. Credentials live only in the process's memory and vanish the moment the process exits — there is no error, warning, or log line to tell you this happened. If you want persistence without the OS keyring, you **must** pass `cookie_file` explicitly.

> ℹ️ **Note:** `ChainedStorage.save()` verifies every primary write with a read-back before deciding whether the fallback is needed. `KeyringStorage.save()` swallows its own exceptions and returns normally, so a raised-and-caught failure alone would never reach `ChainedStorage`'s except branch — instead, after a primary `save()` returns, `ChainedStorage` re-`load()`s from the primary and compares the result to what it just wrote; on any mismatch (an exception, or a keyring backend that reports success without actually persisting) it falls through to `FileStorage(cookie_file)`. `use_keyring=True` with a `cookie_file` set is therefore a viable choice for headless/container/CI persistence; `use_keyring=False, cookie_file=...` (plain `FileStorage`) remains valid too and is simpler if you have no use for the keyring at all. See [Credential Storage](Credential-Storage) for the full mechanics.

### Keyring backends

`KeyringStorage` delegates to the `keyring` package, which picks a backend per OS:

| OS | Backend |
|---|---|
| 🍎 macOS | Keychain |
| 🐧 Linux | Secret Service (GNOME Keyring, KWallet) |
| 🪟 Windows | Windows Credential Locker |

Credentials are stored under a fixed service/account pair:

```python
SERVICE_NAME = "eero-api"
ACCOUNT_NAME = "auth-tokens"
```

If the keyring backend raises (headless Linux with no Secret Service daemon, locked keyring, etc.), `KeyringStorage.save()` / `.load()` catch the exception internally and log at `DEBUG` — the failure is non-fatal, and `ChainedStorage`'s read-back check (see note above) still detects it and falls through to the file fallback. This also covers backends that report success without persisting anything (e.g. `keyring.backends.null.Keyring`, sometimes used to "disable" keyring in containers) — no exception is raised there either, but the read-back still catches the mismatch. `use_keyring=False, cookie_file=...` remains a valid, simpler alternative if you'd rather skip the keyring entirely.

### File storage

`FileStorage` writes a single JSON file to the path you provide:

```python
client = EeroClient(cookie_file="/data/eero-cookies.json")
```

- **No default path exists.** `cookie_file` is never inferred from `~/.config`, `$XDG_CONFIG_HOME`, or anything else — you must pass it explicitly for file-based persistence to happen at all.
- `save()` creates the parent directory (`os.makedirs(..., exist_ok=True)`), refuses to write if `file_path` is a symlink, writes `json.dumps(credentials.to_dict())` to a fresh `tempfile.mkstemp()` file in the same directory (created `0600`), `fsync`s it, re-asserts `0600` with `os.chmod`, then atomically swaps it into place with `os.replace()`. A crash mid-write leaves the previous file or nothing — never a partial record.
- Any failure during `save()` is logged at `ERROR` and swallowed; `save()` never raises.
- `FileStorage.file_path` (property) returns the resolved absolute path (`~` expanded).
- The file holds `{"session_id": ..., "schema_version": 2}` and nothing else. A file written by an earlier release (with the extra fields 7.x wrote, or the pre-v3.0.0 `user_token` key) is migrated to this shape the first time it is loaded. See [Credential Storage](Credential-Storage#-the-credentialstorage-abstraction) and [Migration](Migration#the-credential-record).

---

## 🖥️ Headless / Container / CI Recipes

The SDK reads no environment variables itself. If you want to seed a session from an env var (Kubernetes secret, GitHub Actions secret, etc.), read it in **your own code** and hand it to the client's async token methods — there is no constructor shortcut for this:

```python
import asyncio
import os

from eero import EeroClient


async def main() -> None:
    token = os.environ["EERO_SESSION_TOKEN"]  # your own env var, your own name

    async with EeroClient(use_keyring=False, cookie_file="/data/eero-cookies.json") as client:
        await client.set_session_token(token)

        networks = await client.get_networks()
        print(networks["data"])


asyncio.run(main())
```

To invalidate a session before disposing of a container:

```python
await client.clear_session_token()
```

Both are `async` methods on `EeroClient` (delegating to `AuthAPI.set_session_token` / `clear_session_token`) — never constructor kwargs. Each call also invalidates the client's in-memory response cache.

`set_session_token()` raises `EeroValidationException` for an empty or non-string token, and for a token containing any character outside printable ASCII (including CR/LF) — the same rule the transport applies to every header value, since the token is sent verbatim as `X-User-Token`. A rejected token is never persisted, so strip any trailing newline from a secret read out of a file or env var before passing it in.

---

## 🚫 What the SDK Does NOT Do

> **No environment variables**: the SDK never calls `os.environ` for configuration or secrets. Any env var handling shown above is your own application code, not SDK behavior.

> **No settings file**: nothing under `~/.config/` or anywhere else is written except the credential file you explicitly opt into via `cookie_file`. User-preference persistence (default network, output format, etc.) moved to the [eeroctl](https://github.com/fulviofreitas/eeroctl) CLI in v4.0.0.

> **`preferred_network_id` is in-memory only**: `client.set_preferred_network(network_id)` / `client.preferred_network_id` just set/read an attribute on the `EeroClient` instance. It is not persisted, and it disappears when the object is garbage-collected.

---

## 📨 Request Headers and Transport

Every request the SDK sends carries this fixed header set, built in one place (`eero.api.base.build_request_headers`):

| Header | Value | Configurable? |
|---|---|---|
| `Accept` | `application/json` | No |
| `User-Agent` | `eero.const.DEFAULT_USER_AGENT` (a mobile-app-style string) | No |
| `X-Accept-Language` | `accept_language` constructor option (default `en-US`) | Yes — constructor option |
| `Content-Type` | Set per request by the body encoding: `application/json` for JSON bodies, `application/x-www-form-urlencoded` for form bodies (login, verify, logout) | No |
| `X-User-Token` | The session token — only on requests to the API host over `https` | No — always sent when a token exists |
| `Cookie` | `s=<token>` — same rule, while `send_legacy_cookie=True` | Yes — `send_legacy_cookie` |

Rules the transport enforces regardless of how you configure it:

- Every header value (SDK-supplied and caller-supplied) must be printable ASCII with no CR/LF, otherwise `EeroValidationException` is raised.
- A caller-supplied `headers=` dict may not contain `X-User-Token`, `Cookie`, or `Authorization` (case-insensitive) — `EeroValidationException`. Only the credential builder writes those.
- The session token is never attached to a request whose hostname or scheme differs from the configured API host (`https://api-user.e2ro.com`). Such a request goes out with no credential and a `WARNING` log line.
- Redirects are refused: `allow_redirects=False` is forced on every request, any `3xx` raises `EeroAPIException`, and passing `allow_redirects=True` yourself raises `EeroValidationException`.
- The session token is never written to the shared `aiohttp` cookie jar, so a `session=` you pass in never accumulates the credential.

`send_legacy_cookie` exists so the SDK keeps sending the cookie the API has historically accepted alongside the header; it defaults on and is expected to be removed in a future major version.

> **Note**: For advanced callers composing requests on `BaseAPI` directly, `eero.api.base` exports `RequestEncoding` (`JSON`, `FORM`, `EMPTY_JSON_STRING`, `NONE`) and `build_request_headers(*, accept_language, extra_headers=None)`. Pass `json=` for a JSON body, `data=` for a form body, or `encoding=RequestEncoding.EMPTY_JSON_STRING` for the two-character `""` body some parameterless POSTs require; supplying more than one carrier raises `EeroValidationException`.

---

## 🔁 Retry Policy

| Request | Retried by the SDK? |
|---|---|
| `POST` / `PUT` / `DELETE` / `PATCH` | **Never**, for any reason. A write is attempted exactly once, whatever `get_retries` is set to |
| `GET` that fails with `EeroNetworkException`, `EeroTimeoutException`, or a `5xx` `EeroAPIException` | Up to `get_retries` additional times, with a fixed `GET_RETRY_DELAY_SECONDS` (0.5 s) pause between attempts. Default `0` — off |
| `GET` that fails with `400`, `401`, `403`, `404`, `409`, or `429` | Never |

```python
client = EeroClient(get_retries=2)  # a failing GET is attempted up to 3 times in total
```

The 401 refresh-and-replay described in [Authentication](Authentication#-transparent-refresh-and-replay) is not part of this policy: it is a single replay of the original request (any method) after a successful server-driven re-authentication, not a retry of a failed call.

Rate limiting (`429`) is likewise never retried by the SDK — see [Caching and Rate Limits](Caching-and-Rate-Limits) for how to back off in your own code.

---

## ⏱️ Timeouts

Every request made by `BaseAPI._request` defaults to this `aiohttp.ClientTimeout`:

```python
aiohttp.ClientTimeout(total=30, sock_read=10)
```

| Bound | Value | Meaning |
|---|---|---|
| `total` | 30s | Overall wall-clock budget for the request |
| `sock_read` | 10s | Max time to wait for any single chunk of the response body (guards against a slow-trickle/"slowloris" upstream even if `total` hasn't elapsed) |

> ⚠️ **Warning:** There is no `timeout` constructor argument on `EeroClient`, `EeroAPI`, or `BaseAPI`; the only way to change it is a per-call `timeout=` kwarg on the `BaseAPI` transport methods, which `EeroClient` does not expose. A request that exceeds either bound raises `EeroTimeoutException`.

---

## 🛡️ Security Considerations

- **Keyring-backed storage** keeps the session token out of any file on disk, encrypted at rest by the OS.
- **File storage** is `0600` (owner-only), but is still plaintext JSON — treat the containing volume/host as sensitive.
- **`MemoryStorage`** never touches disk, but also never survives process restart — see the warning above about the silent fallback.
- All API responses are capped at `MAX_RESPONSE_BYTES` (10 MiB) to prevent unbounded memory growth from a hostile or misbehaving upstream.
- Error response bodies are never embedded raw in exception messages or log lines. The exception message is the recognised `meta.error` catalogue string (trimmed, lowercased) or the fixed label `unrecognised error string`; `EeroAPIException` and its subclasses prefix it with `API error <status>: `, while `EeroAuthenticationException` (all 401s), `EeroRateLimitException` and API-reported `EeroValidationException` carry no status in the message at all. `meta.code`, the raw body and the URL are never embedded. Read `err.envelope` / `err.error_code` / `err.status_code` for details; the envelope is logged only through the redacting secure logger. See [Error Handling](Error-Handling#common-attributes-envelope-error_code-message).
- The session token is sent only to the API host over `https`, never to any other host or scheme, and never via the shared cookie jar — see [Request Headers and Transport](#-request-headers-and-transport).
- Redirects are never followed (`allow_redirects=False`, and it cannot be re-enabled) — any 3xx response is rejected outright so the session token can never leak to an unintended host.
- For log redaction behavior (how tokens/cookies are masked in log output), see [Logging and Security](Logging-and-Security).

---

## 🔗 Related Pages

- [Home](Home) — Overview and quick start
- [Python API](Python-API) — Full API reference & examples
- [Authentication](Authentication) — Login/verify flow, session transport, and server-driven refresh
- [Error Handling](Error-Handling) — Exception hierarchy and the `envelope` / `error_code` attributes
- [Credential Storage](Credential-Storage) — Deep dive on storage backends
- [Logging and Security](Logging-and-Security) — Sensitive-field redaction and secure logging
- [Troubleshooting](Troubleshooting) — Common issues & fixes
