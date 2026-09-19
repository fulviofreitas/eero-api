# 🎯 Network Targeting

`network_id` is a trailing optional kwarg almost everywhere — here's how it actually resolves.

---

## Why `network_id` Is a Trailing Optional Kwarg

Most Eero accounts only manage a single network, so requiring `network_id` on every call would be needless boilerplate. Nearly every `EeroClient` method accepts `network_id: Optional[str] = None` as its **last** parameter, letting you omit it entirely for single-network accounts:

```python
await client.get_eeros()                         # resolved automatically
await client.get_eeros(network_id="<network-id>")   # explicit override
```

---

## Resolution Order

When `network_id` is omitted (or `None`), `EeroClient._ensure_network_id` resolves it in this exact order:

1. **Explicit argument** — if `network_id` was passed and is truthy, use it.
2. **Preferred network** — fall back to `self._preferred_network_id` (set via `set_preferred_network()`, or auto-populated as a side effect of `get_networks()` — see below).
3. **Auto-discovery** — only for the 24 methods listed below, and only if neither of the above is set: fetch `get_networks()`, pull the first entry from `data["networks"]` (or `data["data"]`, or a bare list `data`), and extract its ID (`id` field, or the trailing segment of `url`).
4. **Failure** — if none of the above yields an ID, raises `EeroException("No network ID provided and no preferred network set")`.

```python
network_id = network_id or self._preferred_network_id
if network_id:
    return network_id
# ...auto-discover via get_networks() — only for the 24 methods below...
raise EeroException("No network ID provided and no preferred network set")
```

> ⚠️ **Warning: Auto-discovery is the exception, not the rule.** `_ensure_network_id` is called
> 169 times across `EeroClient`; 145 of those calls pass `auto_discover=False`. Only the **24**
> methods below will fetch `get_networks()` to find a network on your behalf. Every other method
> — including many read-only getters and every method in the families added in v8.0.0 —
> requires an explicit `network_id=` or an already-set preferred network, and raises
> `EeroException("No network ID provided and no preferred network set")` otherwise.

### Methods that auto-discover (24 total)

| | |
|---|---|
| `block_device` | `create_profile` |
| `delete_profile` | `get_device` |
| `get_device_labels` | `get_devices` |
| `get_eero` | `get_eeros` |
| `get_network` | `get_profile` |
| `get_profile_devices` | `get_profiles` |
| `pause_device` | `pause_profile` |
| `reboot_eero` | `rename_profile` |
| `run_speed_test` | `set_device_labels` |
| `set_device_nickname` | `set_device_type` |
| `set_guest_network` | `set_profile_devices` |
| `unblock_device` | `update_device_via_link` |

Everything else — including common reads like `get_diagnostics`, `get_insights`,
`get_routing`, `get_blacklist`, `get_reservations`, `get_forwards`, `get_transfer_stats`,
`get_data_usage`, `get_updates`, `get_premium_status`, `get_security_settings`,
`get_dns_settings`, `get_sqm_settings`, `get_led_status`, `get_nightlight`,
`get_backup_internet`, `get_schedules`, `get_guest_network`, `get_speed_tests`,
`get_device_priority`, `get_ac_compat`, `get_ouicheck`, `get_support`, `get_thread`,
`run_diagnostics`, every read in the entitlements / events / permissions / notifications /
DNS-policies / members / WPA3 / power-saving / backup-access-point / subnet / WAN families, and
every setter other than the device and guest-network writes listed above — requires an explicit
`network_id=` or a preferred network already set.

> 💡 **Tip:** The practical fix is cheap: call `get_networks()` once, early, in your session. As a
> side effect it populates `_preferred_network_id` (see below), and every one of the other 145
> methods will then resolve without you passing `network_id=` on every call.

### `network_id` is the *only* positional on some new wrappers

A handful of the v8.0.0 wrappers take `network_id` as their first (and only) positional
parameter, with everything else keyword-only — the opposite arrangement from the rest of the
facade. This is deliberate: the operation has no natural leading resource argument, so
`network_id` moves to the front rather than trailing a long keyword list:

