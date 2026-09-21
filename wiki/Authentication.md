# 🔑 Authentication

The OTP login flow, how the session token travels on each request, server-driven refresh, and non-interactive token seeding.

---

## 🔁 The OTP Flow

Eero has no passwords in this SDK's flow — `login()` triggers a one-time code sent by Eero to the email address or phone number you pass, and `verify()` confirms that code against the session.

```python
import asyncio
from eero import EeroClient
from eero.exceptions import EeroAuthenticationException

async def main() -> None:
    async with EeroClient() as client:
        if not client.is_authenticated:
            await client.login("you@example.com")  # or a phone number

            code = input("Enter the verification code sent by Eero: ")
            try:
                await client.verify(code)
            except EeroAuthenticationException as err:
                print(f"Verification failed: {err.error_code}")
                return

        account = await client.get_account()
        print(account["data"])

asyncio.run(main())
```

> **Note**: `client.is_authenticated` is a **property**, not a coroutine — never `await` it. This holds at every layer: `AuthAPI.is_authenticated`, `EeroAPI.is_authenticated`, and `EeroClient.is_authenticated` are all `@property`.

### `login(user_identifier)`

`EeroClient.login()` → `EeroAPI.login()` → `AuthAPI.login()`. Accepts a single string: an email address or a phone number. Internally it POSTs a form-encoded body (`login=<identifier>`, `Content-Type: application/x-www-form-urlencoded`) to `/2.2/login`, pulls `user_token` out of the response, and stores it as the (not-yet-verified) `session_id`. Any previously stored credentials are cleared first — starting a new login always discards the old session.

Returns `True` when the response carried a token, `False` when it did not. Raises `EeroAuthenticationException` if the API rejects the request — including a server-rejected identifier (HTTP 400 with an `error.form.*` code, which the transport raises as `EeroValidationException` and `login()` re-wraps); the exception carries the response `envelope` and `error_code`. Raises `EeroRateLimitException` if the login endpoint rate-limits, and `EeroNetworkException`/`EeroTimeoutException` on transport failure.

### `verify(verification_code)`

Confirms the code against the pending session. The request is a form-encoded POST (`code=<code>`) to `/2.2/login/verify`, authenticated with the token obtained by `login()`. The response carries the account object, not a new token — the `session_id` set during `login()` is what is now verified, and it is persisted to storage on success. `EeroClient.verify()` additionally calls `clear_cache()` so nothing stale from a previous session lingers.

```python
await client.login("you@example.com")
await client.verify("123456")
```

Raises `EeroAuthenticationException("No session token available. Login first.")` if you call `verify()` before `login()`.

A wrong code surfaces as `EeroAuthenticationException` raised by the transport for the API's `401`. The exception message is the recognised `meta.error` catalogue string (trimmed, lowercased) or the fixed label `unrecognised error string` — `EeroAuthenticationException` carries no HTTP status in the message, and `meta.code`, the raw body and the URL are never embedded. The full response envelope is on `err.envelope` and the `meta.error` string on `err.error_code`. Branch on `error_code`, not on the message text — see [Error Handling](Error-Handling#common-attributes-envelope-error_code-message).

### `resend_verification_code()`

Available on `AuthAPI` (not exposed on `EeroClient`/`EeroAPI` — call it via `client._api.auth.resend_verification_code()` if you need it, though this reaches into a private attribute that is not covered by semver). POSTs an empty JSON object (`{}`) to `/2.2/login/resend`, authenticated with the pending `session_id` from `login()`. Returns `False` on an `EeroAPIException` (any status other than 401/429/400-validation); raises `EeroAuthenticationException` if the pending token is rejected with a 401 or if no login is in progress, `EeroRateLimitException` on 429, `EeroNetworkException` on transport error.

---

## 🚚 How the Session Token Travels

Once a session token exists, the SDK attaches it to every request itself — there is nothing to configure and no cookie jar involved:

| Carrier | Sent when | Notes |
|---|---|---|
| `X-User-Token: <token>` header | On every request to the API host over `https` | The primary credential. Built per request by the transport (`BaseAPI._build_credentials`) |
| `Cookie: s=<token>` | Same rule, while the `send_legacy_cookie` constructor option is `True` (the default) | Passed as a per-request cookie, never written to the shared `aiohttp` cookie jar. Set `send_legacy_cookie=False` to send only the header |

Three guarantees around this:

- **Host and scheme gate.** The credential is only attached when the resolved request URL's hostname exactly matches the configured API host **and** the scheme matches (`https`). A request to any other host, or to the right host over plain `http`, is sent with no credential at all and logs a warning.
- **Caller-supplied credential headers are rejected.** Passing `X-User-Token`, `Cookie`, or `Authorization` in a `headers=` dict to any transport method raises `EeroValidationException` — the credential builder is the only writer of those names.
- **Redirects are always refused.** `allow_redirects=False` is set on every request, any `3xx` raises `EeroAPIException`, and passing `allow_redirects=True` yourself raises `EeroValidationException`. The token can never follow a redirect to another host.

