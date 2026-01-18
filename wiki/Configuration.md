# ⚙️ Configuration

Authentication storage and configuration options for the Python API.

---

## Authentication Storage

### Keyring (Default)

By default, credentials are stored securely in your system keyring:

- **macOS:** Keychain
- **Linux:** Secret Service (GNOME Keyring, KWallet)
- **Windows:** Windows Credential Locker

### File-based Storage

For systems without keyring support or headless environments, credentials are stored in `~/.config/eero/cookies.json`.

---

## Python API Configuration

```python
from eero import EeroClient

# Default configuration (uses keyring)
client = EeroClient()

# Custom configuration
client = EeroClient(
    config_path="/custom/path",  # Custom config directory
    use_keyring=False,           # Disable keyring, use file storage
    cookie_file="/path/to/cookies.json",  # Custom cookie file path
)
```

---

## Config Files

| File | Location | Purpose |
|------|----------|---------|
| Credentials | `~/.config/eero/cookies.json` | Session token storage |
| Settings | `~/.config/eero/config.json` | User preferences |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `EERO_CONFIG_DIR` | Custom config directory path |
| `EERO_SESSION_TOKEN` | Pre-set session token (for CI/CD) |

---

## Security Considerations

### Keyring Advantages

- Credentials encrypted at rest
- Protected by system authentication
- No plaintext files on disk

### File Storage Considerations

- Permissions set to `600` (owner read/write only)
- Located in user config directory
- Suitable for containers/headless systems

### CI/CD Usage

For automated pipelines, set the session token directly:

```python
import os
from eero import EeroClient

# Use environment variable for session token
client = EeroClient(session_token=os.environ.get("EERO_SESSION_TOKEN"))
```

---

## 🔗 Related Pages

- [Python API](Python-API) — Programmatic access
- [Troubleshooting](Troubleshooting) — Common issues