```python
await client.get_channel_utilization("<network-id>", start=..., end=...)
await client.get_app_events(network_id="<network-id>", page_size=50)
await client.set_dhcp(network_id="<network-id>", mode="automatic")
await client.set_wpa3_per_band(network_id="<network-id>", band_5_ghz="WPA3")
await client.set_power_saving(network_id="<network-id>", enable=True)
await client.create_power_saving_schedule(network_id="<network-id>", name=..., days=..., start_time=..., end_time=...)
await client.add_backup_access_point(network_id="<network-id>", ssid=..., password=...)
await client.get_notification_history(network_id="<network-id>", timestamp=None)
```

Passing `network_id=` as a keyword everywhere sidesteps the difference entirely.

---

## `set_preferred_network()` / `preferred_network_id`

```python
client.set_preferred_network("<network-id>")
current = client.preferred_network_id  # "<network-id>"
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
| `set_dns_caching` | `set_dns_caching(enabled, network_id=None)` | ID lands in `enabled` (truthy) |
| `set_dns_mode` | `set_dns_mode(mode, custom_servers=None, network_id=None)` | ID lands in `mode` — **caught**: raises `EeroValidationException` |
| `set_custom_dns` | `set_custom_dns(dns_servers, network_id=None)` | ID lands in `dns_servers` — **caught**: raises `EeroValidationException` |
| `clear_custom_dns` | `clear_custom_dns(family=None, network_id=None)` | ID lands in `family` — **caught**: raises `EeroValidationException` |
| `set_guest_network` | `set_guest_network(enabled, name=None, network_id=None)` | ID lands in `enabled` (truthy) |
| `set_sqm` | `set_sqm(enabled, network_id=None)` | ID lands in `enabled` (truthy) — and this is a settings-class write that may reboot the mesh |
| `set_network_name` | `set_network_name(name, network_id=None)` | ID overwrites the network's *name*, not its target |
| `set_network_password` | `set_network_password(password, network_id=None)` | ID becomes the Wi-Fi *password* |
| `reboot_eero` | `reboot_eero(eero_id, network_id=None)` | ID lands in `eero_id` — reboots (or 404s on) the wrong device |
| `set_led` | `set_led(eero_id, enabled, network_id=None)` | ID lands in `eero_id` |
| `get_device` | `get_device(device_id, network_id=None, refresh_cache=False)` | ID lands in `device_id` |
| `set_device_nickname` | `set_device_nickname(device_id, nickname, network_id=None)` | ID lands in `device_id` |

For `set_upnp` / `set_wpa3` / `set_ipv6` / `set_guest_network` / `set_dns_caching` / `set_sqm`, the ID silently becomes the *value* being set. For `reboot_eero` / `set_led` / `get_device` / `set_device_nickname`, the ID silently becomes the *resource ID*, targeting (or failing to find) the wrong eero or device. Always pass `network_id=` as a keyword.

Because every resource argument now also accepts an API path or absolute URL (next section), a
misplaced bare network ID in `eero_id` / `device_id` is still built into a URL and sent — the
polymorphism does not catch the mistake.

Only three methods catch this: `set_dns_mode`, `set_custom_dns` and `clear_custom_dns` validate their first argument, so a misplaced network ID raises `EeroValidationException` before any request is made. **Do not generalise that to "DNS methods are safe"** — `set_dns_caching` takes a plain `bool` and validates nothing, so it fails silently exactly like the other boolean setters. The protection is a side effect of those three happening to validate, not a property of the DNS surface.

---

## The v5.0.0 Change: `EeroAPI` No Longer Has Preferred-Network Resolution

`EeroAPI.set_preferred_network()` and `EeroAPI.preferred_network_id` were deprecated in v4.7.0 and **removed in v5.0.0**. They never actually wired through to any domain API call — setting them on `EeroAPI` had no effect even before removal.

Preferred-network resolution (the whole mechanism described above) lives **only on `EeroClient`**. When working with `EeroAPI` or an individual domain API (e.g. `SecurityAPI`, `NetworksAPI`) directly, you must pass `network_id=` explicitly on every call — there is no fallback:

```python
async with EeroAPI() as api:
    # network_id is required here — EeroAPI has no preferred-network concept
    await api.security.set_upnp("<network-id>", enabled=True)