Every request also carries `Accept: application/json`, the SDK's `User-Agent`, and `X-Accept-Language` (constructor option `accept_language`, default `en-US`). See [Configuration](Configuration#-request-headers-and-transport) for the header set and [Logging and Security](Logging-and-Security) for what this means when you enable `DEBUG` logging.

---

## ⏳ Session Lifetime

**There is no client-side session expiry.** `AuthCredentials` stores exactly one value — the session token — and `is_authenticated` means "a session token is present". The server is the sole authority on whether that token is still valid; it signals invalidity with a `401`, which the SDK raises as `EeroAuthenticationException`.

Consequences:

- A freshly started process with a stored token reports `is_authenticated == True` even if the server has since invalidated the session. You find out on the first request.
- Nothing in the SDK counts days or "expires" a token locally. Do not build "days remaining" logic on top of the credential record — there is no field for it.

### `refresh_session()`

`AuthAPI.refresh_session()` POSTs to `/2.2/login/refresh`, authenticated by the current session token, with the two-character JSON body `""` (`Content-Type: application/json`). There is no refresh token; the session token is the only credential. The refresh response carries a token in its body, which the SDK deliberately ignores — the current session token remains the one in use.

| Outcome | Return / raise |
|---|---|
| HTTP 200 | returns `True` |
| 401 whose `error_code` is in the verification group (`error.verification.*`, `error.login.unknown`, `error.login.blocked`, `error.too.many.resends`, `error.email.unverified`) or is `error.session.refresh` | returns `False`; stored credentials are **kept** (the session is mid-verification — finish `verify()` — or merely due for a refresh) |
| Any other 401 — `error.session.expired` / `.invalid` / `.revoked`, any other recognised catalogue string, or an unrecognised/absent `error_code` | returns `False`; stored credentials are **deleted** from memory and every storage backend |
| Any other API error from the refresh endpoint (any status, including 429) | returns `False` |
| Network or timeout failure | raises `EeroNetworkException` / `EeroTimeoutException` |
| No session token present | raises `EeroAuthenticationException("No session token available. Login first.")` |

**Concurrent refreshes are coalesced.** If several requests hit a refresh signal at once, the first caller performs the refresh and the others await its result instead of issuing their own. A waiter that has waited longer than 30 seconds gives up and returns `False`, so its own original authentication error is raised.

### `ensure_authenticated()`

Returns `is_authenticated` — `True` if a session token is present, `False` otherwise. It never raises for the "not logged in" case and never triggers a refresh: refreshes are exclusively server-driven (below).

### `get_auth_token()`

Returns the current `session_id` string, or `None` when no token is present. This is what `EeroClient.get_account()` uses under the hood before each `/account` call, and what the transport uses to source the token for a post-refresh replay.

> **Note**: None of `refresh_session()`, `ensure_authenticated()`, or `get_auth_token()` are exposed on `EeroClient` or `EeroAPI` — they live only on `AuthAPI`. In normal usage you never need to call any of them directly (see transparent refresh below).

---

## 🔄 Transparent Refresh-and-Replay

You usually don't need to call `refresh_session()` yourself. Every `AuthenticatedAPI` (i.e. every domain API — `NetworksAPI`, `DevicesAPI`, etc.) wires `AuthAPI.refresh_session` as a hook. When `BaseAPI._request()` gets an HTTP 401 whose JSON body is shaped `{"meta": {"error": "error.session.refresh", ...}}`, it:

1. Calls the refresh hook (`refresh_session()`).
2. If refresh succeeds, replays the original request **once**, rebuilding the headers and cookie from scratch with the token supplied by `get_auth_token()` (a `_refresh_retried` guard prevents loops).
3. If refresh fails, the original `EeroAuthenticationException` is raised as usual.

