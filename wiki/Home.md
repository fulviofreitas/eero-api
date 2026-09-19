# 🌐 Eero API Wiki

Welcome! Everything you need to master the Eero API Python client.

---

## 📚 Guides

### Getting Started

| Page | What you'll learn |
|------|-------------------|
| **[📖 Python API](Python-API)** | Full API reference & examples |
| **[⚙️ Configuration](Configuration)** | Client setup & options |
| **[🔑 Authentication](Authentication)** | Login, OTP verification, session lifecycle |
| **[🔐 Credential Storage](Credential-Storage)** | Keyring, file, and memory storage backends |

### Core Concepts

| Page | What you'll learn |
|------|-------------------|
| **[📄 Raw Response Format](Raw-Response-Format)** | The `{"meta": ..., "data": ...}` envelope |
| **[🎯 Network Targeting](Network-Targeting)** | Passing `network_id` correctly |
| **[🚨 Error Handling](Error-Handling)** | The `EeroException` hierarchy |
| **[⚡ Caching and Rate Limits](Caching-and-Rate-Limits)** | TTL cache & the ~100 req/min ceiling |

### Reference

| Page | What you'll learn |
|------|-------------------|
| **[📚 API Reference](API-Reference)** | Every domain API and method signature |
| **[🔀 Migration](Migration)** | Upgrading from pre-v2.0 (Pydantic) releases |
| **[⚠️ Deprecations](Deprecations)** | No-op and removed surface, and what replaces it |
| **[💡 Examples](Examples)** | End-to-end runnable scripts |

### Project

| Page | What you'll learn |
|------|-------------------|
| **[🛡️ Logging and Security](Logging-and-Security)** | `SecureLoggerAdapter`, redaction, safe debug logging |
| **[🔗 Ecosystem](Ecosystem)** | CLI, dashboard, and exporter projects built on this SDK |
| **[🤝 Contributing](Contributing)** | Dev setup, tests, style |
| **[🔧 Troubleshooting](Troubleshooting)** | Common issues & fixes |

---

## 🚀 Quick Start

### Requirements

- Python 3.12+
- An Eero account that signs in with an email address or phone number, verified by a one-time code (see [Troubleshooting](Troubleshooting#amazon-login-accounts) if you use Amazon login)

### Install

```bash
pip install eero-api
# or
uv add eero-api
```

> 📦 Latest release: see the [PyPI project page](https://pypi.org/project/eero-api/) for the current version.

<details>
<summary>📦 Install from source</summary>

```bash
git clone https://github.com/fulviofreitas/eero-api.git
cd eero-api
pip install .

# For development (includes pytest, black, mypy, ruff)
pip install -e ".[dev]"
```

</details>

### Hello World

```python
import asyncio
from eero import EeroClient

async def main():
    async with EeroClient() as client:
        if not client.is_authenticated:
            await client.login("you@example.com")
            await client.verify(input("Code: "))

        # All methods return a raw {"meta": ..., "data": ...} envelope
        response = await client.get_networks()

        data = response.get("data") or {}
        networks = data if isinstance(data, list) else (data.get("networks") or data.get("data") or [])
        for network in networks:
            print(f"📶 {network.get('name')}: {network.get('status')}")

asyncio.run(main())
```

> **Note**: See [Raw Response Format](Raw-Response-Format) for why there's no `network.name` attribute access — `get_networks()` can nest the network list more than one way.
> **Note**: For a reusable shape-tolerant helper, see [Raw Response Format](Raw-Response-Format#the-networks-shape-specifically).

---

## 🔗 Links

| Resource | URL |
|----------|-----|
| 📦 PyPI | [eero-api](https://pypi.org/project/eero-api/) |
| 📦 GitHub | [fulviofreitas/eero-api](https://github.com/fulviofreitas/eero-api) |
| 🐛 Issues | [Report a bug](https://github.com/fulviofreitas/eero-api/issues) |
| 📋 Changelog | [CHANGELOG.md](https://github.com/fulviofreitas/eero-api/blob/master/CHANGELOG.md) |
| 🖥️ CLI | [eeroctl](https://github.com/fulviofreitas/eeroctl) |

---

## 🙏 Acknowledgments

This project is a modern revamp of the original [eero-client](https://github.com/343max/eero-client) by [@343max](https://github.com/343max). Previously known as `eero-client`.

**What's new:**
- Full async/await with `aiohttp`
- Raw JSON passthrough — no Pydantic models, no data transformation
- 23 domain-specific APIs + AuthAPI (24 API classes total) covering the Eero Cloud API surface the API still serves
- Secure credential storage — OS keyring, with an owner-only (`0600`) file fallback

---

## ⚠️ Important Notes

> **Unofficial Project**: This library uses reverse-engineered APIs and is not affiliated with or endorsed by Eero.

> **Amazon Login Limitation**: If your Eero account uses Amazon for login, this library may not work directly due to API limitations. See [Troubleshooting](Troubleshooting#amazon-login-accounts) for the workaround.

---

## 💡 Tips

- Use the sidebar to navigate between pages
- Code blocks have a copy button
