# 🐍 Python API

The `EeroClient` facade — installation, lifecycle, and every topic area of the SDK.

---

## Installation

```bash
pip install eero-api
# or
uv add eero-api
```

## Quickstart

```python
import asyncio
from eero import EeroClient

async def main():
    async with EeroClient() as client:
        if not client.is_authenticated:
            await client.login("you@example.com")
            await client.verify(input("Verification code: "))

        response = await client.get_networks()
        data = response.get("data") or {}
        networks = data if isinstance(data, list) else (data.get("networks") or data.get("data") or [])
        for network in networks:
            print(f"📶 {network.get('name')}: {network.get('status')}")

asyncio.run(main())
```

> **Note**: `is_authenticated` is a property, not a method — no `()`.

> **Note**: For a reusable shape-tolerant helper, see [Raw Response Format](Raw-Response-Format#the-networks-shape-specifically) — `get_networks()` can return the network list under more than one shape.

---

## Client Lifecycle

`EeroClient` is only usable as an async context manager. There is no `connect()` / `close()` pair.

```python
async with EeroClient() as client:
    ...  # session is opened on __aenter__ and torn down on __aexit__
```

### Constructor

| Argument | Type | Default | Purpose |
|----------|------|---------|---------|
| `session` | `Optional[aiohttp.ClientSession]` | `None` | Bring your own `aiohttp` session instead of letting the client create one |
| `cookie_file` | `Optional[str]` | `None` | Path used by the file-based credential storage fallback |
| `use_keyring` | `bool` | `True` | Store the session token in the OS keyring; falls back to the JSON cookie file when unavailable |
| `cache_timeout` | `int` | `60` | TTL in seconds for the client's in-memory response cache |

```python
import aiohttp
from eero import EeroClient

async with aiohttp.ClientSession() as session:
    async with EeroClient(session=session, use_keyring=False, cache_timeout=120) as client:
        ...
```

> ⚠️ **Warning:** There is no `session_token`, `config_path`, or `timeout` constructor argument, and no environment variables are read. If you already have a session token, use `await client.set_session_token(token)` after entering the context manager.

---

## Raw Response Envelope

Every method — on `EeroClient` and on the lower-level `EeroAPI` — returns the raw, unmodified JSON body from the Eero Cloud API:

```python
{"meta": {...}, "data": {...}}
```

There are no Pydantic models and `eero.models` does not exist. Always index into `resp["data"]`, never attribute-access. See [Raw Response Format](Raw-Response-Format) for the full shape and gotchas (list-vs-dict `data`, missing keys, etc.).

---

## Network Targeting

`network_id` is an **optional trailing keyword argument** on nearly every `EeroClient` method. When omitted, only 19 methods auto-discover your first network — every other method requires a preferred network already set (via `set_preferred_network()`, or as a side effect of calling `get_networks()` once) and raises `EeroException` otherwise. See [Network Targeting](Network-Targeting) for the full list and resolution order.

```python
await client.get_eeros()                       # auto-discovered network
await client.get_eeros(network_id="123456")     # explicit network
```

> **Note**: Since v5.0.0, `set_preferred_network()` / `preferred_network_id` live on `EeroClient` only. The identically-named symbols were removed from `EeroAPI` — they never wired through to any domain API.

---

## Account & Networks

```python
account = await client.get_account()
networks = await client.get_networks()
network = await client.get_network(network_id=None, refresh_cache=False)
await client.set_network_name(name="Home", network_id=None)
premium = await client.get_premium_status(network_id=None)
```

---

## Eeros (Mesh Nodes)

```python
eeros = await client.get_eeros(network_id=None, refresh_cache=False)
eero = await client.get_eero(eero_id, network_id=None, refresh_cache=False)
await client.reboot_eero(eero_id, network_id=None)
```

---

## Devices

```python
devices = await client.get_devices(network_id=None, refresh_cache=False)
device = await client.get_device(device_id, network_id=None, refresh_cache=False)
await client.set_device_nickname(device_id, "Living Room TV", network_id=None)
await client.block_device(device_id, blocked=True, network_id=None)
await client.pause_device(device_id, paused=True, network_id=None)
```

---

## Profiles

```python
profiles = await client.get_profiles(network_id=None, refresh_cache=False)
profile = await client.get_profile(profile_id, network_id=None, refresh_cache=False)
await client.pause_profile(profile_id, paused=True, network_id=None)
await client.create_profile("Kids", network_id=None)
await client.rename_profile(profile_id, "Teens", network_id=None)
await client.delete_profile(profile_id, network_id=None)

devices = await client.get_profile_devices(profile_id, network_id=None)
await client.set_profile_devices(profile_id, device_urls=["/2.2/networks/123/devices/abc"], network_id=None)

await client.get_blocked_applications(profile_id, network_id=None)
await client.set_blocked_applications(profile_id, applications=["TikTok"], network_id=None)
```

---

## Guest Network

```python
await client.set_guest_network(
    enabled=True,
    name="Guest WiFi",
    password="welcome123",
    network_id=None,
)
```

---

## Speed Test & Diagnostics

```python
results = await client.run_speed_test(network_id=None)
diagnostics = await client.get_diagnostics(network_id=None)
await client.run_diagnostics(network_id=None)
```

---

## DHCP Reservations (write support added v6.1.0)

`get_reservations` predates v6.1.0; `create_reservation`, `update_reservation`, and
`delete_reservation` were added in v6.1.0.

```python
reservations = await client.get_reservations(network_id=None)
await client.create_reservation(reservation_data={"mac": "aa:bb:cc:dd:ee:ff", "ip": "192.168.4.50"}, network_id=None)
await client.update_reservation(reservation_id, reservation_data={"ip": "192.168.4.51"}, network_id=None)
await client.delete_reservation(reservation_id, network_id=None)
```

---

## Port Forwards (write support added v6.2.0)

`get_forwards` predates v6.2.0; `create_forward` and `delete_forward` were added in v6.2.0.

```python
forwards = await client.get_forwards(network_id=None)
await client.create_forward(forward_data={"internal_ip": "192.168.4.10", "internal_port": 8080, "external_port": 8080, "protocol": "tcp"}, network_id=None)
await client.delete_forward(forward_id, network_id=None)
```

---

## DNS

> **⚠️ Every DNS write reboots the whole mesh** — all eeros restart and clients lose
> connectivity. Read first and skip the write when nothing has changed; see
> [Troubleshooting](Troubleshooting#my-whole-network-went-down-after-changing-dns).

```python
dns = await client.get_dns_settings(network_id=None)
await client.set_dns_caching(enabled=True, network_id=None)

# All four slots at once — the list is split by address family.
await client.set_custom_dns(
    dns_servers=[
        "1.1.1.1", "1.0.0.1",                          # IPv4 primary / secondary
        "2606:4700:4700::1111", "2606:4700:4700::1001",  # IPv6 primary / secondary
    ],
    network_id=None,
)

# Or one family at a time; the other is left untouched.
await client.set_custom_dns_ipv4(["8.8.8.8", "8.8.4.4"], network_id=None)
await client.set_custom_dns_ipv6(["2001:4860:4860::8888"], network_id=None)

await client.set_dns_mode("custom", custom_servers=["1.1.1.1"], network_id=None)

# Back to the ISP's resolvers. Non-destructive: the API keeps your servers.
await client.clear_custom_dns(family="ipv6", network_id=None)  # one family
await client.clear_custom_dns(network_id=None)                 # both

# Re-enable the stored servers without resupplying them.
await client.set_dns_mode("custom", network_id=None)
```

Reading the result:

```python
data = (await client.get_dns_settings())["data"]

data["dns"]["mode"]                     # "custom" | "automatic"
data["dns"]["custom"]["ips"]            # IPv4 servers
data["dns"]["parent"]["ips"]            # the ISP's resolvers
data["dns"]["caching"]                  # bool
data["ipv6"]["name_servers"]["mode"]    # "custom" | "automatic"
data["ipv6"]["name_servers"]["custom"]  # IPv6 servers, fully expanded
```

At most 2 servers per family; more raises `EeroValidationException`, as does a malformed
address or one of the wrong family.

### Provider presets

The SDK deliberately has no built-in provider list. The API serves its own catalogue, which
is authoritative and stays current — build a picker from it rather than hardcoding addresses:

```python
data = (await client.get_dns_settings())["data"]

for provider in data["dns"]["default_test_servers"]:
    print(provider["name"], provider["ipv4"], provider["ipv6"])
    # Cloudflare ['1.1.1.1', '1.0.0.1'] ['2606:4700:4700::1111', ...]
    # Google     ['8.8.8.8', '8.8.4.4'] ['2001:4860:4860::8888', ...]
    # OpenDNS    [...]                  [...]
    # Quad9      [...]                  [...]

chosen = data["dns"]["default_test_servers"][0]
await client.set_custom_dns(chosen["ipv4"] + chosen["ipv6"])
```

> **⚠️** `set_ipv6_dns()` is **not** for IPv6 DNS servers — it toggles `ipv6_upstream`,
> the IPv6 connectivity setting. Use `set_custom_dns_ipv6()` instead.

---

## SQM / QoS

```python
sqm = await client.get_sqm_settings(network_id=None)
await client.set_sqm_enabled(enabled=True, network_id=None)
await client.configure_sqm(enabled=True, upload_mbps=20, download_mbps=200, network_id=None)
```

---

## Security

```python
security = await client.get_security_settings(network_id=None)
await client.set_wpa3(enabled=True, network_id=None)
await client.set_band_steering(enabled=True, network_id=None)
await client.set_upnp(enabled=False, network_id=None)
await client.set_ipv6(enabled=True, network_id=None)
await client.set_thread_enabled(enabled=True, network_id=None)
await client.configure_security(wpa3=True, band_steering=True, upnp=False, ipv6=True, thread=True, network_id=None)
```

> **Note**: The `EeroClient` method is `set_thread_enabled` (the underlying `SecurityAPI` method is `set_thread`).

---

## Backup Network

```python
backup = await client.get_backup_network(network_id=None)
status = await client.get_backup_status(network_id=None)
await client.set_backup_network(enabled=True, network_id=None)
await client.configure_backup_network(enabled=True, phone_number="+15551234567", network_id=None)
```

---

## LEDs & Nightlight

```python
led = await client.get_led_status(eero_id, network_id=None)
await client.set_led(eero_id, enabled=False, network_id=None)
await client.set_led_brightness(eero_id, brightness=50, network_id=None)

nightlight = await client.get_nightlight(eero_id, network_id=None)
await client.set_nightlight(
    eero_id,
    enabled=True,
    brightness=30,
    schedule_enabled=True,
    schedule_on="22:00",
    schedule_off="06:00",
    network_id=None,
)
```

---

## Schedules & Bedtime

```python
schedule = await client.get_profile_schedule(profile_id, network_id=None)
await client.set_profile_schedule(profile_id, time_blocks=[{"day": "mon", "start": "22:00", "end": "07:00"}], network_id=None)
await client.clear_profile_schedule(profile_id, network_id=None)
await client.enable_bedtime(profile_id, start_time="21:00", end_time="07:00", days=["mon", "tue"], network_id=None)
```

---

## Stats & Usage

```python
transfer = await client.get_transfer_stats(network_id=None, device_id=None)
usage = await client.get_data_usage(network_id=None, payload={"resource": "network"}, resource=None)
reporters = await client.get_burst_reporters(network_id=None)
```

### `get_insights`

```python
async def get_insights(
    self,
    network_id: Optional[str] = None,
    *,
    start: str,
    end: str,
    insight_type: str,
    cadence: str = "daily",
) -> Dict[str, Any]: ...
```

`start`, `end`, and `insight_type` are required keyword-only arguments; `cadence` defaults to
`"daily"`. Unlike most `EeroClient` methods, `network_id` does **not** auto-discover — pass it
explicitly or set a preferred network first (see [Network Targeting](Network-Targeting)).

```python
insights = await client.get_insights(
    network_id=None,
    start="2026-07-01T00:00:00Z",
    end="2026-07-21T00:00:00Z",
    insight_type="blocked",
    cadence="daily",
)
```

---

## Blacklist

```python
blacklist = await client.get_blacklist(network_id=None)
```

> **Note**: `EeroClient` only exposes `get_blacklist`. Adding/removing MACs is available on the lower-level `EeroAPI.blacklist` domain (`add_to_blacklist`, `remove_from_blacklist`) — see [API Reference](API-Reference).

---

## Deprecated

> ⚠️ **Warning:** `set_device_priority` is a confirmed **no-op**. It emits a `DeprecationWarning`, the underlying request returns 200, but nothing changes on the eero. Use [SQM/QoS](#sqm--qos) (`configure_sqm`) for bandwidth control instead.

```python
await client.set_device_priority(device_id, prioritized=True, duration_minutes=30, network_id=None)  # no-op
```

> ⚠️ **Warning:** Every `ActivityAPI` method (`get_activity`, `get_activity_clients`, `get_activity_for_device`, `get_activity_history`, `get_activity_categories`) — and the matching `EeroClient` passthroughs — is deprecated as of v6.0.0. The upstream Eero endpoints now return 404. Migrate to `get_insights(...)` for category/adblock data.

---

## Error Handling

All exceptions derive from `EeroException` and end in `...Exception` (not `...Error`): `EeroAuthenticationException`, `EeroAPIException`, `EeroRateLimitException`, `EeroNetworkException`, `EeroTimeoutException`, `EeroValidationException`, and `from eero.exceptions import EeroNotFoundException, EeroPremiumRequiredException, EeroFeatureUnavailableException`.

```python
from eero import EeroAuthenticationException, EeroException

try:
    await client.get_network(network_id="invalid-id")
except EeroAuthenticationException:
    print("Session expired — log in again")
except EeroException as e:
    print(f"Request failed: {e}")
```

> **Note**: `EeroNotFoundException`, `EeroPremiumRequiredException`, and `EeroFeatureUnavailableException` are **not** in `eero.__all__` — `from eero import EeroNotFoundException` raises `ImportError`. Import them from `eero.exceptions` instead. They are defined but never raised anywhere in `src/`. See [Error Handling](Error-Handling).

Full hierarchy and per-exception guidance: [Error Handling](Error-Handling).

---

## Caching

`EeroClient` keeps a `cache_timeout`-second in-memory cache (default 60s) for read methods that accept `refresh_cache`. Pass `refresh_cache=True` to bypass it for a single call, or call `client.clear_cache()` to drop everything.

```python
await client.get_networks(refresh_cache=True)
client.clear_cache()
```

Details on which methods are cached and rate-limit behavior: [Caching and Rate Limits](Caching-and-Rate-Limits).

---

## Utilities

`id_from_url` is exported from the top-level `eero` package and extracts the trailing ID segment from an API URL fragment or bare ID:

```python
from eero import id_from_url

id_from_url("/2.2/networks/123456/profiles/p_abc")  # -> "p_abc"
id_from_url("123456")                                # -> "123456"
```

---

## The Lower-Level `EeroAPI`

`EeroClient` is a facade over `EeroAPI`, a composition-based aggregator exposing the same domain APIs directly (`api.devices`, `api.profiles`, `api.security`, etc.) without caching or auto-discovery. Use it when you need domain-level control; pass `network_id` explicitly to every call. Full method inventory: [API Reference](API-Reference).

---

## 🔗 Related Pages

- [Home](Home) — Wiki overview and quick links
- [Configuration](Configuration) — Auth storage & settings
- [Authentication](Authentication) — Login/verify flow and session persistence
- [Raw Response Format](Raw-Response-Format) — Envelope shape and extraction patterns
- [Error Handling](Error-Handling) — Full exception hierarchy and handling patterns
- [Caching and Rate Limits](Caching-and-Rate-Limits) — Cache TTLs and rate-limit behavior
- [Network Targeting](Network-Targeting) — How `network_id` resolution works
- [API Reference](API-Reference) — Full per-domain method inventory
- [Examples](Examples) — End-to-end runnable scripts
- [Troubleshooting](Troubleshooting) — Common issues & fixes