This replay is a single re-issue of the original call after successful re-authentication — it applies to writes as well as reads, and it is distinct from the bounded GET retry policy (see [Configuration](Configuration#-retry-policy)), which never touches writes.

`AuthAPI` itself does **not** set this hook on its own requests — only the `AuthenticatedAPI` base class does — so the refresh endpoint can't trigger a refresh loop against itself.

For long-running processes this means the session can now be kept alive indefinitely without human intervention, as long as the server keeps accepting refreshes: the process holds one token, the server asks for a refresh when it wants one, and the SDK complies and continues. When the server instead reports the session as expired, invalid, or revoked, the SDK clears the stored credential and raises `EeroAuthenticationException`; that is your cue to run the OTP flow (or re-seed a token) again.

---

## 🚪 `logout()` vs `clear_session_token()`

These are not the same operation:

| Method | Calls the remote API? | What it clears |
|---|---|---|
| `logout()` | **Yes** — POSTs a form-encoded body to `/2.2/logout` whose single field is literally named `Cookie` and carries `s=<token>`, authenticated with the same token | Local `AuthCredentials` and storage. If not currently authenticated it returns `False` immediately without an API call. A `401` from the server (session already invalid), any other `EeroAPIException`, or a transport failure during the POST is swallowed — local credentials are still deleted, and `True` is returned. An `EeroRateLimitException` (429) or `EeroValidationException` (400) propagates and local credentials are **not** cleared |
| `clear_session_token()` | **No** | Clears `session_id` in memory and calls `storage.clear()`, deleting the keyring entry / credential file in every backend of the chain |

```python
await client.logout()             # tells the server, then wipes local state
await client.clear_session_token() # wipes local state only, no network call
```

`EeroClient.set_session_token()` / `clear_session_token()` additionally call `clear_cache()`, and `EeroClient.logout()` clears the cache when it returns `True` (i.e. whenever credentials were actually present), so the in-memory response cache never serves data from a different session.

There is also `AuthAPI.clear_auth_data()` (not exposed on `EeroClient`/`EeroAPI`); it does the same as `clear_session_token()` (clears memory and deletes the stored record in every backend) and additionally resets the internal login-in-progress flag.

---

## 🤖 Non-Interactive / CI

For headless environments where you can't sit through an OTP prompt each run, seed a previously-obtained session token directly:

```python
await client.set_session_token(token)
```

This writes the token into `AuthCredentials.session_id` and persists it via the configured storage backend; from then on every request carries it as described above. Raises `EeroValidationException` for an empty or non-string token, and for a token containing any character outside printable ASCII (including CR/LF) — the same rule the transport applies to every header value, since the token is sent verbatim as `X-User-Token`. A rejected token is never persisted.

See [Configuration](Configuration#-headless--container--ci-recipes) for the full recipe (reading the token from your own env var and picking a storage backend).

---

## 💾 What Gets Persisted

`AuthCredentials` (defined in `src/eero/api/auth_storage.py`) has exactly one field, and this is the exact record written by `FileStorage`/`KeyringStorage`:

```json
{
  "session_id": "…",
  "schema_version": 2
}
```

`schema_version` is the value of `eero.const.CREDENTIAL_SCHEMA_VERSION`. A record loaded **without** that key is treated as legacy: it may carry the pre-v3.0.0 `user_token` key instead of `session_id`, plus the extra fields earlier releases wrote alongside the token. On first load the SDK keeps only the token (reading `session_id`, falling back to `user_token`), drops everything else, and re-saves the record in the shape above. This happens once per backend, is idempotent, and logs no values.

> **Note**: If you parse the credential file with your own tooling, read `session_id` and nothing else — the extra fields written by 7.x are gone and must not be relied on. See [Migration](Migration#the-credential-record) for their names and what to do about them.

For the storage backends themselves (keyring vs. file vs. memory vs. chained), see [Credential Storage](Credential-Storage).

---

## 🍏 Amazon Login Accounts

If your Eero account was created via "Sign in with Amazon," this SDK's email/phone OTP flow does not apply directly. See [Troubleshooting](Troubleshooting#amazon-login-accounts) for the workaround.

---

## 🚨 Failure Modes

| Scenario | Exception |
|---|---|
| `verify()` called with a wrong code (API returns 401) | `EeroAuthenticationException` — inspect `err.error_code` / `err.envelope` |
| `login()` with an identifier the server rejects (400, `error.form.*`) | `EeroAuthenticationException` (wrapping the transport's `EeroValidationException`; `error_code` is the `error.form.*` string) |
| `verify()` / `resend_verification_code()` / `refresh_session()` called before `login()` (no session token) | `EeroAuthenticationException` (`"No session token available. Login first."`) |
| `refresh_session()` receives any API error (401, 429, 5xx, …) | Returns `False` — does not raise. On a 401, credentials are kept only for the verification group or `error.session.refresh`; every other 401 deletes them |
| `refresh_session()` hits a network or timeout failure | `EeroNetworkException` / `EeroTimeoutException` |
| `set_session_token()` with an empty/non-string token, or one containing non-printable-ASCII characters (including CR/LF) | `EeroValidationException` |
| Any request whose session the server reports as expired, invalid, or revoked | `EeroAuthenticationException` (stored credentials cleared when this happens during a refresh) |
| A `headers=` dict containing `X-User-Token`, `Cookie`, or `Authorization` | `EeroValidationException` |
| Transport-level failure during login/verify/refresh | `EeroNetworkException` / `EeroTimeoutException` |

A `403` with `error.access.denied` is **not** an authentication failure: it raises `EeroAccessDeniedException` (`is_auth_error()` is `False`) and leaves the stored credentials alone — the session is valid, the account is simply not permitted.

All exception classes derive from `EeroException`, expose `is_auth_error()`, and carry `envelope` and `error_code`. See [Error Handling](Error-Handling) for the full hierarchy and the `meta.error` catalogue groups.

---

## 🔗 Related Pages

- [Home](Home) — Overview and quick start
- [Configuration](Configuration) — Constructor options, request headers, retry policy, and storage-selection table
- [Credential Storage](Credential-Storage) — Deep dive on `CredentialStorage` backends
- [Error Handling](Error-Handling) — The `EeroException` hierarchy and the `envelope` / `error_code` attributes
- [Troubleshooting](Troubleshooting) — Common issues & fixes, including Amazon-login accounts
