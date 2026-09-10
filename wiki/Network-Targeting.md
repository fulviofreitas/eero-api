# 🎯 Network Targeting

`network_id` is a trailing optional kwarg almost everywhere — here's how it actually resolves.

---

## Why `network_id` Is a Trailing Optional Kwarg

Most Eero accounts only manage a single network, so requiring `network_id` on every call would be needless boilerplate. Nearly every `EeroClient` method accepts `network_id: Optional[str] = None` as its **last** parameter, letting you omit it entirely for single-network accounts:

```python
await client.get_eeros()                         # resolved automatically
await client.get_eeros(network_id="1234567")      # explicit override
```

---

## Resolution Order

When `network_id` is omitted (or `None`), `EeroClient._ensure_network_id` resolves it in this exact order:

1. **Explicit argument** — if `network_id` was passed and is truthy, use it.
2. **Preferred network** — fall back to `self._preferred_network_id` (set via `set_preferred_network()`, or auto-populated as a side effect of `get_networks()` — see below).
3. **Auto-discovery** — if neither is set and auto-discovery is allowed for that call, fetch `get_networks()`, pull the first entry from `data["networks"]` (or `data["data"]`, or a bare list `data`), and extract its ID (`id` field, or the trailing segment of `url`).
4. **Failure** — if none of the above yields an ID, raises `EeroException("No network ID provided and no preferred network set")`.

```python
network_id = network_id or self._preferred_network_id
if network_id:
    return network_id
# ...auto-discover via get_networks()...
raise EeroException("No network ID provided and no preferred network set")
```

> **Note**: Not every method allows auto-discovery. Mutating calls like `set_network_name`, `set_led`, `set_wpa3`, `set_upnp`, `set_ipv6` call `_ensure_network_id(network_id, auto_discover=False)` — they require an explicit `network_id` or a previously-set preferred network; they will not silently discover one.

---

## `set_preferred_network()` / `preferred_network_id`

```python
client.set_preferred_network("1234567")
current = client.preferred_network_id  # "1234567"
```

This is **in-memory only** — it is not persisted to disk, keyring, or any config file, and does not survive process restart or a new `EeroClient` instance.

---

## Auto-Discovery Side Effect of `get_networks()`

Calling `client.get_networks()` has a side effect: if no preferred network is currently set, it extracts the first network from the response and sets it as the preferred network for the rest of the session.

```python
await client.get_networks()               # preferred_network_id was None
client.preferred_network_id               # now populated with the first network's ID
```

This means the very first call you make against a multi-network account — even a read-only one — can silently pin every subsequent call (that omits `network_id`) to that first network.

---

## ⚠️ Warning: `network_id` Is Never the First Positional Argument

The single most common mistake is passing a network ID as the **first** positional argument. On `EeroClient`, the resource/value comes first and `network_id` is always last:

```python
# ❌ WRONG — "123456" is bound to `enabled`, which is truthy;
#            network_id stays None and resolves via preferred/auto-discovery
await client.set_upnp("123456")

# ✅ CORRECT
await client.set_upnp(enabled=True, network_id="123456")
```

Because `enabled` only checks truthiness, `set_upnp("123456")` doesn't raise — it silently enables UPnP on whichever network `_ensure_network_id` resolves to, which is almost never the one you meant to target.

### Methods where this is most likely

| Method | Signature | Footgun |
|---|---|---|
| `set_upnp` | `set_upnp(enabled, network_id=None)` | ID lands in `enabled` (truthy) |
| `set_wpa3` | `set_wpa3(enabled, network_id=None)` | ID lands in `enabled` (truthy) |
| `set_ipv6` | `set_ipv6(enabled, network_id=None)` | ID lands in `enabled` (truthy) |
| `set_dns_mode` | `set_dns_mode(mode, custom_servers=None, network_id=None)` | ID lands in `mode`, sent as an invalid DNS mode string |
| `set_guest_network` | `set_guest_network(enabled, name=None, password=None, network_id=None)` | ID lands in `enabled` (truthy) |
| `set_network_name` | `set_network_name(name, network_id=None)` | ID overwrites the network's *name*, not its target |
| `reboot_eero` | `reboot_eero(eero_id, network_id=None)` | ID lands in `eero_id` — reboots (or 404s on) the wrong device |
| `set_led` | `set_led(eero_id, enabled, network_id=None)` | ID lands in `eero_id` |
| `get_device` | `get_device(device_id, network_id=None, refresh_cache=False)` | ID lands in `device_id` |
| `set_device_nickname` | `set_device_nickname(device_id, nickname, network_id=None)` | ID lands in `device_id` |

For `set_upnp` / `set_wpa3` / `set_ipv6` / `set_guest_network` / `set_dns_mode`, the ID silently becomes the *value* being set. For `reboot_eero` / `set_led` / `get_device` / `set_device_nickname`, the ID silently becomes the *resource ID*, targeting (or failing to find) the wrong eero or device. Always pass `network_id=` as a keyword.

---

## The v5.0.0 Change: `EeroAPI` No Longer Has Preferred-Network Resolution

`EeroAPI.set_preferred_network()` and `EeroAPI.preferred_network_id` were deprecated in v4.7.0 and **removed in v5.0.0**. They never actually wired through to any domain API call — setting them on `EeroAPI` had no effect even before removal.

Preferred-network resolution (the whole mechanism described above) lives **only on `EeroClient`**. When working with `EeroAPI` or an individual domain API (e.g. `SecurityAPI`, `NetworksAPI`) directly, you must pass `network_id=` explicitly on every call — there is no fallback:

```python
async with EeroAPI() as api:
    # network_id is required here — EeroAPI has no preferred-network concept
    await api.security.set_upnp("1234567", enabled=True)
```

If you want the resolve-once-then-forget ergonomics, use `EeroClient` instead of `EeroAPI`.

---

## Multi-Network Accounts

If your account manages more than one network, don't rely on auto-discovery or the preferred-network default — it will silently pick whichever network came back first from `get_networks()`. Fetch the network list once, extract each ID explicitly (see [Raw Response Format](Raw-Response-Format#resource-urls-and-ids) for `id_from_url`), and pass `network_id=` on every call:

```python
from eero import EeroClient, id_from_url

async with EeroClient() as client:
    response = await client.get_networks()
    networks = response.get("data", {}).get("networks", {}).get("data", [])
    network_ids = [id_from_url(n["url"]) for n in networks]

    for network_id in network_ids:
        eeros = await client.get_eeros(network_id=network_id)
        print(network_id, eeros.get("data"))
```

Never call `set_preferred_network()` in code paths that fan out across multiple networks in the same session — it's global, in-memory, mutable state shared by every subsequent call that omits `network_id`.

---

## 🔗 Related Pages

- [Python API](Python-API) — full API reference & examples
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
- [Deprecations](Deprecations) — no-op and removed surface, and what replaces it
