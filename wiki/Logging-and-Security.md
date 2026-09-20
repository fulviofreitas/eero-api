# 🛡️ Logging and Security

Why this SDK ships its own logging layer, how redaction works, and how to debug without leaking credentials.

---

## Why the SDK Ships Its Own Logging Layer

The session token travels on every request as the `X-User-Token` header (and, by default, as the `s=` cookie), and JSON response bodies (`{"meta": ..., "data": ...}` envelopes can carry `user_token`, `session_id`, and similar fields). Naive `DEBUG` logging of requests/responses — the first thing anyone reaches for while debugging — will happily print these values verbatim. `src/eero/logging.py` exists so that debug logging is safe by default wherever it's used.

In practice, the modules that handle credentials or response bodies directly opt into it:

| Module | Logger | Why |
|---|---|---|
| `src/eero/api/auth.py` | `get_secure_logger(__name__)` | Handles login, verify, refresh, session tokens |
| `src/eero/api/base.py` (the transport) | `get_secure_logger(__name__)` | Logs parsed error envelopes at `DEBUG`/`ERROR` — never the raw body text — so any credential-shaped field in an error envelope is redacted |
| Domain APIs and `client.py` | plain `logging.getLogger(__name__)` unless a module opts in | Log request method/URL/status and identifiers, not raw payload bodies |

> **Note**: If you add your own debug logging around SDK calls — e.g. logging the raw envelope returned by `get_account()` or `get_devices()` — use `get_secure_logger()` yourself. The SDK's internal loggers only protect the modules listed above.

---

## `get_secure_logger()` — The Recommended Entry Point

A drop-in replacement for `logging.getLogger()`:

```python
from eero.logging import get_secure_logger

_LOGGER = get_secure_logger(__name__)

_LOGGER.debug("Response: %s", {"user_token": "secret123", "status": "ok"})
# Output: Response: {'user_token': 'secr...[REDACTED:9chars]', 'status': 'ok'}
```

`get_secure_logger(name, sensitive_patterns=None, visible_chars=4)` is `@lru_cache`d — repeated calls with the same `(name, sensitive_patterns, visible_chars)` return the same adapter instance.

A custom `sensitive_patterns=` is scoped to the loggers you pass it to. The compiled regex is
cached **per pattern set** (`_get_sensitive_regex()` is keyed by the frozenset it receives), so
the SDK's own loggers, which use `DEFAULT_SENSITIVE_PATTERNS`, and a logger you build with your
own set never share or overwrite each other's regex. Combine the two with
`add_sensitive_pattern()` below when you want the defaults plus your own field names.

---

## `SecureLoggerAdapter`

`SecureLoggerAdapter(logger, extra=None, sensitive_patterns=DEFAULT_SENSITIVE_PATTERNS, visible_chars=4)` wraps a standard `logging.Logger` and overrides `debug()`, `info()`, `warning()`, `error()`, `critical()`, and `exception()`. Each override:

1. Redacts sensitive data in the `extra` kwarg (if it's a dict) via `process()`.
2. Redacts every positional format argument via `redact_sensitive()` before handing off to the underlying `logging.Logger.log()`.

```python
logger = get_secure_logger(__name__)
logger.warning("Auth cookie: %s", {"session_id": "abc123xyz"}, extra={"api_key": "topsecret"})
```

Both the positional dict argument and the `extra` dict are redacted independently before the record is emitted.

---

## `redact_sensitive()`

```python
from eero.logging import redact_sensitive

redact_sensitive({"password": "hunter2", "username": "alice"})
# {'password': 'hunt...[REDACTED:7chars]', 'username': 'alice'}
```

Behavior, verified against `src/eero/logging.py`:

- Only **dicts** are inspected. A bare string or other non-dict value is returned **unchanged** — `redact_sensitive("s=abc123")` does **not** redact anything, because there's no key to match against. Sensitive values must be inside a dict to be caught.
- Matching is a **case-insensitive substring search** (`re.search`, not an exact-match), so a key merely *containing* one of the patterns is redacted — e.g. `access_key_id` matches on `key`, `X-Api-Key` matches on `api_key`/`key`.
- Redaction recurses into nested dicts and into lists of dicts (a list of non-dict items is left as-is).

### The exact redacted field-name patterns (`DEFAULT_SENSITIVE_PATTERNS`)

```python
{
    "token", "password", "passwd", "secret", "key", "credential",
    "session_id", "session", "cookie", "auth", "api_key", "apikey",
    "access_token", "refresh_token", "user_token", "bearer",
    "authorization", "private",
}
```

### Redacted value format

| Input value | Redacted output |
|---|---|
| `None` | `[NONE]` |
| `True` / `False` | `[REDACTED:bool]` |
| `123` / `1.5` | `[REDACTED:number]` |
| `""` | `[EMPTY]` |
| `"abc"` (≤ `visible_chars`) | `[REDACTED:3chars]` |
| `"secret123"` (> `visible_chars`) | `secr...[REDACTED:9chars]` |

### Before / after

```python
raw = {"session_id": "s_9f8a7b6c5d4e", "email": "you@example.com", "status": "ok"}
```

```text
Before: {'session_id': 's_9f8a7b6c5d4e', 'email': 'you@example.com', 'status': 'ok'}
After:  {'session_id': 's_9f...[REDACTED:14chars]', 'email': 'you@example.com', 'status': 'ok'}
```

> **Note**: `email` isn't in `DEFAULT_SENSITIVE_PATTERNS`, so it's logged in full. If your own logging touches account emails or phone numbers, extend the pattern set with `add_sensitive_pattern()` below.

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

> ⚠️ **Warning:** `add_sensitive_pattern()` mutates **process-global** state: it resets
> `_SENSITIVE_REGEX` to `None`, so the *very next* sensitive-key check anywhere in the process
> (across every `SecureLoggerAdapter`, not just yours) recompiles against whatever pattern set
> happens to be passed to it. Call it once at startup — e.g. alongside your logging
> configuration — rather than per-request, and be aware it affects every logger in the process,
> not just the one you're configuring.

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
- [ ] Scrub the account email address / phone number used for login — it's not in `DEFAULT_SENSITIVE_PATTERNS`
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
| 🙈 Error bodies | The raw text of an error response is never embedded in an exception message or log line. The message carries the HTTP status plus `meta.code` / `meta.error` (or a byte count for a non-JSON body); the parsed envelope is attached as `err.envelope` and logged only through the secure logger |
| 🔒 HTTPS only | `API_HOST = "https://api-user.e2ro.com"`, `API_ENDPOINT = f"{API_HOST}/2.2"` (two device-mutation writes use `f"{API_HOST}/2.3"`, see [API Reference](API-Reference#constants)) — HTTPS-only hardcoded hosts; there is no HTTP fallback |

See [Error Handling](Error-Handling#http-status--exception-mapping) for the full status-to-exception mapping these behaviors feed into.

---

## Credential Storage

Session tokens are persisted at rest via `KeyringStorage` (OS keyring), `FileStorage` (owner-only `0600` JSON file), `MemoryStorage`, or `ChainedStorage` combining the two — selected by the `use_keyring` / `cookie_file` arguments on `EeroClient`. See [Credential Storage](Credential-Storage) for the full backend selection logic.

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
