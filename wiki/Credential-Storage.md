# 🔐 Credential Storage

The `CredentialStorage` abstraction, its four concrete backends, and how `create_storage()` picks one.

---

## 🏗️ The `CredentialStorage` Abstraction

Every backend in `src/eero/api/auth_storage.py` implements the same abstract base class:

```python
class CredentialStorage(ABC):
    async def load(self) -> AuthCredentials: ...
    async def save(self, credentials: AuthCredentials) -> None: ...
    async def clear(self) -> None: ...
```

`AuthCredentials` is a plain `@dataclass` with three fields — `session_id`, `refresh_token`, `session_expiry` — plus helpers `is_session_expired()`, `has_valid_session()`, `to_dict()`, `from_dict()`, `clear_session()`, `clear_all()`. Every backend round-trips this object; none of them know about networks, profiles, or anything besides auth state.

`AuthAPI` owns exactly one `CredentialStorage` instance (built by `create_storage()` in its `__init__`) and calls `load()` on `__aenter__`, `save()` after every login/verify/refresh/token-seed, and `clear()` only from `clear_auth_data()`.

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

`load()` calls `keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)`, JSON-decodes the result into an `AuthCredentials`, and — if the loaded session is already expired — calls `clear_session()` on it and re-saves before returning it. `save()` JSON-encodes `credentials.to_dict()` and calls `keyring.set_password(...)`. `clear()` calls `keyring.delete_password(...)`, swallowing `keyring.errors.PasswordDeleteError` (nothing to delete is not an error).

> **Note**: `load()` and `save()` wrap the underlying `keyring` calls in a bare `except Exception` and log at **`DEBUG`**, not a higher level — a locked keyring, missing Secret Service daemon on headless Linux, or any other backend failure is treated as **non-fatal**. `load()` returns an empty `AuthCredentials()` on failure; `save()` just silently no-ops (the docstring/comment on `save()` explicitly notes "using file fallback" — meaning this is safe specifically because `ChainedStorage` is expected to be layered in front of it whenever you need persistence guarantees).

---

## 📄 `FileStorage`

```python
class FileStorage(CredentialStorage):
    def __init__(self, file_path: str) -> None
```

- The path is resolved eagerly in `__init__` via `os.path.abspath(os.path.expanduser(file_path))` — `~` is expanded and the result is made absolute. There is **no default path**; you must always supply one.
- `file_path` is a read-only `@property` returning the resolved path.
- `load()` returns an empty `AuthCredentials()` if the file doesn't exist or fails to parse as JSON (`FileNotFoundError`, `json.JSONDecodeError` caught explicitly; any other exception is caught too and logged at `WARNING`). An expired session found on disk is cleared and re-saved, same as `KeyringStorage`.
- `save()` creates the parent directory with `os.makedirs(cookie_dir, exist_ok=True)`, writes `json.dumps(credentials.to_dict())` to the file, then `os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)` — owner read/write only (`0600`). The exact keys written are:

```json
{
  "session_id": "…",
  "refresh_token": "…",
  "session_expiry": "2026-10-10T12:00:00"
}
```

- `clear()` removes the file with `os.remove()` if it exists; a missing file or any other error is logged at `WARNING` and swallowed (never raises).

---

## ⛓️ `ChainedStorage`

```python
class ChainedStorage(CredentialStorage):
    def __init__(self, primary: CredentialStorage, fallback: CredentialStorage) -> None
```

Only ever constructed by `create_storage()` as `ChainedStorage(primary=KeyringStorage(), fallback=FileStorage(cookie_file))` — but nothing stops you from composing it yourself with any two `CredentialStorage` instances.

| Operation | Order of operations | On partial failure |
|---|---|---|
| `load()` | Try `primary.load()` first. If it returns credentials with a `session_id`, return them immediately. Otherwise try `fallback.load()`. | If the fallback load succeeds (has a `session_id`), the credentials are **migrated back into `primary`** via `primary.save(credentials)` before being returned — so a successful file-backed load quietly repopulates the keyring for next time. |
| `save()` | Try `primary.save()`. | If `primary.save()` raises, the exception is caught, logged at `DEBUG`, and `fallback.save()` is attempted. If **both** raise, the fallback's exception is logged at `ERROR` and swallowed — `save()` never raises to the caller. |
| `clear()` | Calls `primary.clear()` **and** `fallback.clear()` unconditionally (both always run; no early return). | Not explicitly guarded — an exception from either would propagate, since `clear()` has no try/except here (unlike `load`/`save`). |

> ⚠️ **Warning: The `save()` fallback path is dead code.** `KeyringStorage.save()` catches its
> own exceptions internally and returns normally instead of raising (see above). That means
> `ChainedStorage.save()`'s `except` branch — the one that would call `fallback.save()` — never
> fires in practice; a keyring failure on save is invisible, and the file is **never written** as
> part of `save()`. The only path that ever populates the file backend is the **read-side**
> migration in `load()` (a successful `fallback.load()` gets copied back into `primary`) — but
> that only helps if the file already has credentials in it from some other source. Do not rely on
> `ChainedStorage` (i.e. `use_keyring=True` with a `cookie_file` set) for headless/CI/container
> persistence — use `use_keyring=False, cookie_file=...` (plain `FileStorage`) instead, which
> writes on every `save()`.

---

## 🧠 `MemoryStorage`

```python
class MemoryStorage(CredentialStorage):
    def __init__(self) -> None
```

Holds one `AuthCredentials` instance as a plain attribute. `load()`/`save()`/`clear()` just read, overwrite, or reset that attribute — no I/O, no serialization, nothing ever touches disk.

> ⚠️ **Warning:** This is the silent-data-loss backend. `EeroClient(use_keyring=False)` with no `cookie_file` resolves here automatically (see the selection table above) — there is no error, warning, or log line telling you this happened. Every session, once the process exits, is gone. Only use this deliberately (tests, short-lived ephemeral processes, secrets injected fresh every run via `set_session_token()`).

---

## 🗂️ Choosing a Backend

| Deployment scenario | Recommended construction | Why |
|---|---|---|
| 🖥️ Desktop (macOS/Windows/Linux w/ desktop env) | `EeroClient()` (defaults) | `KeyringStorage` alone — OS-encrypted, no file to protect |
| 🐧 Headless Linux (no Secret Service daemon) | `EeroClient(use_keyring=False, cookie_file="/path/to/creds.json")` | Keyring calls fail silently at `DEBUG` and `ChainedStorage.save()`'s file fallback never fires (see warning above) — skip keyring entirely and go straight to `FileStorage` |
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
| Drop the active session but keep other stored state, no server round-trip | `await client.clear_session_token()` |
| Log out and tell the server too | `await client.logout()` |
| Wipe everything, including deleting the keyring entry / cookie file outright | `await client._api.auth.clear_auth_data()` (reaches into the private `AuthAPI`; not exposed on `EeroClient`/`EeroAPI`; not covered by semver) |

All four invalidate `EeroClient`'s in-memory response cache as a side effect where the operation is exposed on `EeroClient` (`set_session_token`, `clear_session_token`, `logout`), so a rotated or cleared session never serves stale cached data.

---

## 🔗 Related Pages

- [Home](Home) — Overview and quick start
- [Configuration](Configuration) — Storage-selection summary table and constructor options
- [Authentication](Authentication) — Login/verify flow, session lifetime, and what gets persisted
- [Logging and Security](Logging-and-Security) — Sensitive-field redaction in logs
- [Troubleshooting](Troubleshooting) — Common issues & fixes
