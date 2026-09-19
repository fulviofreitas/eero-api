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

Error responses follow the same envelope shape, with `meta.error` carrying the API's error string. The SDK raises them as exceptions instead of returning them, but the envelope is attached unmodified as `err.envelope` (and `meta.error` as `err.error_code`) — see [Error Handling](Error-Handling#common-attributes-envelope-error_code-message).

### `get_networks()` (abridged)

```python
{
    "meta": {"code": 200, "server_time": "2026-01-22T10:00:00.000Z"},
    "data": {
        "networks": {
            "count": 1,
            "data": [
                {
                    "url": "/2.2/networks/<network-id>",
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
            "url": "/2.2/networks/<network-id>/devices/<mac>",
            "nickname": "Living Room TV",
            "mac": "<mac>",
            "connected": True,
            "ip": "192.168.4.23",
        }
    ]
}
```

`data` is a **list** for `get_devices()` but an **object** for `get_networks()` — and the shape of the networks container itself varies. Never assume a shape; see [The networks shape, specifically](#the-networks-shape-specifically).

---

## Safe Access Patterns

```python
response = await client.get_networks()

for network in as_list(response, "networks"):   # helper defined below
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

## The networks shape, specifically

`get_networks()` is the one response worth calling out, because its `data` has been seen in
three different shapes:

| Shape | Where it comes from |
|---|---|
| `data["networks"]` is a **list** | What the SDK's own auto-discovery assumes, and what the `/account` fallback in `EeroClient.get_networks()` constructs |
| `data["networks"]` is an **object** wrapping `{"count": N, "data": [...]}` | Seen in the wild on the live Cloud API, but **not** supported by the SDK's auto-discovery |
| `data` is a **bare list** | Seen on some accounts |

> ⚠️ **Warning:** The SDK's internal auto-discovery does `networks = data.get("networks") or
> data.get("data") or []` and then indexes `networks[0]`. It assumes `data["networks"]` is a
> **list**. If your account returns the nested `{"count": N, "data": [...]}` container, that
> indexing raises `KeyError: 0` — auto-discovery does not probe for this shape. If you hit this,
> pass `network_id=` explicitly instead of relying on auto-discovery; see
> [Network Targeting](Network-Targeting).

In your own code, use the `as_list()` helper below — it handles all three shapes correctly for
reading responses, even though the SDK's internal auto-discovery does not:

```python
from typing import Any


def as_list(response: dict[str, Any], key: str | None = None) -> list[dict[str, Any]]:
    """Pull a list of resources out of an Eero response envelope."""
    data = response.get("data") or {}

    if isinstance(data, list):
        return data

    items = data.get(key) if key else None
    if items is None:
        items = data.get("data") or []

    # Some containers nest one level deeper: {"count": N, "data": [...]}
    if isinstance(items, dict):
        items = items.get("data") or []

    return items if isinstance(items, list) else []
```

```python
networks = as_list(await client.get_networks(), "networks")
devices = as_list(await client.get_devices())
eeros = as_list(await client.get_eeros(), "eeros")
```

> 💡 **Tip:** Wrap this once in your own codebase rather than repeating the `.get()` chain at
> every call site. When the upstream shape shifts, you fix one function.

---

## Before/After: Pre-v2.0 vs. v2.0+

| Pre-v2.0 (Pydantic) | v2.0+ (raw dict) |
|---|---|
| `network.name` | `network["name"]` |
| `network.status` (normalized enum) | `network.get("status")` (raw string, e.g. `"connected"`) |
| `network.public_ip` | `network.get("wan_ip")` |
| `device.nickname` | `device.get("nickname")` |
| `device.connected` (bool) | `device.get("connected")` (raw JSON bool) |
| `for network in await client.get_networks()` | `for network in as_list(await client.get_networks(), "networks")` |

---

## Resource URLs and IDs

Eero embeds resource identity in `url` fields rather than bare `id` fields, e.g. `/2.2/networks/12345` or `/2.2/networks/12345/devices/abcdef`. Use the exported `id_from_url` helper to pull the trailing segment:

```python
from eero import id_from_url

network = networks[0]
network_id = id_from_url(network["url"])  # "12345"
```

`id_from_url` accepts either a bare ID (returned unchanged) or a URL/URL fragment (returns the trailing path segment). It raises `EeroValidationException` for empty or non-string input.

### The `resources` links

Several envelopes — the network, each eero, each profile, and the guest network — also carry a
`resources` object: a map of link names to host-relative paths for related resources. On a
network it looks like this (abridged; the exact set of keys is whatever the API returns for
your network):

```python
{
    "meta": {"code": 200, "server_time": "..."},
    "data": {
        "url": "/2.2/networks/<network-id>",
        "name": "Home",
        "resources": {
            "eeros": "/2.2/networks/<network-id>/eeros",
            "devices": "/2.2/networks/<network-id>/devices",
            "profiles": "/2.2/networks/<network-id>/profiles",
            "settings": "/2.2/networks/<network-id>/settings",
            "guestnetwork": "/2.2/networks/<network-id>/guestnetwork",
            "reboot": "/2.2/networks/<network-id>/reboot",
            "speedtest": "/2.2/networks/<network-id>/speedtest",
            "routing": "/2.3/networks/<network-id>/routing",
            ...
        },
        ...
    }
}
```

Since v8.0.0 the SDK reads these links: every domain method resolves its URL through
`sub_resource_url(...)`, which prefers the link published on the envelope you pass as `parent=`
and falls back to a template only when no envelope (or no such link) is available. Note that a
link may carry a different version prefix from the SDK's default (`routing` above is on `2.3`)
— the SDK preserves whatever prefix the link carries.

You do not need to unwrap anything before passing an envelope back in: the helpers accept the
full `{"meta": ..., "data": ...}` response or the bare `data` object and detect which they were
given. Nothing in this path mutates, copies-with-changes, or re-shapes the envelope; the
response you get back from any method is still the API's body, unmodified.

Three forms are interchangeable wherever a method takes a resource identifier — a bare ID, the
`url` value, or that value joined onto the API host — and links to any other host or scheme are
refused with `EeroValidationException`. The exported helpers (`resolve_link`, `self_url`,
`resource_url`, `sub_resource_url`, `join_api_path`) and the per-family version constants are
described in [Network Targeting](Network-Targeting#resource-links-ids-paths-and-urls-are-interchangeable).

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
- [Network Targeting](Network-Targeting) — passing `network_id` correctly, and using the `resources` links
- [Migration](Migration) — upgrading from pre-v2.0 (Pydantic) releases
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
