# 🌐 Eero API Wiki

Welcome! Everything you need to master the Eero API Python client.

## 📚 Guides

| Page | What you'll learn |
|------|-------------------|
| **[📖 Python API](Python-API)** | Full API reference & examples |
| **[⚙️ Configuration](Configuration)** | Auth storage & settings |
| **[🔧 Troubleshooting](Troubleshooting)** | Common issues & fixes |

---

## 🚀 Quick Start

### Install

```bash
pip install eero-api
# or
uv add eero-api
```

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
        
        for network in await client.get_networks():
            print(f"📶 {network.name}: {network.status}")

asyncio.run(main())
```

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
- Pydantic models for type safety
- Secure keyring integration
- Comprehensive Python API

---

## ⚠️ Important Notes

> **Unofficial Project**: This library uses reverse-engineered APIs and is not affiliated with or endorsed by Eero.

> **Amazon Login Limitation**: If your Eero account uses Amazon for login, this library may not work directly due to API limitations. See [Troubleshooting](Troubleshooting#amazon-login-accounts) for the workaround.

---

## 💡 Tips

- Use the sidebar to navigate between pages
- Code blocks have a copy button
- Each page has a table of contents
