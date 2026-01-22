# 🌐 Eero API

> Your async Python toolkit for Eero mesh networks ✨

[![PyPI version](https://img.shields.io/pypi/v/eero-api.svg)](https://pypi.org/project/eero-api/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![CI](https://github.com/fulviofreitas/eero-api/actions/workflows/ci.yml/badge.svg)](https://github.com/fulviofreitas/eero-api/actions/workflows/ci.yml)

## ⚡ Why Eero API?

- 🚀 **Async-first** — Non-blocking, blazing fast
- 🔐 **Secure** — System keyring for credentials
- 📦 **Type-safe** — Full Pydantic models
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
        
        for network in await client.get_networks():
            print(f"📶 {network.name}: {network.status}")

asyncio.run(main())
```

> 💡 Credentials are auto-saved to your system keyring

## 📚 Docs

| Guide | What's inside |
|-------|---------------|
| **[📖 Python API](../../wiki/Python-API)** | Full API reference |
| **[⚙️ Configuration](../../wiki/Configuration)** | Auth & settings |
| **[🔧 Troubleshooting](../../wiki/Troubleshooting)** | Common fixes |
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