```

If you want the resolve-once-then-forget ergonomics, use `EeroClient` instead of `EeroAPI`.

---

## Resource Links: IDs, Paths, and URLs Are Interchangeable

The API embeds resource identity in `url` fields (`/2.2/networks/<network-id>`) and, on the
network, eero, profile, and guest-network envelopes, a `resources` object whose values are
host-relative paths to related resources (`eeros`, `devices`, `profiles`, `settings`,
`guestnetwork`, `reboot`, `speedtest`, `led_action`, `schedules`, …). Since v8.0.0 the SDK
uses those links rather than hardcoding every path.

### Every resource argument accepts three forms

Wherever a domain method (or an `EeroClient` wrapper) documents a `network_id`, `eero_id`,
`device_id` / `mac`, `profile`, `forward`, `reservation`, `invite_id`, or `schedule` argument,
you may pass any of:

| Form | Example | What the SDK does |
|---|---|---|
| Bare ID | `"<network-id>"` | Substitutes it into the method's URL template on that family's API version |
| API path | `"/2.2/networks/<network-id>"` | Joins it onto the API host, preserving whatever version prefix the path carries |
| Absolute URL | `"https://api-user.e2ro.com/2.2/networks/<network-id>"` | Uses it as-is after validation |

An absolute URL is accepted only when its scheme and hostname exactly match the API host.
Anything else — another host, `http://`, a userinfo trick like
`https://api-user.e2ro.com@evil.example/…`, or a suffix trick like
`https://api-user.e2ro.com.evil.example/…` — raises `EeroValidationException` before any
request is made. The session token therefore can never be sent anywhere but the API host, even
if a link value is attacker-controlled.

When a template continues past the resource (for example `networks/{id}/settings`), a bare ID is
substituted into the whole template, while a path or URL is taken to identify the *parent*
resource and the suffix is appended to it.

```python
from eero import EeroAPI

async with EeroAPI() as api:
    net = await api.networks.get_network("<network-id>")
    data = net["data"]

    # All three address the same network, so all three list the same eeros:
    eeros = await api.eeros.get_eeros("<network-id>")                 # bare-ID form
    eeros = await api.eeros.get_eeros(data["url"])                    # path form: "/2.2/networks/<network-id>"
    eeros = await api.eeros.get_eeros(
        "https://api-user.e2ro.com/2.2/networks/<network-id>"         # absolute form
    )
```

The path/URL form names the **resource the argument stands for** (here, the network), not the
sub-resource the method reaches — pass `data["url"]`, not `data["resources"]["eeros"]`. To
reach a sub-resource through its published link, hand the whole envelope over as `parent=`
(next section) and let the method pick the link itself.

### `parent=` — use the link the API published

Every domain method also takes a keyword-only `parent=` argument: the *envelope of the resource
you already hold* (a full `{"meta": …, "data": …}` response or just its `data` object). When
supplied, the method resolves its URL from that envelope's published link — the network's
`resources.settings`, the eero's `resources.led_action`, the profile's `resources.schedules`,
the resource's own `url` — instead of building one from a template. This matters because the
API is free to publish a link on a different version than the template default (`routing`, for
instance, is served on `2.3` while the template fallback is `2.2`), and because it makes the
request follow whatever the API says the resource's address is.

The envelope passed as `parent=` is only ever read. It is never mutated, copied-with-changes,
or merged into the response you get back — the raw-response contract is untouched.

```python
net = await api.networks.get_network("<network-id>")

# Uses net["data"]["resources"]["settings"] rather than the template
await api.sqm.set_sqm("<network-id>", True, parent=net)

# The guest-network password write wants the *guest network's* envelope
guest = await api.networks.get_guest_network("<network-id>", parent=net)
await api.networks.set_guest_password("<network-id>", "<new-password>", parent=guest)
```

Which envelope a method expects for `parent=` is stated in its docstring and in the
[API Reference](API-Reference) tables: network-scoped methods want the network envelope; eero
methods want the eero's own envelope; `get_device` / `update_device_via_link` want the device's
envelope; profile methods want the profile's; `update_forward` / `update_reservation` /
`update_schedule` / `delete_schedule` accept the resource's envelope *as the resource argument
itself*. A few methods accept `parent=` purely for signature consistency and ignore it
(`BackupAPI`, the Thread writes) — their docstrings say so.

**`EeroClient` does this for you.** When a fresh cached envelope exists — the network from
`get_network()`, the eero from a cached `get_eeros()` list, the device from a cached
`get_device()` — the facade passes it as `parent=` automatically. Call `get_network()` once at
the start of a session and every subsequent network-scoped call resolves through the API's own
links for as long as the cache entry is fresh (default 60 s).

