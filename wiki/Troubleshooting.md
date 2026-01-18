# 🔧 Troubleshooting

Common issues and their solutions when using the Eero API Python client.

---

## macOS: "operation not permitted" when activating venv

If you see this error when trying to activate the virtual environment:

```
(eval):source:1: operation not permitted: venv/bin/activate
```

This is caused by macOS quarantine attributes on downloaded files. Fix it by running:

```bash
xattr -cr venv
```

> 💡 **Tip:** If using `uv`, you won't encounter this issue as `uv` manages its own environment.

---

## Authentication Issues

### Session Expired

If you see authentication errors, your session may have expired. Re-authenticate:

```python
async with EeroClient() as client:
    # Force new login
    await client._api.auth.clear_auth_data()
    await client.login("your-email@example.com")
    code = input("Enter verification code: ")
    await client.verify(code)
```

### Check Authentication Status

```python
async with EeroClient() as client:
    if client.is_authenticated:
        print("Authenticated")
    else:
        print("Not authenticated - need to login")
```

---

## Network Connection Issues

### No Networks Found

If get_networks() returns an empty list:

1. Verify you're authenticated
2. Check your Eero account has networks associated
3. Try re-authenticating

```python
async with EeroClient() as client:
    networks = await client.get_networks()
    if not networks:
        print("No networks found - check your Eero account")
```

### API Timeouts

For slow or unreliable connections:

```python
# Increase timeout
client = EeroClient(timeout=60)  # 60 seconds
```

---

## Import Errors

### Module Not Found

If you see ModuleNotFoundError: No module named eero:

```bash
# Install the package
pip install eero-api

# Or install from source
pip install -e .
```

---

## Debug Mode

For detailed logging when troubleshooting issues:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

async with EeroClient() as client:
    # Operations will now show detailed logs
    networks = await client.get_networks()
```

---

## 🔗 Related Pages

- [Python API](Python-API) — API documentation
- [Configuration](Configuration) — Setup options
