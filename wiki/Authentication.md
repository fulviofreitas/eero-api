# 🔑 Authentication

The OTP login flow, session lifetime, transparent refresh, and non-interactive token seeding.

---

## 🔁 The OTP Flow

Eero has no passwords in this SDK's flow — `login()` triggers a one-time code sent by Eero to the email address or phone number you pass, and `verify()` exchanges that code for a session.

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
                print(f"Verification failed: {err}")
                return

        account = await client.get_account()
        print(account["data"])

asyncio.run(main())
```

> **Note**: `client.is_authenticated` is a **property**, not a coroutine — never `await` it. This holds at every layer: `AuthAPI.is_authenticated`, `EeroAPI.is_authenticated`, and `EeroClient.is_authenticated` are all `@property`.

### `login(user_identifier)`

`EeroClient.login()` → `EeroAPI.login()` → `AuthAPI.login()`. Accepts a single string: an email address or a phone number. Internally it POSTs to the login endpoint, pulls `user_token` out of the response, and stores it as the (not-yet-verified) `session_id`. Any previously stored credentials are cleared first — starting a new login always discards the old session.

Raises `EeroAuthenticationException` if the API rejects the request, `EeroNetworkException` on a transport-level failure.

### `verify(verification_code)`

Exchanges the code for a confirmed session. On success, `AuthCredentials.session_expiry` is set to **30 days from now** and the session cookie (`s=<session_id>`) is written into the aiohttp cookie jar and persisted to storage. `EeroClient.verify()` additionally calls `clear_cache()` on success so nothing stale from a previous session lingers.

```python
await client.login("you@example.com")
await client.verify("123456")
```

Raises `EeroAuthenticationException` — with the message `"Verification code incorrect"` specifically when the API returns HTTP 401 — or `EeroAuthenticationException("No session token available. Login first.")` if you call `verify()` before `login()`.

### `resend_verification_code()`

Available on `AuthAPI` (not exposed on `EeroClient`/`EeroAPI` — call it via `client._api.auth.resend_verification_code()` if you need it, though this reaches into a private attribute). Re-triggers the code send using the pending `session_id` from `login()`. Returns `False` on API failure instead of raising; raises `EeroAuthenticationException` if no login is in progress, `EeroNetworkException` on a transport error.

---

## ⏳ Session Lifetime

A verified session is valid for **~30 days**. The exact field tracked in `AuthCredentials` (`src/eero/api/auth_storage.py`) is `session_expiry: Optional[datetime]` — there is no separate "days remaining" property; you derive that yourself from `session_expiry` if you need it, but note this field is internal to `AuthCredentials` and not exposed as a public attribute on `EeroClient`/`EeroAPI`.

### `refresh_session()`

`AuthAPI.refresh_session()` uses the stored `refresh_token` to mint a new session without a fresh OTP. It tries each URL in `REFRESH_ENDPOINTS` (`/login/refresh`, then `/account/refresh`) in order; a `404` from one just moves to the next, any other API error (401, 403, 5xx) is terminal and clears all local credentials immediately. Raises `EeroAuthenticationException("No refresh token available")` if there's no refresh token to use.

### `ensure_authenticated()`

Checks `is_authenticated`, and if the stored `session_expiry` has passed **and** a `refresh_token` is present, calls `refresh_session()` for you. Returns `True`/`False` — it never raises for the "not logged in" case, it just returns `False`.

### `get_auth_token()`

Calls `ensure_authenticated()` internally, then returns the current `session_id` string (or `None` if not authenticated). This is what `EeroClient.get_account()` uses under the hood to pull a valid token before each `/account` call.

> **Note**: None of `refresh_session()`, `ensure_authenticated()`, or `get_auth_token()` are exposed on `EeroClient` or `EeroAPI` — they live only on `AuthAPI`. In normal usage you never need to call any of them directly (see transparent refresh below).

---

## 🔄 Transparent Refresh-and-Retry

You usually don't need to call `refresh_session()` yourself. Every `AuthenticatedAPI` (i.e. every domain API — `NetworksAPI`, `DevicesAPI`, etc.) wires `AuthAPI.refresh_session` as a hook (`self._refresh_hook`). When `BaseAPI._request()` gets an HTTP 401 whose JSON body is shaped `{"meta": {"error": "error.session.refresh", ...}}`, it:

1. Calls the refresh hook (`refresh_session()`).
2. If refresh succeeds, transparently retries the original request **once** (a `_refresh_retried` guard prevents infinite loops).
3. If refresh fails, the original `EeroAuthenticationException` is raised as usual.

`AuthAPI` itself does **not** set this hook on its own requests — only the `AuthenticatedAPI` base class does — so the refresh endpoints can't trigger a refresh loop against themselves.

---

## 🚪 `logout()` vs `clear_session_token()`

These are not the same operation:

| Method | Calls the remote API? | What it clears |
|---|---|---|
| `logout()` | **Yes** — POSTs to `/logout` with the current session token | Local `AuthCredentials` (all fields), cookie jar, and storage. If not currently authenticated it returns `False` immediately without an API call. A `401` from the server (session already invalid) or any other API/network error during the POST is swallowed — local credentials are cleared regardless. |
| `clear_session_token()` | **No** | Only `session_id` and `session_expiry` on `AuthCredentials`, plus the cookie jar and storage (`refresh_token` is left untouched in memory, but the persisted record is re-saved with the cleared fields) |

```python
await client.logout()             # tells the server, then wipes local state
await client.clear_session_token() # wipes local state only, no network call
```

`EeroClient.logout()` and `EeroClient.set_session_token()` / `clear_session_token()` additionally call `clear_cache()` so the in-memory response cache never serves data from a different session.

There is also `AuthAPI.clear_auth_data()` (not exposed on `EeroClient`/`EeroAPI`), which clears in-memory credentials **and** calls `storage.clear()` to delete the underlying keyring entry or file entirely — a stronger operation than `clear_session_token()`, which re-saves an emptied record rather than deleting it.

---

## 🤖 Non-Interactive / CI

For headless environments where you can't sit through an OTP prompt each run, seed a previously-obtained session token directly:

```python
await client.set_session_token(token)
```

This writes the token into `AuthCredentials.session_id`, sets `session_expiry` to 30 days out, installs the `s=` cookie, and persists it via the configured storage backend. Raises `EeroValidationException("token", "must be a non-empty string")` for an empty or non-string token.

See [Configuration](Configuration#-headless--container--ci-recipes) for the full recipe (reading the token from your own env var and picking a storage backend).

---

## 💾 What Gets Persisted

`AuthCredentials` (defined in `src/eero/api/auth_storage.py`) has exactly three fields, and these are the exact JSON keys written by `FileStorage`/`KeyringStorage`:

```json
{
  "session_id": "…",
  "refresh_token": "…",
  "session_expiry": "2026-10-10T12:00:00"
}
```

> **Note**: **v3.0.0 renamed `user_token` to `session_id`.** `AuthCredentials.from_dict()` still reads an old `user_token` key as a fallback for backward compatibility with credential files written by pre-v3.0.0 versions, but every write from this version onward uses `session_id`.

For the storage backends themselves (keyring vs. file vs. memory vs. chained), see [Credential Storage](Credential-Storage).

---

## 🍏 Amazon Login Accounts

If your Eero account was created via "Sign in with Amazon," this SDK's email/phone OTP flow does not apply directly. See [Troubleshooting](Troubleshooting#amazon-login-accounts) for the workaround.

---

## 🚨 Failure Modes

| Scenario | Exception |
|---|---|
| `verify()` called with a wrong code (API returns 401) | `EeroAuthenticationException` (`"Verification code incorrect"`) |
| `verify()` / `resend_verification_code()` called before `login()` | `EeroAuthenticationException` (`"No session token available. Login first."`) |
| `refresh_session()` with no stored refresh token | `EeroAuthenticationException` (`"No refresh token available"`) |
| `set_session_token()` with an empty/non-string token | `EeroValidationException` |
| Any request hitting a fully expired session with no usable refresh | `EeroAuthenticationException` |
| Transport-level failure during login/verify/refresh | `EeroNetworkException` |

All exception classes derive from `EeroException` and expose `is_auth_error()`. See [Error Handling](Error-Handling) for the full hierarchy.

---

## 🔗 Related Pages

- [Home](Home) — Overview and quick start
- [Configuration](Configuration) — Constructor options and storage-selection table
- [Credential Storage](Credential-Storage) — Deep dive on `CredentialStorage` backends
- [Error Handling](Error-Handling) — The `EeroException` hierarchy
- [Troubleshooting](Troubleshooting) — Common issues & fixes, including Amazon-login accounts
