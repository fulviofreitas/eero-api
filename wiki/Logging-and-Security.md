# 🛡️ Logging and Security

Why this SDK ships its own logging layer, how redaction works, and how to debug without leaking credentials.

---

## Why the SDK Ships Its Own Logging Layer

The session token travels on every request as the `X-User-Token` header (and, by default, as the `s=` cookie), and JSON response bodies (`{"meta": ..., "data": ...}` envelopes can carry `user_token`, `session_id`, and similar fields). Naive `DEBUG` logging of requests/responses — the first thing anyone reaches for while debugging — will happily print these values verbatim. `src/eero/logging.py` exists so that debug logging is safe by default wherever it's used.

In practice, the modules that handle credentials or response bodies directly opt into it:

| Module | Logger | Why |
|---|---|---|
| `src/eero/api/auth.py` | `get_secure_logger(__name__)` | Handles login, verify, refresh, session tokens |
| `src/eero/api/base.py` (the transport) | `get_secure_logger(__name__)` | Logs parsed error envelopes at `DEBUG` only (the `ERROR` line carries just the status and method) — never the raw body text — so any credential-shaped field in an error envelope is redacted |
| `src/eero/api/auth_storage.py` and almost every domain API | `get_secure_logger(__name__)` | Credential persistence, and domain modules whose envelopes may echo identifiers |
| `client.py`, `dns.py`, `security.py`, `support.py`, `transfer.py`, `ac_compat.py`, `burst_reporters.py` | plain `logging.getLogger(__name__)` | Log method/URL/status and identifiers, not payloads |

> **Note**: If you add your own debug logging around SDK calls — e.g. logging the raw envelope returned by `get_account()` or `get_devices()` — use `get_secure_logger()` yourself. The SDK's internal loggers only protect the SDK's own log lines.

---

## `get_secure_logger()` — The Recommended Entry Point

A drop-in replacement for `logging.getLogger()`:

```python
from eero.logging import get_secure_logger

_LOGGER = get_secure_logger(__name__)

_LOGGER.debug("Response: %s", {"user_token": "secret123", "status": "ok"})
# Output: Response: {'user_token': '[REDACTED:9chars]', 'status': 'ok'}
```

`get_secure_logger(name, sensitive_patterns=None, visible_chars=4)` is `@lru_cache`d — repeated calls with the same `(name, sensitive_patterns, visible_chars)` return the same adapter instance.

A custom `sensitive_patterns=` is scoped to the loggers you pass it to. The compiled regex is
cached **per pattern set** (`_get_sensitive_regex()` is keyed by the frozenset it receives), so
the SDK's own loggers, which use `DEFAULT_SENSITIVE_PATTERNS`, and a logger you build with your
own set never share or overwrite each other's regex. Combine the two with
`add_sensitive_pattern()` below when you want the defaults plus your own field names.

---

## `SecureLoggerAdapter`

`SecureLoggerAdapter(logger, extra=None, sensitive_patterns=DEFAULT_SENSITIVE_PATTERNS, visible_chars=4)` wraps a standard `logging.Logger`. It overrides `log()`, and `debug()`, `info()`, `warning()`, `error()`, `critical()` and `exception()` all funnel through it, so every route into the adapter shares one redaction path. For each call it:

