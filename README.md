<div align="center">

# 🐍 Eero API

**Your async Python toolkit for Eero mesh networks**

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776ab?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/eero-api?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/eero-api/)
[![License](https://img.shields.io/badge/license-MIT-22c55e?style=for-the-badge)](LICENSE)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/fulviofreitas/eero-api)

---

_A modern, async-first Python SDK for the Eero mesh WiFi API._  
_Raw JSON responses, system keyring integration, and smart caching._

[Get Started](#-quick-start) · [Documentation](#-docs) · [Ecosystem](#-ecosystem) · [License](#-license)

</div>

---

## ⚡ Why Eero API?

- 🚀 **Async-first** — Non-blocking, blazing fast
- 🔐 **Secure** — System keyring for credentials
- 📦 **Raw JSON** — Direct API responses, no transformations
- ⚡ **Smart caching** — Snappy responses

## 📦 Install

```bash
pip install eero-api
# or with uv
uv add eero-api
```

## 🚀 Quick Start

```python
import asyncio
from eero import EeroClient

async def main():
    async with EeroClient() as client:
        if not client.is_authenticated:
            await client.login("you@example.com")
            await client.verify(input("Code: "))
        
        # All methods return raw JSON responses
        response = await client.get_networks()
        networks = response.get("data", {}).get("networks", [])
        
        for network in networks:
            print(f"📶 {network['name']}: {network.get('status')}")

asyncio.run(main())
```

> 💡 Credentials are auto-saved to your system keyring

## 📄 Raw Response Format

All API methods return the exact JSON from Eero's API:

```python
{
    "meta": {"code": 200, "server_time": "..."},
    "data": {
        # Endpoint-specific payload
    }
}
```

See [MIGRATION.md](MIGRATION.md) for details on the raw response architecture.

## 📚 Docs

| Guide | What's inside |
|-------|---------------|
| **[📖 Python API](../../wiki/Python-API)** | Full API reference |
| **[⚙️ Configuration](../../wiki/Configuration)** | Auth & settings |
| **[🔧 Troubleshooting](../../wiki/Troubleshooting)** | Common fixes |
| **[🔄 Migration Guide](MIGRATION.md)** | v1.x → v2.0 migration |
| **[🏠 Wiki Home](../../wiki)** | All documentation |

## 🔗 Ecosystem

| Project | Description |
|---------|-------------|
| **[🖥️ eero-cli](https://github.com/fulviofreitas/eero-cli)** | Terminal interface for Eero networks |
| **[🛜 eero-ui](https://github.com/fulviofreitas/eero-ui)** | Svelte dashboard for network management |
| **[📊 eero-prometheus-exporter](https://github.com/fulviofreitas/eero-prometheus-exporter)** | Prometheus metrics for monitoring |

## ⚠️ Important Notes

> **Unofficial Project**: This library uses reverse-engineered APIs and is not affiliated with or endorsed by Eero.

> **Amazon Login Limitation**: If your Eero account uses Amazon for login, this library may not work directly due to API limitations. **Workaround**: Have someone in your household create a standard Eero account (with email/password) and invite them as an admin to your network. Then use those credentials to authenticate.

## 📄 License

[MIT](LICENSE) — Use it, fork it, build cool stuff 🎉

---

<div align="center">

## 📊 Repository Metrics

![Repository Metrics](./metrics.repository.svg)

</div>
