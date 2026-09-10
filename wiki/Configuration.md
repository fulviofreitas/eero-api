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

`EeroClient` takes exactly four keyword arguments — nothing else:

```python
from eero import EeroClient

client = EeroClient(
    session=None,        # Optional[aiohttp.ClientSession]
    cookie_file=None,    # Optional[str]
    use_keyring=True,    # bool
    cache_timeout=60,    # int (seconds)
)
```

| Argument | Type | Default | Purpose |
|---|---|---|---|
| `session` | `Optional[ClientSession]` | `None` | Reuse an existing aiohttp session; otherwise one is created and owned by the client for the lifetime of the `async with` block |
| `cookie_file` | `Optional[str]` | `None` | Explicit path to a JSON credential file (see [File storage](#file-storage)) |
| `use_keyring` | `bool` | `True` | Whether to try the OS keyring for credential storage |
| `cache_timeout` | `int` | `60` | TTL in seconds for the client's in-memory response cache (`account`, `networks`, `network`, `eeros`, `devices`, `profiles`) |

> **Note**: There is no `config_path`, `timeout`, or `session_token` constructor argument. There are no `connect()` / `close()` methods — the async context manager (`async with EeroClient() as client:`) is the only lifecycle API.

---

## 🔐 Credential Storage

Storage backend selection is handled by `create_storage()` in `eero.api.auth_storage`, driven entirely by `use_keyring` and `cookie_file`:

| `use_keyring` | `cookie_file` | Backend selected |
|---|---|---|
| `True` | set | `ChainedStorage` — tries `KeyringStorage` first; falls back to `FileStorage(cookie_file)` on **load** failure only |
| `True` | `None` (default) | `KeyringStorage` only |
| `False` | set | `FileStorage(cookie_file)` only |
| `False` | `None` | `MemoryStorage` |

> ⚠️ **Warning:** `EeroClient(use_keyring=False)` with no `cookie_file` silently resolves to `MemoryStorage`. Credentials live only in the process's memory and vanish the moment the process exits — there is no error, warning, or log line to tell you this happened. If you want persistence without the OS keyring, you **must** pass `cookie_file` explicitly.

> ⚠️ **Warning:** The `save()` side of `ChainedStorage`'s file fallback is dead code. `KeyringStorage.save()` swallows its own exceptions and returns normally, so `ChainedStorage.save()`'s except-and-fall-back-to-file branch never fires in practice — the file is never written by `save()`. For headless/container/CI persistence, use `use_keyring=False, cookie_file=...` (plain `FileStorage`), not `use_keyring=True` with a `cookie_file` set. See [Credential Storage](Credential-Storage) for the full mechanics.

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

If the keyring backend raises (headless Linux with no Secret Service daemon, locked keyring, etc.), `KeyringStorage.save()` / `.load()` catch the exception internally and log at `DEBUG` — the failure is non-fatal, but because `save()` never re-raises, `ChainedStorage`'s file fallback is never triggered on save (see warning above). Don't rely on `ChainedStorage` for headless persistence — use `use_keyring=False, cookie_file=...` instead.

### File storage

`FileStorage` writes a single JSON file to the path you provide:

```python
client = EeroClient(cookie_file="/data/eero-cookies.json")
```

- **No default path exists.** `cookie_file` is never inferred from `~/.config`, `$XDG_CONFIG_HOME`, or anything else — you must pass it explicitly for file-based persistence to happen at all.
- The parent directory is created with `os.makedirs(..., exist_ok=True)` if missing.
- After every write, permissions are set to **owner read/write only** (`0600`, via `os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)`).
- `FileStorage.file_path` (property) returns the resolved absolute path (`~` expanded).

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

---

## 🚫 What the SDK Does NOT Do

> **No environment variables**: the SDK never calls `os.environ` for configuration or secrets. Any env var handling shown above is your own application code, not SDK behavior.

> **No settings file**: nothing under `~/.config/` or anywhere else is written except the credential file you explicitly opt into via `cookie_file`. User-preference persistence (default network, output format, etc.) moved to the [eeroctl](https://github.com/fulviofreitas/eeroctl) CLI in v4.0.0.

> **`preferred_network_id` is in-memory only**: `client.set_preferred_network(network_id)` / `client.preferred_network_id` just set/read an attribute on the `EeroClient` instance. It is not persisted, and it disappears when the object is garbage-collected.

---

## ⏱️ Timeouts

Every HTTP request made by `BaseAPI._request` uses a hardcoded `aiohttp.ClientTimeout`:

```python
aiohttp.ClientTimeout(total=30, sock_read=10)
```

| Bound | Value | Meaning |
|---|---|---|
| `total` | 30s | Overall wall-clock budget for the request |
| `sock_read` | 10s | Max time to wait for any single chunk of the response body (guards against a slow-trickle/"slowloris" upstream even if `total` hasn't elapsed) |

> ⚠️ **Warning:** These values are **not configurable** — there is no `timeout` constructor argument on `EeroClient`, `EeroAPI`, or `BaseAPI`. A request that exceeds either bound raises `EeroTimeoutException`.

---

## 🛡️ Security Considerations

- **Keyring-backed storage** keeps the session token out of any file on disk, encrypted at rest by the OS.
- **File storage** is `0600` (owner-only), but is still plaintext JSON — treat the containing volume/host as sensitive.
- **`MemoryStorage`** never touches disk, but also never survives process restart — see the warning above about the silent fallback.
- All API responses are capped at `MAX_RESPONSE_BYTES` (10 MiB) to prevent unbounded memory growth from a hostile or misbehaving upstream, and error-message bodies are truncated to `MAX_ERROR_BODY_CHARS` (512 chars) before being logged or raised.
- Redirects are never followed (`allow_redirects=False`) — any 3xx response is rejected outright so the session cookie can never leak to an unintended host.
- For log redaction behavior (how tokens/cookies are masked in log output), see [Logging and Security](Logging-and-Security).

---

## 🔗 Related Pages

- [Home](Home) — Overview and quick start
- [Python API](Python-API) — Full API reference & examples
- [Authentication](Authentication) — Login/verify flow and session lifecycle
- [Credential Storage](Credential-Storage) — Deep dive on storage backends
- [Logging and Security](Logging-and-Security) — Sensitive-field redaction and secure logging
- [Troubleshooting](Troubleshooting) — Common issues & fixes