### The link helpers

The resolution primitives are exported from the package root for callers who build URLs
themselves. None of them perform I/O or mutate an envelope.

| Helper | What it returns |
|---|---|
| `resolve_link(parent, name)` | Absolute URL for `parent["resources"][name]` (or `parent["data"]["resources"][name]`), or `None` when absent |
| `self_url(parent)` | Absolute URL for the envelope's own `url`, or `None` |
| `resource_url(id_or_url, template, *, version=API_VERSION_DEFAULT)` | Absolute URL from a bare ID (via `template`, which must contain exactly one `{id}`), a path, or an absolute URL — the id/path/URL polymorphism in one function |
| `sub_resource_url(id_or_url, template, *, link, parent=None, version=…)` | `resolve_link(parent, link)` when it yields a URL, otherwise `resource_url(...)` — the single call every domain method makes |
| `join_api_path(path)` | `API_HOST` + a host-relative path, version prefix preserved |
| `id_from_url(id_or_url)` | Trailing path segment of a URL, or the bare ID unchanged |

```python
from eero import resolve_link, self_url, resource_url, sub_resource_url, join_api_path

net = await api.networks.get_network("<network-id>")
resolve_link(net, "eeros")        # "https://api-user.e2ro.com/2.2/networks/<network-id>/eeros"
self_url(net)                     # "https://api-user.e2ro.com/2.2/networks/<network-id>"
resource_url("<network-id>", "networks/{id}/settings")
sub_resource_url("<network-id>", "networks/{id}/settings", link="settings", parent=net)
join_api_path("/2.3/networks/<network-id>/routing")
```

### API versions are per family

`eero.const` names the version each family is served on, and `api_endpoint(version)` is the
one place that joins a version onto the host:

| Constant | Value | Used for |
|---|---|---|
| `API_VERSION_DEFAULT` | `"2.2"` | Networks, eeros, profiles, guest network, and every family not listed below |
| `API_VERSION_DEVICE_WRITES` | `"2.3"` | `set_device_nickname` / `pause_device` — the same write on `2.2` returns 200 and changes nothing |
| `API_VERSION_MULTISTATICIP` | `"2.3"` | `WanAPI.get_multistaticip` / `set_multistaticip` |
| `API_VERSION_SECONDARY_WAN` | `"2.3"` | `WanAPI.set_secondary_wan_config` / `set_device_secondary_wan_access` |
| `api_endpoint("2.3")` | `"https://api-user.e2ro.com/2.3"` | Base URL for a given version |

`API_VERSION`, `API_ENDPOINT`, and `DEVICE_UPDATE_ENDPOINT` remain as derived aliases of the
above. A link read from an envelope keeps its own version prefix regardless of these constants,
which is one more reason to prefer `parent=` over bare IDs when you hold the envelope.

---

## Multi-Network Accounts

If your account manages more than one network, don't rely on auto-discovery or the preferred-network default — it will silently pick whichever network came back first from `get_networks()`. Fetch the network list once, extract each ID explicitly (see [Raw Response Format](Raw-Response-Format#resource-urls-and-ids) for `id_from_url`), and pass `network_id=` on every call:

```python
from eero import EeroClient, id_from_url

async with EeroClient() as client:
    response = await client.get_networks()
    data = response.get("data") or {}
    networks = data if isinstance(data, list) else (data.get("networks") or data.get("data") or [])
    network_ids = [id_from_url(n["url"]) for n in networks]

    for network_id in network_ids:
        eeros = await client.get_eeros(network_id=network_id)
        print(network_id, eeros.get("data"))
```

> **Note**: For a reusable shape-tolerant helper, see [Raw Response Format](Raw-Response-Format#the-networks-shape-specifically).

Never call `set_preferred_network()` in code paths that fan out across multiple networks in the same session — it's global, in-memory, mutable state shared by every subsequent call that omits `network_id`.

---

## 🔗 Related Pages

- [Python API](Python-API) — full API reference & examples
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope and the `resources` links
- [API Reference](API-Reference) — which envelope each method expects as `parent=`
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
- [Deprecations](Deprecations) — no-op and removed surface, and what replaces it
