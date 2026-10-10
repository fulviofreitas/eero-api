# 🔐 Credential Storage

The `CredentialStorage` abstraction, its four concrete backends, and how `create_storage()` picks one.

---

## 🏗️ The `CredentialStorage` Abstraction

Every backend in `src/eero/api/auth_storage.py` implements the same abstract base class:

```python
class CredentialStorage(ABC):
    async def load(self) -> AuthCredentials: ...
    async def save(self, credentials: AuthCredentials) -> bool: ...
    async def clear(self) -> None: ...
```

`AuthCredentials` is a plain `@dataclass` with exactly one field — `session_id` — plus helpers `to_dict()`, `from_dict()`, and `clear_all()`. Every backend round-trips this object; none of them know about networks, profiles, or anything besides the session token. There is no expiry field and no refresh token: the server decides whether a token is still valid, and refreshing reuses the same token (see [Authentication](Authentication#-session-lifetime)).

`to_dict()` produces the persisted record shape, which is the same for every backend:

```json
{
  "session_id": "…",
  "schema_version": 2
}
```

`schema_version` is `eero.const.CREDENTIAL_SCHEMA_VERSION`. A stored record **without** that key is a legacy record from an earlier release — it may use the pre-v3.0.0 `user_token` key instead of `session_id`, and may carry the extra fields 7.x wrote alongside the token (named in [Migration](Migration#the-credential-record)). Each backend's `load()` migrates such a record in place: it keeps the token (reading `session_id`, falling back to `user_token`), drops every other field, and re-saves the record in the current shape. The migration runs once per backend, is idempotent (a record that already carries `schema_version` is never rewritten), and logs no values — a `DEBUG` line that a migration happened, then a read-back check that logs `DEBUG` on match or `WARNING` on mismatch (the in-memory credentials are returned either way).

`save()` never raises and returns whether the backend now holds the saved token, judged by reading it back rather than by the write not raising (a write call that returns normally proves nothing: a no-op keyring accepts everything). Callers that ignore the return value keep working. `MemoryStorage` returns `True` because it holds the record for the life of the process, not because it is durable.

`AuthAPI` owns exactly one `CredentialStorage` instance (built by `create_storage()` in its `__init__`) and calls `load()` on `__aenter__`, `save()` after `verify()` and `set_session_token()` (never after `login()`, whose pending token stays in memory until verification succeeds), and `clear()` from `logout()`, `clear_session_token()`, `clear_auth_data()` and a refresh that reports the session as terminated. `AuthAPI` records the outcome of each save and exposes it as the read-only property `credentials_persisted` (also on `EeroAPI` and `EeroClient`): `False` only when the most recent save of the session was read back and no backend retained it, `True` otherwise (including after a load or a clear). `login()` and `verify()` keep returning only the API outcome, so check this property when losing the session on exit matters.

There are four concrete implementations: `KeyringStorage`, `FileStorage`, `MemoryStorage`, `ChainedStorage`.

---

## 🧭 `create_storage()` — Selection Logic

```python
def create_storage(
    use_keyring: bool = True,
    cookie_file: Optional[str] = None,
) -> CredentialStorage:
```

This is the only place backend selection happens — driven purely by the `use_keyring` / `cookie_file` values you pass into `EeroClient(...)` (which flow through `EeroAPI` → `AuthAPI` unchanged).

| `use_keyring` | `cookie_file` | Backend returned |
|---|---|---|
| `True` | set | `ChainedStorage(primary=KeyringStorage(), fallback=FileStorage(cookie_file))` |
| `True` | `None` | `KeyringStorage()` |
| `False` | set | `FileStorage(cookie_file)` |
| `False` | `None` | `MemoryStorage()` |

In prose: keyring is tried whenever `use_keyring=True`; a file path is only ever consulted as a *fallback* alongside keyring, or as the *sole* backend when you explicitly disable keyring; and if you disable keyring without giving a file path, there is nothing left to fall back to, so credentials live in memory only for the life of the process.

---

## 🔑 `KeyringStorage`

```python
class KeyringStorage(CredentialStorage):
    SERVICE_NAME = "eero-api"
    ACCOUNT_NAME = "auth-tokens"
```

Delegates to the third-party `keyring` package, which resolves a platform backend at import time:

| OS | Backend |
|---|---|
| 🍎 macOS | Keychain |
| 🐧 Linux | Secret Service (GNOME Keyring, KWallet) |
| 🪟 Windows | Windows Credential Locker |

`load()` calls `keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)`, JSON-decodes the result into an `AuthCredentials`, and — if the stored record was a legacy one (no `schema_version` key) — re-saves it in the current shape before returning it. `save()` JSON-encodes `credentials.to_dict()`, calls `keyring.set_password(...)`, then reads the entry back with `keyring.get_password(...)` and returns `True` only if the stored `session_id` matches. `clear()` calls `keyring.delete_password(...)`, swallowing `keyring.errors.PasswordDeleteError` silently (nothing to delete is not an error) and logging any other exception at `DEBUG`; `clear()` never raises.

> **Note**: `load()` and `save()` wrap the underlying `keyring` calls in a bare `except Exception`, so a locked keyring, a missing Secret Service daemon on headless Linux, or any other backend failure is **non-fatal**: `load()` returns an empty `AuthCredentials()` and `save()` returns `False`, never raising. A backend that reports success without persisting anything (e.g. `keyring.backends.null.Keyring`) is caught the same way, by the read-back.
>
> ⚠️ **Warning:** With the default `EeroClient()` (`use_keyring=True`, no `cookie_file`) the keyring is the *only* backend. If it retains nothing, `login()`/`verify()` still succeed and the session works for this process, but it is **not persisted anywhere** and is lost on exit. `save()` logs a fixed `WARNING` ("Keyring did not retain the session; credentials are not persisted and will be lost when this process exits", never the token), and `credentials_persisted` is `False`. To fix it, give the client a `cookie_file` so there is a fallback, or use `use_keyring=False, cookie_file=...`. When `create_storage()` layers a file behind the keyring it builds `KeyringStorage(warn_on_unpersisted=False)`: the keyring failing to retain a write is routine there and handled by the fallback, so that warning is suppressed (the keyring still returns `False` and logs the cause at `DEBUG`).

---

## 📄 `FileStorage`

```python
class FileStorage(CredentialStorage):
    def __init__(self, file_path: str) -> None
```

- The path is resolved eagerly in `__init__` via `os.path.abspath(os.path.expanduser(file_path))` — `~` is expanded and the result is made absolute. There is **no default path**; you must always supply one.
- `file_path` is a read-only `@property` returning the resolved path.
- `load()` returns an empty `AuthCredentials()` if the file doesn't exist or fails to parse as JSON (`FileNotFoundError`, `json.JSONDecodeError` caught explicitly; any other exception is caught too and logged at `WARNING`). A legacy record found on disk is migrated and re-saved, same as `KeyringStorage`.
- `save()` creates the parent directory (`os.makedirs(..., exist_ok=True)`), refuses to write if `file_path` is a symlink, writes `json.dumps(credentials.to_dict())` to a fresh `tempfile.mkstemp()` file in the same directory (created `0600`), `fsync`s it, re-asserts `0600` with `os.chmod`, then atomically swaps it into place with `os.replace()`. A crash mid-write leaves the previous file or nothing — never a partial record. The file is then read back, and `save()` returns `True` only if the stored token matches (a mismatch logs a fixed `WARNING`). Any failure is logged at `ERROR` and swallowed, returning `False`; `save()` never raises. The exact keys written are:

```json
{
  "session_id": "…",
  "schema_version": 2
}
```

> **Note**: If your own tooling reads this file, read `session_id` only. The extra fields 7.x wrote are no longer written, and any copy of them still sitting in an old file is dropped the first time the SDK loads it — see [Migration](Migration#the-credential-record).

- `clear()` removes the file with `os.remove()` if it exists (a missing file is a silent no-op); a removal error is logged at `WARNING` and swallowed (never raises).

---

## ⛓️ `ChainedStorage`

```python
class ChainedStorage(CredentialStorage):
    def __init__(self, primary: CredentialStorage, fallback: CredentialStorage) -> None
```

Only ever constructed by `create_storage()` as `ChainedStorage(primary=KeyringStorage(), fallback=FileStorage(cookie_file))` — but nothing stops you from composing it yourself with any two `CredentialStorage` instances. `ChainedStorage` performs no legacy-record migration of its own; each underlying backend migrates on its own `load()`.

| Operation | Order of operations | On partial failure |
|---|---|---|
| `load()` | Try `primary.load()` first. If it returns credentials with a `session_id`, return them immediately. Otherwise try `fallback.load()`. | If the fallback holds a `session_id`, it is promoted with `primary.save(credentials)`; the primary is then re-loaded and, if the read-back matches, `fallback.clear()` deletes the fallback copy so only one backend holds the live record. If the read-back does not match, the fallback copy is kept (DEBUG log). |
| `save()` | Try `primary.save()`. If it does not raise, read the primary back with `primary.load()` and compare `session_id` to what was just saved. | If `primary.save()` raises, **or** the read-back doesn't match what was saved, `fallback.save()` is attempted (both cases are logged at `DEBUG`) and the fallback is read back too. If **both** the primary path and `fallback.save()` fail, the fallback's exception is logged at `ERROR` and swallowed — `save()` never raises to the caller. Returns `True` if either backend was read back holding the token. A verified primary write does not write the fallback, and instead clears any older fallback record (best effort; a failing clear is logged at `DEBUG` and ignored), so a superseded token cannot be resurrected by `load()`'s promotion if the primary is wiped later. |
| `clear()` | Attempts `primary.clear()` **and** `fallback.clear()` independently; one raising never skips the other. | A backend that raises is logged at `WARNING` (fixed text) and ignored. `clear()` raises only if **both** backends raised, and then re-raises the first error after both were attempted. `logout()`, `clear_session_token()` and `clear_auth_data()` therefore never raise because of a single failing backend; the in-memory token is cleared first in any case. |

> ℹ️ **Note: `save()` verifies the primary write with a read-back before skipping the file
> fallback.** `KeyringStorage.save()` catches its own exceptions internally and returns normally
> instead of raising (see above), and some keyring backends (e.g. `keyring.backends.null.Keyring`)
> report success without persisting anything at all — no exception, ever. Relying on `primary.save()`
> raising would miss both cases, so `ChainedStorage.save()` instead mirrors the read-back-then-act
> pattern `load()`'s own promotion logic already uses: after a primary write that didn't raise, it
> re-`load()`s the primary and compares `session_id` against what it just wrote. Only a matching
> read-back skips the fallback; any mismatch — raised exception or silent no-op alike — falls
> through to `fallback.save()`, so `ChainedStorage` (`use_keyring=True` with a `cookie_file` set) is
> a viable choice for headless/CI/container persistence. `use_keyring=False, cookie_file=...` (plain
> `FileStorage`) remains valid too, and is simpler if you have no use for the keyring at all.

---

## 🧠 `MemoryStorage`

```python
class MemoryStorage(CredentialStorage):
    def __init__(self) -> None
```

Holds one `AuthCredentials` instance as a plain attribute. `load()` returns a copy and `save()` stores a copy, so mutating the live credentials object in place cannot change the stored record without going through `save()`/`clear()`; `clear()` resets the attribute. No I/O, no serialization, nothing ever touches disk.

> ⚠️ **Warning:** This is the silent-data-loss backend. `EeroClient(use_keyring=False)` with no `cookie_file` resolves here automatically (see the selection table above) — there is no error, warning, or log line telling you this happened. Every session, once the process exits, is gone. Only use this deliberately (tests, short-lived ephemeral processes, secrets injected fresh every run via `set_session_token()`).

---

## 🗂️ Choosing a Backend

| Deployment scenario | Recommended construction | Why |
|---|---|---|
| 🖥️ Desktop (macOS/Windows/Linux w/ desktop env) | `EeroClient()` (defaults) | `KeyringStorage` alone — OS-encrypted, no file to protect |
| 🐧 Headless Linux (no Secret Service daemon) | `EeroClient(use_keyring=False, cookie_file="/path/to/creds.json")` | A keyring-only setup retains nothing here (`save()` warns and `credentials_persisted` is `False`); with a `cookie_file`, `ChainedStorage`'s read-back catches that and falls through to the file (see note above), but there's no keyring to gain anything from here anyway — skip it entirely and go straight to `FileStorage` |
| 🐳 Docker container | `EeroClient(use_keyring=False, cookie_file="/data/eero-cookies.json")` | No keyring daemon available inside most containers; skip straight to `FileStorage` and mount `/data` as a volume for persistence across restarts |
| 🤖 CI pipeline | `EeroClient(use_keyring=False, cookie_file=<workspace path>)` + `set_session_token()` from a CI secret | No interactive OTP possible; seed the token directly each run (see [Authentication](Authentication#-non-interactive--ci)) |
| ☁️ Serverless / ephemeral (Lambda-style, no writable disk) | `EeroClient(use_keyring=False)` | Falls through to `MemoryStorage` deliberately — nothing to persist between invocations anyway; re-seed via `set_session_token()` on every cold start |

---

## 🔌 Custom Backends

The source does **not** expose an injection point on `EeroClient`, `EeroAPI`, or `AuthAPI` for supplying your own `CredentialStorage` implementation — `AuthAPI.__init__` always calls `create_storage(use_keyring, cookie_file)` internally, and that function only ever returns one of the four built-in classes. If you need different storage behavior (e.g. a secrets-manager-backed store), your options are:

- Subclass `CredentialStorage` yourself and manage it entirely outside this SDK, using `set_session_token()` / `clear_session_token()` on `EeroClient` to move data in and out of `AuthAPI` at the times that matter to you.
- Use `cookie_file` pointed at a path your own tooling manages (e.g. a file synced from a secrets manager before the process starts).

There is no monkey-patch-free extension point beyond that — don't assume one exists.

---

## 🔄 Rotating / Clearing Credentials

| Goal | Call |
|---|---|
| Rotate to a new externally-issued token | `await client.set_session_token(new_token)` |
| Drop the active session locally, no server round-trip | `await client.clear_session_token()` |
| Log out and tell the server too | `await client.logout()` |
| Same as `clear_session_token()` plus resets the login-in-progress flag | `await client._api.auth.clear_auth_data()` (reaches into the private `AuthAPI`; not exposed on `EeroClient`/`EeroAPI`; not covered by semver) |

Every credential-dropping call above (`clear_session_token`, `logout`, `clear_auth_data`) deletes the stored record from every backend — there is no "re-save an empty record" variant. The operations exposed on `EeroClient` also invalidate its in-memory response cache as a side effect (`set_session_token` and `clear_session_token` always; `logout` when it returns `True`, i.e. whenever credentials were actually present), so a rotated or cleared session never serves stale cached data.

---

## 🔗 Related Pages

- [Home](Home) — Overview and quick start
- [Configuration](Configuration) — Storage-selection summary table and constructor options
- [Authentication](Authentication) — Login/verify flow, session transport, and what gets persisted
- [Migration](Migration#v7x--v800) — What changed in the credential record in v8.0.0
- [Logging and Security](Logging-and-Security) — Sensitive-field redaction in logs
- [Troubleshooting](Troubleshooting) — Common issues & fixes
