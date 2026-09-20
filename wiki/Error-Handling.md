# 🚨 Error Handling

Every error the SDK raises inherits from `EeroException` — here's the full tree, how the API's error catalogue selects the class, and how to handle them.

---

## Exception Hierarchy

All exceptions are defined in `src/eero/exceptions.py`:

```text
Exception
└── EeroException                      (.message, .envelope, .error_code, is_auth_error())
    ├── EeroAuthenticationException    is_auth_error() → True
    ├── EeroRateLimitException
    ├── EeroNetworkException
    ├── EeroTimeoutException
    ├── EeroValidationException        (.field) — client-side validation AND API 400 form errors
    └── EeroAPIException               (.status_code)
        ├── EeroAccessDeniedException
        ├── EeroClientBlockedException
        ├── EeroNotFoundException      (.resource_type, .resource_id)
        ├── EeroPremiumRequiredException   (.feature)
        └── EeroFeatureUnavailableException (.feature, .reason)
```

Every class is exported from the top-level `eero` package (`from eero import EeroNotFoundException` works), alongside the error catalogue helpers `ErrorGroup`, `classify_error_code`, and `exception_for_error` — see [The error catalogue](#the-error-catalogue-eeroerrors).

> ⚠️ **Warning:** `EeroValidationException` is **not** a subclass of `EeroAPIException`, even though the transport raises it for an API `400` carrying a form-error string. It derives from `EeroException` only, because it is also the SDK's own client-side validation error (bad IP literal, bad header value, …). A handler that catches only `EeroAPIException` will **not** see an API validation error — catch `EeroValidationException` explicitly, or catch `EeroException`.

---

## Common attributes: `envelope`, `error_code`, `message`

When the API answers with an error status, the SDK parses the body once and attaches the result to the exception — it does not paste the body into the message:

| Attribute | Type | Value |
|---|---|---|
| `err.envelope` | `Optional[Dict[str, Any]]` | The raw, unmodified JSON response envelope (`{"meta": {...}, ...}`) when the body was a JSON object; `None` when the body was empty, not JSON, or when no response was received at all (`EeroNetworkException`, `EeroTimeoutException`, local `EeroValidationException`) |
| `err.error_code` | `Optional[str]` | `envelope["meta"]["error"]` exactly as the API sent it, when present and a string; otherwise `None` |
| `err.message` / `str(err)` | `str` | For an API error: the recognised catalogue string (trimmed, lowercased) when `error_code` is in the catalogue, or the fixed label `unrecognised error string` when it is absent, empty, or free text. `EeroAPIException` and its subclasses prefix this with `API error <status>: `. Never the body text, never the request URL |

```python
from eero import EeroAPIException, EeroAuthenticationException, EeroNotFoundException

try:
    await client.get_network(network_id="<network-id>")
except EeroAuthenticationException as err:
    if err.error_code == "error.verification.required":
        print("Finish the OTP flow first")
    else:
        print(f"Session rejected: {err.error_code}")
except EeroNotFoundException as err:
    print(err.status_code, err.error_code)         # 404, e.g. "error.network.not.found"
except EeroAPIException as err:
    if err.envelope is not None:
        print(err.envelope["meta"])                 # the API's own error metadata, unmodified
```

Branch on `error_code` (or on the exception class), never on the message string — the message is a fixed, leak-safe label; `error_code` is what the API sent. The envelope is the API's exact response; the SDK does not rewrite or trim it.

The same rule applies to log output: the transport logs the parsed envelope through the redacting secure logger (`DEBUG` for 401/404/429, `ERROR` for other statuses) and never the raw body text. See [Logging and Security](Logging-and-Security#other-transport-security-behavior).

---

## The error catalogue (`eero.errors`)

The API reports failures as `{"meta": {"code": <status>, "error": "<string>"}}`. The `meta.error` strings form a **closed catalogue** of dot-separated identifiers; the SDK keeps that catalogue in `src/eero/errors.py`, groups each string by meaning, and matches **case-insensitively** (surrounding whitespace trimmed). Some error responses omit `meta.error`, and some carry a free-text sentence instead — neither is in the catalogue, and the SDK treats both as "unrecognised".

| Export | What it does |
|---|---|
| `ErrorGroup` (`str, Enum`) | `SESSION`, `SESSION_REFRESH`, `VERIFICATION`, `ACCESS_DENIED`, `NOT_FOUND`, `RATE_LIMIT`, `VALIDATION`, `PREMIUM`, `FEATURE_UNAVAILABLE`, `CLIENT_BLOCKED`, `DOMAIN` |
| `classify_error_code(error_code) -> Optional[ErrorGroup]` | The group a `meta.error` string belongs to, or `None` for `None`/empty/unrecognised/free-text input |
| `message_for_error_code(error_code) -> str` | The normalised catalogue string, or `"unrecognised error string"` (`eero.errors` only — not re-exported from the package root) |
| `exception_for_error(status_code, *, envelope, error_code) -> EeroException` | Builds (does not raise) the exception the transport will raise for a non-2xx/3xx response, with `envelope` and `error_code` attached |
| `SESSION_ERRORS`, `VERIFICATION_ERRORS`, … `DOMAIN_ERRORS` (`FrozenSet[str]`) | The member strings of each group (`eero.errors` only) |

`exception_for_error` is the single place classification happens, and its precedence is fixed:

1. **HTTP 401 → `EeroAuthenticationException`, always**, whatever `meta.error` says.
2. Otherwise a string in a **status-independent** group — `PREMIUM`, `FEATURE_UNAVAILABLE`, `CLIENT_BLOCKED`, `RATE_LIMIT` — selects its class regardless of HTTP status.
3. Otherwise the **HTTP status** selects the class: `403` + `error.access.denied` → `EeroAccessDeniedException`; every `404` → `EeroNotFoundException`; `429` → `EeroRateLimitException`; `400` + a `VALIDATION` string → `EeroValidationException`.
4. Everything else — every `DOMAIN` string, any unrecognised or free-text string, a `403`/`400` that doesn't match above — is `EeroAPIException`.

An unrecognised or free-text `meta.error` **never changes the class chosen by the status** and never raises on its own; it is carried through as `error_code` on whatever exception is raised.

### The groups

| `ErrorGroup` | Catalogue strings | Class raised | Notes |
|---|---|---|---|
| `SESSION` | `error.session.expired`, `error.session.invalid`, `error.session.revoked` | `EeroAuthenticationException` | Terminal. When the refresh endpoint returns one of these, stored credentials are **cleared** (likewise for an unrecognised/absent string on a 401 from refresh) |
| `SESSION_REFRESH` | `error.session.refresh` | `EeroAuthenticationException` — only if the refresh fails | On a 401 the transport calls `refresh_session()` and replays the request once; credentials are never cleared by this string. See [Authentication](Authentication#-transparent-refresh-and-replay) |
| `VERIFICATION` | `error.verification.required`, `.invalid`, `.expired`, `.failure`, `.blocked`, `error.login.unknown`, `error.login.blocked`, `error.too.many.resends`, `error.email.unverified` | `EeroAuthenticationException` | The account is mid-verification or blocked from completing login. Never clears stored credentials |
| `ACCESS_DENIED` | `error.access.denied` | `EeroAccessDeniedException` (on 403) | Authenticated but not permitted. **Not** an auth error; credentials kept |
| `NOT_FOUND` | `error.network.not.found`, `error.eero.no_serial_found`, `error.software_keys.not_found` | `EeroNotFoundException` | Every 404 raises this class, with or without a recognised string |
| `RATE_LIMIT` | `error.rate.limit` | `EeroRateLimitException` | Also raised for any HTTP 429 |
| `VALIDATION` | `error.form.errors`, `error.form.email.unavailable`, `error.form.phone.unavailable`, `error.form.email.malformed`, `error.form.phone.malformed`, `error.invites.format.faulty`, `error.invalid.user.role`, `error.reservation.ip.invalid`, `error.network.multistaticipv2.wan_ip_not_in_range` | `EeroValidationException` (on 400) | `field == "request"`; `envelope` carries the API's detail. Not an `EeroAPIException` — see the warning above |
| `PREMIUM` | `error.premium.user_not_subscribed`, `error.partner.unavailable` | `EeroPremiumRequiredException` | Any status |
| `FEATURE_UNAVAILABLE` | `error.eero.offline`, `error.network.unavailable`, `error.eero.not.capable`, `error.eero.deactivated`, `error.eero.owned_by_organization`, `error.eero.wifibackup.as.gateway`, `error.eero.already.owned`, `error.eero.needs.reset` | `EeroFeatureUnavailableException` | Any status |
| `CLIENT_BLOCKED` | `error.app.version.blocked` | `EeroClientBlockedException` | Any status — the API refuses this client version |
| `DOMAIN` | `error.reservation.failed`, `error.assignment.ip.unavailable`, `error.assignment.port.unavailable`, `error.forward.failed`, `error.backup.access.point.ssid.already.exists`, `error.backup.access.point.ssid.conflict`, `error.max.number.of.backup.access.points.reached`, `error.invite.status.accepted`/`.rejected`/`.revoked`/`.expired`, `error.max.admins.reached`, `error.public_static_ip.reservation.error`, `error.network.transfer.recipient.unverified_phone`/`.unverified_email`/`.mismatched_phone`/`.mismatched_email`/`.ambiguous`, `error.user.amazon_login.exists`, `error.user.amazon_login.email.unavailable`, `error.software_keys.already_used`, `error.stripe.card.incorrect_number`/`.expired`/`.incorrect_cvc`/`.incorrect_zip`/`.declined`/`.processing_error`, `error.stripe.coupon.inappropriate`/`.invalid`/`.missing`, `encryptme.error.email.exists`/`.email.invalid`/`.creation.failed` | `EeroAPIException` | Stay generic; branch on `error_code` |

```python
from eero import ErrorGroup, classify_error_code

classify_error_code("Error.Session.Expired")   # ErrorGroup.SESSION (case-insensitive)
classify_error_code("Something went wrong")    # None — free text
classify_error_code(None)                      # None
```

---

## Exception Reference

| Exception | When it's raised | Extra attributes |
|---|---|---|
| `EeroException` | Base class — not raised directly by the SDK | — |
| `EeroAuthenticationException` | Every HTTP 401 (after the refresh-and-replay attempt, when applicable); also raised locally when an auth operation needs a session token and none is present | — |
| `EeroRateLimitException` | HTTP 429, or `error.rate.limit` on any status | — |
| `EeroNetworkException` | Any `aiohttp.ClientError` (DNS failure, connection reset, TLS error, etc.) | — (`envelope` is `None`) |
| `EeroTimeoutException` | `asyncio.TimeoutError` (request exceeded the configured timeout) | — (`envelope` is `None`) |
| `EeroAPIException` | Blocked redirect (3xx), oversized response body, invalid JSON on a 2xx, and any error status not claimed by a subclass below — including every `DOMAIN` string and every unrecognised string | `status_code` (`Optional[int]`) |
| `EeroAccessDeniedException` | HTTP 403 with `error.access.denied` | `status_code` |
| `EeroClientBlockedException` | `error.app.version.blocked` on any status | `status_code` |
| `EeroNotFoundException` | Every HTTP 404 | `status_code`, `resource_type`, `resource_id` (both `None` when built by the transport, which has no resource context; set when constructed directly) |
| `EeroPremiumRequiredException` | A `PREMIUM` string on any status | `status_code`, `feature` (the generic default when built by the transport) |
| `EeroFeatureUnavailableException` | A `FEATURE_UNAVAILABLE` string on any status | `status_code`, `feature` (the `error_code`), `reason` (the message) |
| `EeroValidationException` | (a) **Locally**, before any network call: `id_from_url()` given an empty/non-string ID; `set_session_token()` given an empty/non-string token; an `accept_language` or any other header value that is not printable ASCII; a caller-supplied `X-User-Token` / `Cookie` / `Authorization` header; `allow_redirects=True`; more than one body carrier on one request; an invalid `cadence` on the data-usage methods; an empty `serial` / `version` on `get_ouicheck`; the DNS write methods given a malformed IP literal, an address of the wrong family, a zone-scoped address, more than 2 servers for one family, an unrecognised DNS mode, or `mode="custom"` without servers. (b) **From the API**: HTTP 400 with a `VALIDATION` string | `field` (the offending argument locally; `"request"` from the API) |

The legacy constructors still work for direct construction — `EeroNotFoundException(resource_type, resource_id)`, `EeroPremiumRequiredException(feature)`, `EeroFeatureUnavailableException(feature, reason)`, `EeroValidationException(field, message)` — and each of those classes also has a `from_response(message, *, envelope=None, error_code=None)` classmethod (plus `status_code=` on the three `EeroAPIException` subclasses) that the transport uses when it has no resource/feature/field context.

---

## HTTP Status → Exception Mapping

What `BaseAPI._request()` (via `exception_for_error`) does for each response:

| HTTP status | Exception raised | Notes |
|---|---|---|
| `200`–`299` | *(none — success)* | `204` or an empty body returns `{}`; invalid JSON on a 2xx raises `EeroAPIException` |
| `300`–`399` | `EeroAPIException` | Redirects are never followed (`allow_redirects=False`, not overridable) and are always rejected, to stop the session token leaking to another host |
| `400` | `EeroValidationException` if `meta.error` is a `VALIDATION` string, else `EeroAPIException` | `field == "request"`; API detail in `envelope` |
| `401` | `EeroAuthenticationException` | Always, whatever the string. `error.session.refresh` first triggers a transparent refresh + single replay; the exception is raised only if there's no refresh hook or the refresh fails. Stored credentials are cleared only when the **refresh endpoint** answers with a `SESSION` string or an unrecognised/absent string — never for `VERIFICATION` or `SESSION_REFRESH` strings |
| `403` | `EeroAccessDeniedException` with `error.access.denied`, else `EeroAPIException` | Not an auth error; credentials kept |
| `404` | `EeroNotFoundException` | Always — with a catalogue string, a free-text sentence, or no `meta.error` at all |
| `429` | `EeroRateLimitException` | See [Caching and Rate Limits](Caching-and-Rate-Limits) |
| any status with a `PREMIUM` / `FEATURE_UNAVAILABLE` / `CLIENT_BLOCKED` / `RATE_LIMIT` string (except 401) | the group's class | Status-independent groups |
| everything else | `EeroAPIException` (`status_code=<actual>`) | The generic fallback, `error_code` set when present |
| response body > `MAX_RESPONSE_BYTES` | `EeroAPIException` | Raised mid-stream, before the body is fully buffered |
| `asyncio.TimeoutError` | `EeroTimeoutException` | Request exceeded the timeout (see [Configuration](Configuration)) |
| `aiohttp.ClientError` | `EeroNetworkException` | Connection-level failures, wrapped with `from err` |

**What is retried before any of these reach you.** Writes (`POST`/`PUT`/`DELETE`/`PATCH`) are never retried by the SDK. A `GET` that fails with `EeroNetworkException`, `EeroTimeoutException`, or a `5xx` `EeroAPIException` is retried up to `get_retries` additional times (constructor option, default `0`); `4xx` and `429` are never retried. The exception you catch is the one from the final attempt. See [Configuration](Configuration#-retry-policy).

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

- `EeroAuthenticationException.is_auth_error()` — always `True`. This is the only class the transport raises for a 401, so in practice it is the only one for which the method returns `True`.
- `EeroAPIException.is_auth_error()` (inherited by `EeroAccessDeniedException` and the other subclasses) — `status_code == 401`, which the transport never produces for these classes; it is `False` for every 403/404/… including `EeroAccessDeniedException`.
- Every other class — `False`.

A 403 is deliberately **not** an auth error: the session is valid, the account simply isn't allowed to do that.

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
> | `EeroForbiddenException` / `EeroForbiddenError` | `EeroAccessDeniedException` |
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
    print(f"Eero API call failed: {err.error_code or err.message}")
```

### Catching narrowly

```python
from eero import (
    EeroAccessDeniedException,
    EeroAPIException,
    EeroAuthenticationException,
    EeroNotFoundException,
    EeroRateLimitException,
    EeroValidationException,
)

try:
    await client.get_devices()
except EeroAuthenticationException as err:
    print(f"Session rejected ({err.error_code}) — need to log in again")
except EeroAccessDeniedException:
    print("This account may not do that on this network")
except EeroNotFoundException:
    print("No such network")
except EeroRateLimitException:
    print("Rate limited — back off")
except EeroValidationException as err:
    print(f"The API rejected the request: {err.error_code}")   # not an EeroAPIException
except EeroAPIException as err:
    print(f"API error {err.status_code}: {err.error_code}")
```

### Branching on `error_code`

```python
from eero import EeroAPIException

try:
    await client.create_reservation(reservation_data={...})
except EeroAPIException as err:
    if err.error_code == "error.assignment.ip.unavailable":
        ...  # pick another address
    else:
        raise
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

### Handling premium / unavailable features

```python
from eero import EeroFeatureUnavailableException, EeroPremiumRequiredException

try:
    await client.get_premium_status()
except EeroPremiumRequiredException as err:
    print(f"Needs an Eero Plus subscription ({err.error_code})")
except EeroFeatureUnavailableException as err:
    print(f"Not available on this network: {err.error_code}")
```

---

## 🔗 Related Pages

- [Migration](Migration#v7x--v800) — the v8.0.0 error-class changes and how to update handlers
- [Authentication](Authentication) — 401 semantics, refresh-and-replay, credential clearing
- [Caching and Rate Limits](Caching-and-Rate-Limits) — avoiding `EeroRateLimitException` in the first place
- [Configuration](Configuration) — request timeouts and the GET retry policy
- [Troubleshooting](Troubleshooting) — common issues & fixes
- [Logging and Security](Logging-and-Security) — `SecureLoggerAdapter` and safe debug logging of failed requests