1. Checks `isEnabledFor(level)` **first**. A disabled level returns immediately: nothing is redacted, nothing is formatted, and no argument can make the call raise.
2. Redacts the message object and every positional format argument via `redact_sensitive()`.
3. Merges the adapter's own `extra` context with the call's `extra=` (the call's keys win) and redacts the result, so the values land on the log record as redacted attributes.
4. Hands the redacted values to the underlying `logging.Logger.log()`.

```python
logger = get_secure_logger(__name__)
logger.warning("Auth cookie: %s", {"session_id": "abc123xyz"}, extra={"api_key": "topsecret"})
logger.log(logging.INFO, "Rows: %s", [{"token": "abc"}], extra={"secret": "x"})
```

The positional argument and the `extra` dict are both redacted before the record is emitted, whether the call goes through a level method or `log()`. The objects you pass in are never modified.

---

## `redact_sensitive()`

```python
from eero.logging import redact_sensitive

redact_sensitive({"password": "hunter2", "username": "alice"})
# {'password': '[REDACTED:7chars]', 'username': 'alice'}
```

Behavior, verified against `src/eero/logging.py`:

- **Mappings, lists and tuples** are inspected, in any combination and nesting: a top-level list of dicts, a tuple inside a dict, a list inside a list inside a dict. A bare string or other non-container value is returned **unchanged** — `redact_sensitive("s=abc123")` does **not** redact anything, because there's no key to match against. Sensitive values must sit under a key to be caught.
- The result is always a **new** structure; the argument is never mutated. A mapping comes back as a plain `dict` (keys unchanged), a `list` stays a `list`, a `tuple` stays a `tuple`.
- Matching is a **case-insensitive substring search** (`re.search`, not an exact-match) on `str(key)`, so a key merely *containing* one of the patterns is redacted — e.g. `access_key_id` matches on `key`, `X-Api-Key` matches on `api_key`/`key`. Non-string keys (`1`, `("a", "token")`, `None`) never raise; they are matched by their text form and kept as the original key objects.
- When a key matches, its whole value is replaced by the redacted form below, whatever the value's type.
- Recursion stops at 16 levels of nesting and at any reference cycle (a container that contains itself, directly or through other containers). The offending container is replaced by the fixed text `[REDACTED:cyclic-or-too-deep]` instead of raising `RecursionError`, so nothing below the cap can leak. A container that is merely referenced twice (no cycle) is redacted normally both times.

### The exact redacted field-name patterns (`DEFAULT_SENSITIVE_PATTERNS`)

```python
{
    "token", "password", "passwd", "secret", "key", "credential",
    "session_id", "session", "cookie", "auth", "api_key", "apikey",
    "access_token", "refresh_token", "user_token", "bearer",
    "authorization", "private",
    "login", "email", "phone", "sms", "serial", "mac", "mac_address", "ssid",
}
```

The first eighteen are *credential-shaped* (`_ZERO_VISIBILITY_PATTERNS`) and never show any of the value; the last eight are *identifier-shaped* and keep a short visible prefix.

### Redacted value format

| Input value | Redacted output |
|---|---|
| `None` | `[NONE]` |
| `True` / `False` | `[REDACTED:bool]` |
| `123` / `1.5` | `[REDACTED:number]` |
| `""` | `[EMPTY]` |
| `"abc"` (≤ `visible_chars`) | `[REDACTED:3chars]` |
| `"secret123"` (> `visible_chars`) | `secr...[REDACTED:9chars]` |

The `secr...` prefix form applies only to identifier-shaped keys (`email`, `phone`, `login`, `mac`, `ssid`, `serial`, `sms`); credential-shaped keys always produce `[REDACTED:Nchars]` regardless of `visible_chars`.

### Before / after

```python
raw = {"session_id": "s_9f8a7b6c5d4e", "email": "you@example.com", "status": "ok"}
```

```text
Before: {'session_id': 's_9f8a7b6c5d4e', 'email': 'you@example.com', 'status': 'ok'}
After:  {'session_id': '[REDACTED:14chars]', 'email': 'you@...[REDACTED:15chars]', 'status': 'ok'}
```

> **Note**: `email`/`phone`/`login` are identifier-shaped patterns: the first 4 characters remain visible. Credential-shaped keys (`token`, `session*`, `cookie`, `auth*`, `password`, `secret`, `key`, …) show only the length. To redact additional field names of your own, extend the pattern set with `add_sensitive_pattern()` below.

---

## `add_sensitive_pattern()`

Builds a pattern set that is the defaults plus your own field name. It does not mutate
`DEFAULT_SENSITIVE_PATTERNS` in place; it returns a new `FrozenSet[str]` you pass back into
`get_secure_logger()`. No cache reset is involved: the new set gets its own compiled regex the
first time it is used, independently of every other set:

```python
from eero.logging import add_sensitive_pattern, get_secure_logger

patterns = add_sensitive_pattern("my_webhook_url")
logger = get_secure_logger(__name__, sensitive_patterns=patterns)

logger.debug("Config: %s", {"my_webhook_url": "https://hooks.example.com/T00/B00/XXXX"})
# Config: {'my_webhook_url': 'http...[REDACTED:38chars]'}
```

> **Note**: `add_sensitive_pattern()` is pure — it touches no global state and has no effect on
> any existing logger; only loggers you build with the returned set use it.

---

## ⚠️ Warning: `logging.basicConfig(level=logging.DEBUG)` Is Not Safe

> ⚠️ **Warning:** `logging.basicConfig(level=logging.DEBUG)` sets the **root** logger to `DEBUG`, which also enables `DEBUG` for every third-party library, including `aiohttp`. `aiohttp`'s own client logging at `DEBUG` includes request/response **headers** — which includes the `X-User-Token` header and the `Cookie` header (`s=<token>`), both carrying your live session token. `SecureLoggerAdapter` only wraps loggers obtained through `get_secure_logger()`; it cannot intercept or redact `aiohttp`'s own log records.

The correct recipe: turn on `DEBUG` for this SDK's own loggers only, and keep `aiohttp` (and everything else) at `INFO` or `WARNING`:

```python
import logging

# Root/default level for everything, including aiohttp.
logging.basicConfig(level=logging.WARNING)

# Debug this SDK's own logging (both the secure-logger-backed modules
# and the plain-logger-backed ones) without turning on aiohttp's
# header-dumping debug output.
logging.getLogger("eero").setLevel(logging.DEBUG)
logging.getLogger("aiohttp").setLevel(logging.WARNING)
```

---

## Safe-Debugging Checklist (Filing a Bug Report)

Before pasting logs into a GitHub issue:

- [ ] Confirm you did **not** set the root logger to `DEBUG` (see the warning above) — if you did, re-run with `logging.getLogger("eero").setLevel(logging.DEBUG)` instead and capture fresh output
- [ ] Search the log for `X-User-Token:`, `Cookie:`, `Set-Cookie:`, `s=`, or any `session_id`/`user_token` value and redact manually — the SDK's redaction only covers what passes through `get_secure_logger()`
- [ ] Scrub the account email / phone from any `aiohttp` or plain-logger output — the secure logger redacts them only when they appear as dict keys
- [ ] Scrub the network's Wi-Fi password and guest network password if present in a `get_network()` response dump
- [ ] Truncate or omit full response bodies where possible — device MACs, hostnames, and nicknames are personally identifying
- [ ] Double-check any `extra={...}` dicts you added yourself for custom debug statements

---

## Other Transport Security Behavior

Verified in `src/eero/api/base.py` and `src/eero/const.py`:

| Behavior | Detail |
|---|---|
| 🔑 Credential placement | The session token is sent as the `X-User-Token` header (plus the `s=` cookie while `send_legacy_cookie=True`) **only** on requests whose hostname and scheme match the configured API host. Any other host, or plain `http`, gets no credential and a `WARNING` log line. The token is never written to the shared `aiohttp` cookie jar |
| 🚫 Caller-supplied credential headers | A `headers=` dict containing `X-User-Token`, `Cookie`, or `Authorization` (any case) raises `EeroValidationException` before the request is sent |
| 🧹 Header validation | Every header value must be printable ASCII with no CR/LF (`EeroValidationException` otherwise) — header injection is impossible by construction |
| 🔁 Redirects | Never followed — `allow_redirects=False` is forced on every request and cannot be re-enabled (`allow_redirects=True` raises `EeroValidationException`); any `3xx` response is rejected as an `EeroAPIException` rather than letting the token travel to a different host |
| 📏 Response size cap | `MAX_RESPONSE_BYTES = 10 * 1024 * 1024` (10 MiB) — the body is streamed in 64 KiB chunks and the request is aborted with `EeroAPIException` if the cap is exceeded |
| 🙈 Error bodies | The raw text of an error response is never embedded in an exception message or log line. The exception message is the recognised `meta.error` catalogue string (trimmed, lowercased) or the fixed label `unrecognised error string`; `EeroAPIException` and its subclasses prefix it with `API error <status>: `, while `EeroAuthenticationException` (all 401s), `EeroRateLimitException` and API-reported `EeroValidationException` carry no status in the message at all. `meta.code`, the raw body and the URL are never embedded (a byte count appears only for a 2xx whose body is not valid JSON). Read `err.envelope` / `err.error_code` / `err.status_code` for details; the parsed envelope is logged only through the secure logger |
| 🧾 URLs in logs | The request URL (which carries network, device and eero identifiers) is logged only at `DEBUG` (`Request: …`, `Resource not found at …`, `Request to … timed out`, `Network error: … for URL: …`, `Retrying GET …`). The `ERROR` lines for a timeout or a network failure carry just the HTTP method (and, for a network failure, the exception type), and the `WARNING` for a GET retry carries just the attempt count. `tests/api/test_log_hygiene.py` fails if an identifier appears in any `eero.api.base` record above `DEBUG` |
| 🔒 HTTPS only | `API_HOST = "https://api-user.e2ro.com"`; `API_ENDPOINT = api_endpoint("2.2")`; device writes (`DEVICE_UPDATE_ENDPOINT`), multi-static-IP and secondary-WAN use `api_endpoint("2.3")` (see [API Reference](API-Reference#constants)) — HTTPS-only hardcoded hosts; there is no HTTP fallback |

See [Error Handling](Error-Handling#http-status--exception-mapping) for the full status-to-exception mapping these behaviors feed into.

---

## Credential Storage

Session tokens are persisted at rest via `KeyringStorage` (OS keyring), `FileStorage` (owner-only `0600` JSON file), `MemoryStorage`, or `ChainedStorage` combining the two — selected by the `use_keyring` / `cookie_file` arguments on `EeroClient`. See [Credential Storage](Credential-Storage) for the full backend selection logic.

`AuthCredentials` (the record every backend loads and saves) leaves `session_id` out of its `repr()`, so printing, f-string formatting or a traceback that shows the record never exposes the token. Equality and `to_dict()` / `from_dict()` still include it.

---

## ⚠️ This Is an Unofficial Client

> ⚠️ **Warning:** This SDK talks to a reverse-engineered, undocumented Eero Cloud API. It is not affiliated with or endorsed by Eero or Amazon. Only use it against Eero accounts you own — logging in against an account you don't control, or attempting to enumerate/brute-force the OTP flow, is misuse of someone else's account and network.

---

## 🔗 Related Pages

- [Error Handling](Error-Handling) — the `EeroException` hierarchy and HTTP status mapping
- [Credential Storage](Credential-Storage) — keyring, file, and memory storage backends
- [Authentication](Authentication) — the OTP login flow and session lifecycle
- [Configuration](Configuration) — client setup & options
- [Troubleshooting](Troubleshooting) — common issues & fixes
