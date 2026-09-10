# 📄 Raw Response Format

Every method returns the exact JSON body from the Eero Cloud API — no models, no transformation.

---

## What Changed in v2.0.0

Pre-v2.0, this SDK parsed every response into Pydantic models (`Network`, `Device`, `Eero`, `Profile`, `Account`, `Activity`, `Diagnostics`), renamed fields (`wan_ip` → `public_ip`), and normalized status values. As of **v2.0.0** that entire `models/` directory is deleted.

The SDK is now a thin, faithful transport layer over `api-user.e2ro.com`:

- No data extraction from the envelope
- No field renaming — raw field names like `wan_ip` are preserved
- No status normalization
- No fallback objects synthesized on error

Turning API responses into typed objects is the downstream consumer's job (see [eeroctl](https://github.com/fulviofreitas/eeroctl), [eero-ui](https://github.com/fulviofreitas/eero-ui), [eero-prometheus-exporter](https://github.com/fulviofreitas/eero-prometheus-exporter)), not this library's.

> **Note**: `pydantic` is still a declared dependency in `pyproject.toml`, but it is **not part of the public surface** — the SDK doesn't import it anywhere in `src/eero/`. Don't expect `eero.models` to exist; it doesn't.

---

## The Envelope Shape

Every `EeroAPI` / `EeroClient` method returns:

```python
{"meta": {...}, "data": {...}}
```

`meta.code` mirrors the HTTP status of a successful call (typically `200`). `data` holds the endpoint-specific payload — its shape (list vs. object) depends on the endpoint.

### `get_networks()` (abridged)

```python
{
    "meta": {"code": 200, "server_time": "2026-01-22T10:00:00.000Z"},
    "data": {
        "networks": {
            "count": 1,
            "data": [
                {
                    "url": "/2.2/networks/1234567",
                    "name": "Home",
                    "status": "connected",
                    "wan_ip": "203.0.113.10",
                }
            ]
        }
    }
}
```

### `get_devices()` (abridged)

```python
{
    "meta": {"code": 200, "server_time": "2026-01-22T10:00:00.000Z"},
    "data": [
        {
            "url": "/2.2/networks/1234567/devices/abcdef",
            "nickname": "Living Room TV",
            "mac": "aa:bb:cc:dd:ee:ff",
            "connected": True,
            "ip": "192.168.4.23",
        }
    ]
}
```

`data` is a **list** for `get_devices()` but an **object with a nested `networks` container** for `get_networks()` — always inspect the actual response for the endpoint you're calling rather than assuming a shape.

---

## Safe Access Patterns

```python
response = await client.get_networks()
data = response.get("data", {})
networks = data.get("networks", {}).get("data", [])

for network in networks:
    print(network.get("name"), network.get("status"))
```

```python
response = await client.get_devices()
devices = response.get("data", [])   # already a list here

for device in devices:
    print(device.get("nickname"), device.get("mac"))
```

> ⚠️ **Warning:** `for x in await client.get_networks()` is a bug. It iterates the **top-level envelope's keys** — you'll get the strings `"meta"` and `"data"`, not network objects. Always index into `response["data"]` (or `.get("data", {})`) first.

Use `.get(...)` with defaults throughout — a field's absence is not an error condition the SDK will catch for you; the API is undocumented and fields can appear or disappear between calls.

---

## Before/After: Pre-v2.0 vs. v2.0+

| Pre-v2.0 (Pydantic) | v2.0+ (raw dict) |
|---|---|
| `network.name` | `network["name"]` |
| `network.status` (normalized enum) | `network.get("status")` (raw string, e.g. `"connected"`) |
| `network.public_ip` | `network.get("wan_ip")` |
| `device.nickname` | `device.get("nickname")` |
| `device.connected` (bool) | `device.get("connected")` (raw JSON bool) |
| `for network in await client.get_networks()` | `for network in (await client.get_networks())["data"]["networks"]["data"]` |

---

## Resource URLs and IDs

Eero embeds resource identity in `url` fields rather than bare `id` fields, e.g. `/2.2/networks/12345` or `/2.2/networks/12345/devices/abcdef`. Use the exported `id_from_url` helper to pull the trailing segment:

```python
from eero import id_from_url

network = networks[0]
network_id = id_from_url(network["url"])  # "12345"
```

`id_from_url` accepts either a bare ID (returned unchanged) or a URL/URL fragment (returns the trailing path segment). It raises `EeroValidationException` for empty or non-string input.

---

## Typing Guidance

Every method signature returns `Dict[str, Any]` — there is no generic parameterization and no schema enforced by the SDK. If you want typed access at your application boundary, define your own `TypedDict`s (or Pydantic models) around the raw response:

```python
from typing import Any, TypedDict


class NetworkSummary(TypedDict):
    url: str
    name: str
    status: str


def to_network_summary(raw: dict[str, Any]) -> NetworkSummary:
    return {
        "url": raw["url"],
        "name": raw.get("name", ""),
        "status": raw.get("status", "unknown"),
    }
```

This keeps the SDK dependency-light and future-proof against upstream field changes, while still letting you get static-typing benefits in your own code.

---

## 🔗 Related Pages

- [Python API](Python-API) — full API reference & examples
- [Network Targeting](Network-Targeting) — passing `network_id` correctly
- [Migration](Migration) — upgrading from pre-v2.0 (Pydantic) releases
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
