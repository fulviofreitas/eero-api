# 📚 API Reference

Exhaustive signature reference for every public class and method in the SDK.

---

## Orientation

The SDK is a layered stack:

```
EeroClient   → high-level facade: caching, network_id resolution, one method per operation
    ↓
EeroAPI      → composition root: aggregates 23 domain APIs + AuthAPI (24 API classes total) as attributes (client._api.<domain>)
    ↓
Domain APIs  → one class per Eero Cloud resource (NetworksAPI, DevicesAPI, ProfilesAPI, ...)
    ↓
BaseAPI / AuthenticatedAPI → HTTP transport, error mapping, auth headers
```

Use `EeroClient` for almost everything — it's the only layer with the 60s TTL cache and
`network_id` auto-resolution. Drop to `EeroAPI` (or a domain API directly) when you need
explicit control over which network a call targets, or when a domain method has no
`EeroClient` wrapper (flagged per-domain below).

> ⚠️ **Warning:** Preferred-network resolution (`set_preferred_network()` / `preferred_network_id`)
> exists on `EeroClient` ONLY. The same-named symbols were removed from `EeroAPI` in v5.0.0 —
> they never wired through to any domain API. When using `EeroAPI` or a domain API directly,
> pass `network_id` explicitly on every call.

Every method (both `EeroClient` and the domain APIs) returns a raw `Dict[str, Any]` envelope
shaped `{"meta": {...}, "data": {...}}` unless noted otherwise. See [Raw Response Format](Raw-Response-Format).

---

## EeroClient

`from eero import EeroClient`. Constructor:

```python
def __init__(self, session: Optional[ClientSession]=None, cookie_file: Optional[str]=None, use_keyring: bool=True, cache_timeout: int=60) -> None
```

All `network_id` parameters below are trailing optional kwargs — when omitted, `EeroClient`
resolves the network via `preferred_network_id` (if set); only 19 methods will additionally
auto-discover by fetching the account's networks. Every other method raises `EeroException` if
neither is available. See [Network Targeting](Network-Targeting) for the exact list.

### Session & Account

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Context manager | `async def __aenter__(self) -> 'EeroClient'` | `EeroClient` | Only lifecycle API — no `connect()`/`close()` |
| Context manager | `async def __aexit__(self, exc_type, exc_val, exc_tb) -> None` | `None` | |
| `is_authenticated` | `def is_authenticated(self) -> bool` | `bool` | **Property** — no `()` |
| `login` | `async def login(self, user_identifier: str) -> bool` | `bool` | |
| `verify` | `async def verify(self, verification_code: str) -> bool` | `bool` | |
| `logout` | `async def logout(self) -> bool` | `bool` | |
| `set_session_token` | `async def set_session_token(self, token: str) -> None` | `None` | |
| `clear_session_token` | `async def clear_session_token(self) -> None` | `None` | |
| `get_account` | `async def get_account(self, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | |

### Networks

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_networks` | `async def get_networks(self, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_network` | `async def get_network(self, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_network_name` | `async def set_network_name(self, name: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_preferred_network` | `def set_preferred_network(self, network_id: str) -> None` | `None` | EeroClient-only; not a property |
| `preferred_network_id` | `def preferred_network_id(self) -> Optional[str]` | `Optional[str]` | **Property** — EeroClient-only |
| `get_premium_status` | `async def get_premium_status(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_guest_network` | `async def set_guest_network(self, enabled: bool, name: Optional[str]=None, password: Optional[str]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `run_speed_test` | `async def run_speed_test(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_diagnostics` | `async def get_diagnostics(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `run_diagnostics` | `async def run_diagnostics(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_insights` | `async def get_insights(self, network_id: Optional[str]=None, *, start: str, end: str, insight_type: str, cadence: str='daily') -> Dict[str, Any]` | `Dict[str, Any]` | `start`/`end`/`insight_type` are keyword-only |
| `get_routing` | `async def get_routing(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_thread` | `async def get_thread(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Thread radio settings |
| `get_support` | `async def get_support(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

### Eeros

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_eeros` | `async def get_eeros(self, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_eero` | `async def get_eero(self, eero_id: str, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `reboot_eero` | `async def reboot_eero(self, eero_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

### Devices

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_devices` | `async def get_devices(self, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_device` | `async def get_device(self, device_id: str, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_device_nickname` | `async def set_device_nickname(self, device_id: str, nickname: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Writes go to the `/2.3` endpoint — see [Constants](#constants) |
| `block_device` | `async def block_device(self, device_id: str, blocked: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `pause_device` | `async def pause_device(self, device_id: str, paused: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_device_priority` | `async def get_device_priority(self, device_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | No dedicated domain endpoint — internally calls `get_device()` and returns the full device payload |

> **Note**: `set_device_priority` was removed in v8.0.0 — the API never exposed device-level
> priority. Use [SQM](#sqm--qos) instead.

### Profiles

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_profiles` | `async def get_profiles(self, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_profile` | `async def get_profile(self, profile_id: str, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `pause_profile` | `async def pause_profile(self, profile_id: str, paused: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `create_profile` | `async def create_profile(self, name: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `rename_profile` | `async def rename_profile(self, profile_id: str, name: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete_profile` | `async def delete_profile(self, profile_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_blocked_applications` | `async def get_blocked_applications(self, profile_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_blocked_applications` | `async def set_blocked_applications(self, profile_id: str, applications: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_profile_devices` | `async def get_profile_devices(self, profile_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_profile_devices` | `async def set_profile_devices(self, profile_id: str, device_urls: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `EeroClient` has no wrapper for `ProfilesAPI.update_profile_content_filter()` or
> `ProfilesAPI.update_profile_block_list()` — call them via `client._api.profiles` directly.

### Schedules

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_profile_schedule` | `async def get_profile_schedule(self, profile_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_profile_schedule` | `async def set_profile_schedule(self, profile_id: str, time_blocks: List[Dict], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `clear_profile_schedule` | `async def clear_profile_schedule(self, profile_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `enable_bedtime` | `async def enable_bedtime(self, profile_id: str, start_time: str, end_time: str, days: Optional[List[str]]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `EeroClient` has no wrapper for `ScheduleAPI.set_weekday_bedtime()` or
> `ScheduleAPI.set_weekend_bedtime()` — call them via `client._api.schedule` directly.

### Guest

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `set_guest_network` | see [Networks](#networks) | `Dict[str, Any]` | Listed under Networks to avoid duplication |

### DNS

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_dns_settings` | `async def get_dns_settings(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_dns_caching` | `async def set_dns_caching(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_custom_dns` | `async def set_custom_dns(self, dns_servers: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Mixed IPv4/IPv6 list, split by family |
| `set_custom_dns_ipv4` | `async def set_custom_dns_ipv4(self, dns_servers: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Leaves IPv6 untouched |
| `set_custom_dns_ipv6` | `async def set_custom_dns_ipv6(self, dns_servers: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Leaves IPv4 untouched |
| `clear_custom_dns` | `async def clear_custom_dns(self, family: Optional[str]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Switches to automatic; **retains** stored servers |
| `set_dns_mode` | `async def set_dns_mode(self, mode: str, custom_servers: Optional[List[str]]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `set_ipv6_dns` was removed in v8.0.0 — it wrote `ipv6_upstream`, the IPv6
> connectivity toggle, not DNS servers. Use `set_ipv6()` for the connectivity toggle, or
> `set_custom_dns_ipv6()` for IPv6 DNS servers.

> ### ⚠️ A DNS change reboots the whole mesh
>
> Every eero restarts and all clients lose Wi-Fi and internet while they do. Observed
> 2026-09-12: two DNS writes were followed ~5 minutes later by all four nodes rebooting
> within a 17-second window. The eero app behaves the same way when applying a DNS change.
>
> For anything automated:
>
> - **Write conditionally.** Read `get_dns_settings()` first and skip the write if the
>   configuration already matches. A reconciliation loop that writes unconditionally will
>   reboot the network every run.
> - **Never retry in a tight loop.** A burst of writes appears to queue a burst of reboots.
> - **A 200 is not an all-clear.** The response returns immediately; the reboot lands minutes
>   later.
>
> This applies to every write method below — including `set_dns_caching`.

### The DNS data model

Each address family has its own independent mode selector and server list, mirroring the
four slots in the eero app (IPv4 primary/secondary, IPv6 primary/secondary):

| Path | Meaning |
|------|---------|
| `data.dns.mode` | `"custom"` or `"automatic"` — the IPv4 selector |
| `data.dns.custom.ips` | Configured IPv4 servers, **retained** when mode is `automatic` |
| `data.dns.parent.ips` | The ISP-provided upstream resolvers |
| `data.dns.caching` | DNS caching on/off |
| `data.ipv6.name_servers.mode` | `"custom"` or `"automatic"` — the IPv6 selector |
| `data.ipv6.name_servers.custom` | Configured IPv6 servers |

Three things to know:

- **The shapes are asymmetric.** The IPv4 list nests under `custom.ips`; the IPv6 list sits
  directly under `custom`.
- **IPv6 addresses are stored fully expanded.** A server written as `2606:4700:4700::1111`
  reads back as `2606:4700:4700:0:0:0:0:1111`. Compare with `ipaddress.IPv6Address`, never
  string equality.
- **Clearing is non-destructive and reversible.** `clear_custom_dns()` switches the mode to
  `automatic` and leaves the stored servers in place, exactly like the app's "ISP DNS
  (Default)" option. `set_dns_mode("custom")` with no `custom_servers` switches back and
  re-enables them — no need to resupply the addresses.

At most **2 servers per address family** are accepted; exceeding that raises
`EeroValidationException`. This matches the app's slots and is a deliberate client-side
limit — the API itself accepts more, but behaviour beyond four servers is unverified.

`data.dns.default_test_servers` carries the API's own provider catalogue (Cloudflare, Google,
OpenDNS, Quad9), each with `name`, `ipv4` and `ipv6`. The SDK offers no hardcoded presets —
build a picker from that list so it stays current and complete.

### SQM / QoS

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_sqm_settings` | `async def get_sqm_settings(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_sqm_enabled` | `async def set_sqm_enabled(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `configure_sqm` | `async def configure_sqm(self, enabled: bool, upload_mbps: Optional[int]=None, download_mbps: Optional[int]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `EeroClient` has no wrapper for `SqmAPI.set_sqm_bandwidth()` or `SqmAPI.set_sqm_auto()`
> — call them via `client._api.sqm` directly.

### Security

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_security_settings` | `async def get_security_settings(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_wpa3` | `async def set_wpa3(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_band_steering` | `async def set_band_steering(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_upnp` | `async def set_upnp(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_ipv6` | `async def set_ipv6(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `configure_security` | `async def configure_security(self, wpa3: Optional[bool]=None, band_steering: Optional[bool]=None, upnp: Optional[bool]=None, ipv6: Optional[bool]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `set_thread_enabled` (and the `thread=` keyword on `configure_security`) was removed
> in v8.0.0 — the API does not accept a `thread` field on the settings write. Thread write
> support is planned for a future release.

### Backup

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_backup_network` | `async def get_backup_network(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_backup_status` | `async def get_backup_status(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_backup_network` | `async def set_backup_network(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `configure_backup_network` | `async def configure_backup_network(self, enabled: Optional[bool]=None, phone_number: Optional[str]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

### Reservations

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_reservations` | `async def get_reservations(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Predates v6.1.0 |
| `create_reservation` | `async def create_reservation(self, reservation_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Added v6.1.0 |
| `update_reservation` | `async def update_reservation(self, reservation_id: str, reservation_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Added v6.1.0 |
| `delete_reservation` | `async def delete_reservation(self, reservation_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Added v6.1.0 |

### Forwards

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_forwards` | `async def get_forwards(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Predates v6.2.0 |
| `create_forward` | `async def create_forward(self, forward_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Added v6.2.0 |
| `delete_forward` | `async def delete_forward(self, forward_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Added v6.2.0 |

### LEDs & Nightlight

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_led_status` | `async def get_led_status(self, eero_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_led` | `async def set_led(self, eero_id: str, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_led_brightness` | `async def set_led_brightness(self, eero_id: str, brightness: int, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_nightlight` | `async def get_nightlight(self, eero_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_nightlight` | `async def set_nightlight(self, eero_id: str, enabled: Optional[bool]=None, brightness: Optional[int]=None, schedule_enabled: Optional[bool]=None, schedule_on: Optional[str]=None, schedule_off: Optional[str]=None, ambient_light_enabled: Optional[bool]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `EeroClient` has no wrapper for `EerosAPI.set_nightlight_brightness()` or
> `EerosAPI.set_nightlight_schedule()` — call them via `client._api.eeros` directly.

### Diagnostics & Speed Test

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `run_speed_test` | see [Networks](#networks) | `Dict[str, Any]` | |
| `get_diagnostics` | see [Networks](#networks) | `Dict[str, Any]` | |
| `run_diagnostics` | see [Networks](#networks) | `Dict[str, Any]` | |

### Stats & Usage

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_transfer_stats` | `async def get_transfer_stats(self, network_id: Optional[str]=None, device_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_data_usage` | `async def get_data_usage(self, network_id: Optional[str]=None, payload: Optional[Dict[str, Any]]=None, resource: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_insights` | see [Networks](#networks) | `Dict[str, Any]` | |

> **Note**: `get_burst_reporters` was removed in v8.0.0 — the endpoint returns 404; the resource
> is POST-only. `client._api.burst_reporters.create_burst_reporter(...)` remains available.

### Blacklist

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_blacklist` | see [Networks](#networks) | `Dict[str, Any]` | |

> **Note**: `EeroClient` has no wrapper for `BlacklistAPI.add_to_blacklist()` or
> `BlacklistAPI.remove_from_blacklist()` — call them via `client._api.blacklist` directly.

### Misc

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_ac_compat` | `async def get_ac_compat(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_ouicheck` | `async def get_ouicheck(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_updates` | `async def get_updates(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `get_password` was removed in v8.0.0 — the endpoint returns 404 on every path
> version. Use `get_network()`; the same fields are carried on the network envelope.

### Cache

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `clear_cache` | `def clear_cache(self) -> None` | `None` | Synchronous; drops all cached entries regardless of TTL |

---

## Domain APIs

Reach every domain API through `client._api.<attr>` (on `EeroClient`) or directly on an
`EeroAPI` instance (`api.<attr>`). The attribute name is identical to the module name for
every domain in this SDK — there are no naming divergences.

> **Note**: `client._api` is a private attribute and is not covered by semver — it can change
> without a major-version bump. It is, however, the documented escape hatch for calling domain
> methods that have no `EeroClient` wrapper.

All domain classes except `AuthAPI` extend `AuthenticatedAPI(auth_api: AuthAPI)` and take a
single `auth_api` constructor argument. `AuthAPI` itself extends `BaseAPI` and owns the
session/cookie/keyring plumbing.

### BaseAPI / AuthenticatedAPI (`src/eero/api/base.py`)

Transport layer — not reached via an `EeroAPI` attribute; domain classes inherit from it.

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, session: Optional[ClientSession]=None, cookie_file: Optional[str]=None, base_url: str='') -> None` | `BaseAPI` | |
| `session` | `def session(self) -> ClientSession` | `ClientSession` | Property-style accessor |
| `get` | `async def get(self, url: str, auth_token: Optional[str]=None, **kwargs) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `post` | `async def post(self, url: str, auth_token: Optional[str]=None, **kwargs) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `put` | `async def put(self, url: str, auth_token: Optional[str]=None, **kwargs) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete` | `async def delete(self, url: str, auth_token: Optional[str]=None, **kwargs) -> Dict[str, Any]` | `Dict[str, Any]` | |

`id_from_url(id_or_url: str) -> str` is a module-level function in `base.py`, re-exported from
the package root (`from eero import id_from_url`).

### AuthAPI (`client._api.auth`)

Owns login/session lifecycle and credential storage.

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, session: Optional[ClientSession]=None, cookie_file: Optional[str]=None, use_keyring: bool=True) -> None` | `AuthAPI` | |
| `is_authenticated` | `def is_authenticated(self) -> bool` | `bool` | **Property** |
| `login` | `async def login(self, user_identifier: str) -> bool` | `bool` | |
| `verify` | `async def verify(self, verification_code: str) -> bool` | `bool` | |
| `resend_verification_code` | `async def resend_verification_code(self) -> bool` | `bool` | No `EeroClient` wrapper |
| `logout` | `async def logout(self) -> bool` | `bool` | |
| `refresh_session` | `async def refresh_session(self) -> bool` | `bool` | No `EeroClient` wrapper |
| `ensure_authenticated` | `async def ensure_authenticated(self) -> bool` | `bool` | No `EeroClient` wrapper |
| `get_auth_token` | `async def get_auth_token(self) -> Optional[str]` | `Optional[str]` | No `EeroClient` wrapper |
| `clear_auth_data` | `async def clear_auth_data(self) -> None` | `None` | No `EeroClient` wrapper |
| `set_session_token` | `async def set_session_token(self, token: str) -> None` | `None` | |
| `clear_session_token` | `async def clear_session_token(self) -> None` | `None` | |

### AuthCredentials & CredentialStorage backends (`src/eero/api/auth_storage.py`)

Not reachable via `EeroAPI` attributes — used internally by `AuthAPI`. Documented here for
completeness; see [Credential Storage](Credential-Storage) for usage guidance.

<details>
<summary>📦 Full signatures</summary>

| Class | Method | Signature |
|-------|--------|-----------|
| `AuthCredentials` | — | `is_session_expired(self) -> bool` |
| `AuthCredentials` | — | `has_valid_session(self) -> bool` |
| `AuthCredentials` | — | `to_dict(self) -> dict` |
| `AuthCredentials` | classmethod | `from_dict(cls, data: dict) -> 'AuthCredentials'` |
| `AuthCredentials` | — | `clear_session(self) -> None` |
| `AuthCredentials` | — | `clear_all(self) -> None` |
| `CredentialStorage` (ABC) | — | `async def load(self) -> AuthCredentials` |
| `CredentialStorage` (ABC) | — | `async def save(self, credentials: AuthCredentials) -> None` |
| `CredentialStorage` (ABC) | — | `async def clear(self) -> None` |
| `KeyringStorage` | — | same three methods as `CredentialStorage` |
| `FileStorage` | Constructor | `def __init__(self, file_path: str) -> None` |
| `FileStorage` | — | `def file_path(self) -> str` (property) |
| `FileStorage` | — | same `load`/`save`/`clear` as `CredentialStorage` |
| `MemoryStorage` | Constructor | `def __init__(self) -> None` |
| `MemoryStorage` | — | same `load`/`save`/`clear` |
| `ChainedStorage` | Constructor | `def __init__(self, primary: CredentialStorage, fallback: CredentialStorage) -> None` |
| `ChainedStorage` | — | same `load`/`save`/`clear` |

</details>

<details>
<summary>📦 NetworksAPI (<code>client._api.networks</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `NetworksAPI` | |
| `get_networks` | `async def get_networks(self) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_network` | `async def get_network(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_guest_network` | `async def set_guest_network(self, network_id: str, enabled: bool, name: Optional[str]=None, password: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `run_speed_test` | `async def run_speed_test(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `reboot_network` | `async def reboot_network(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |
| `get_premium_status` | `async def get_premium_status(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_network_name` | `async def set_network_name(self, network_id: str, name: str) -> Dict[str, Any]` | `Dict[str, Any]` | |

</details>

<details>
<summary>📦 EerosAPI (<code>client._api.eeros</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `EerosAPI` | |
| `get_eeros` | `async def get_eeros(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_eero` | `async def get_eero(self, network_id: str, eero_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `reboot_eero` | `async def reboot_eero(self, network_id: str, eero_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_led_status` | `async def get_led_status(self, network_id: str, eero_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_led` | `async def set_led(self, network_id: str, eero_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_led_brightness` | `async def set_led_brightness(self, network_id: str, eero_id: str, brightness: int) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_nightlight` | `async def get_nightlight(self, network_id: str, eero_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_nightlight` | `async def set_nightlight(self, network_id: str, eero_id: str, enabled: Optional[bool]=None, brightness: Optional[int]=None, schedule_enabled: Optional[bool]=None, schedule_on: Optional[str]=None, schedule_off: Optional[str]=None, ambient_light_enabled: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_nightlight_brightness` | `async def set_nightlight_brightness(self, network_id: str, eero_id: str, brightness: int) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |
| `set_nightlight_schedule` | `async def set_nightlight_schedule(self, network_id: str, eero_id: str, enabled: bool, on_time: Optional[str]=None, off_time: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |

</details>

<details>
<summary>📦 DevicesAPI (<code>client._api.devices</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `DevicesAPI` | |
| `get_devices` | `async def get_devices(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_device` | `async def get_device(self, network_id: str, device_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_device_nickname` | `async def set_device_nickname(self, network_id: str, device_id: str, nickname: str) -> Dict[str, Any]` | `Dict[str, Any]` | Writes via `/2.3` endpoint |
| `block_device` | `async def block_device(self, network_id: str, device_id: str, blocked: bool) -> Dict[str, Any]` | `Dict[str, Any]` | Writes via `/2.2` `POST`/`DELETE /networks/{id}/blacklist` (issue #109) — not `/2.3` |
| `pause_device` | `async def pause_device(self, network_id: str, device_id: str, paused: bool) -> Dict[str, Any]` | `Dict[str, Any]` | Writes via `/2.3` endpoint |

> Note: there is no `get_device_priority` on `DevicesAPI` — `EeroClient.get_device_priority()`
> is implemented by calling `get_device()` and returning the full payload. `set_device_priority`
> was removed in v8.0.0 — use SQM instead.

</details>

<details>
<summary>📦 ProfilesAPI (<code>client._api.profiles</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `ProfilesAPI` | |
| `get_profiles` | `async def get_profiles(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_profile` | `async def get_profile(self, network_id: str, profile_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `pause_profile` | `async def pause_profile(self, network_id: str, profile_id: str, paused: bool) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_profile_devices` | `async def get_profile_devices(self, network_id: str, profile_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_profile_devices` | `async def set_profile_devices(self, network_id: str, profile_id: str, device_urls: List[str]) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `update_profile_content_filter` | `async def update_profile_content_filter(self, network_id: str, profile_id: str, filters: Dict[str, bool]) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |
| `update_profile_block_list` | `async def update_profile_block_list(self, network_id: str, profile_id: str, domains: List[str], block: bool=True) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |
| `get_blocked_applications` | `async def get_blocked_applications(self, network_id: str, profile_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_blocked_applications` | `async def set_blocked_applications(self, network_id: str, profile_id: str, applications: List[str]) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `create_profile` | `async def create_profile(self, network_id: str, name: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `rename_profile` | `async def rename_profile(self, network_id: str, profile_id: str, name: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete_profile` | `async def delete_profile(self, network_id: str, profile_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |

</details>

<details>
<summary>📦 ScheduleAPI (<code>client._api.schedule</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `ScheduleAPI` | |
| `get_profile_schedule` | `async def get_profile_schedule(self, network_id: str, profile_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_profile_schedule` | `async def set_profile_schedule(self, network_id: str, profile_id: str, time_blocks: List[Dict[str, Any]]) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `clear_profile_schedule` | `async def clear_profile_schedule(self, network_id: str, profile_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `enable_bedtime` | `async def enable_bedtime(self, network_id: str, profile_id: str, start_time: str, end_time: str, days: Optional[List[str]]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_weekday_bedtime` | `async def set_weekday_bedtime(self, network_id: str, profile_id: str, start_time: str, end_time: str) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |
| `set_weekend_bedtime` | `async def set_weekend_bedtime(self, network_id: str, profile_id: str, start_time: str, end_time: str) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |

</details>

<details>
<summary>📦 DnsAPI (<code>client._api.dns</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `DnsAPI` | |
| `get_dns_settings` | `async def get_dns_settings(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_dns_caching` | `async def set_dns_caching(self, network_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_custom_dns` | `async def set_custom_dns(self, network_id: str, dns_servers: List[str]) -> Dict[str, Any]` | `Dict[str, Any]` | Mixed IPv4/IPv6 list, split by family |
| `set_custom_dns_ipv4` | `async def set_custom_dns_ipv4(self, network_id: str, dns_servers: List[str]) -> Dict[str, Any]` | `Dict[str, Any]` | Leaves IPv6 untouched |
| `set_custom_dns_ipv6` | `async def set_custom_dns_ipv6(self, network_id: str, dns_servers: List[str]) -> Dict[str, Any]` | `Dict[str, Any]` | Leaves IPv4 untouched |
| `clear_custom_dns` | `async def clear_custom_dns(self, network_id: str, family: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `family="ipv4"`/`"ipv6"`, or both |
| `set_dns_mode` | `async def set_dns_mode(self, network_id: str, mode: str, custom_servers: Optional[List[str]]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `set_ipv6_dns` was removed in v8.0.0 — it wrote `ipv6_upstream`, the IPv6
> connectivity toggle, not DNS. Use `SecurityAPI.set_ipv6` for the toggle, or
> `set_custom_dns_ipv6` for IPv6 DNS servers.

</details>

<details>
<summary>📦 SqmAPI (<code>client._api.sqm</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `SqmAPI` | |
| `get_sqm_settings` | `async def get_sqm_settings(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_sqm_enabled` | `async def set_sqm_enabled(self, network_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_sqm_bandwidth` | `async def set_sqm_bandwidth(self, network_id: str, upload_mbps: Optional[int]=None, download_mbps: Optional[int]=None) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |
| `configure_sqm` | `async def configure_sqm(self, network_id: str, enabled: bool, upload_mbps: Optional[int]=None, download_mbps: Optional[int]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_sqm_auto` | `async def set_sqm_auto(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |

</details>

<details>
<summary>📦 SecurityAPI (<code>client._api.security</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `SecurityAPI` | |
| `get_security_settings` | `async def get_security_settings(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_wpa3` | `async def set_wpa3(self, network_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_band_steering` | `async def set_band_steering(self, network_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_upnp` | `async def set_upnp(self, network_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_ipv6` | `async def set_ipv6(self, network_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `configure_security` | `async def configure_security(self, network_id: str, wpa3: Optional[bool]=None, band_steering: Optional[bool]=None, upnp: Optional[bool]=None, ipv6: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `set_thread` was removed in v8.0.0 — the API does not accept a `thread` field on the
> settings write. Thread write support is planned for a future release.

</details>

<details>
<summary>📦 BackupAPI (<code>client._api.backup</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `BackupAPI` | |
| `get_backup_network` | `async def get_backup_network(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_backup_status` | `async def get_backup_status(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_backup_network` | `async def set_backup_network(self, network_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `configure_backup_network` | `async def configure_backup_network(self, network_id: str, enabled: Optional[bool]=None, phone_number: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

</details>

<details>
<summary>📦 ReservationsAPI (<code>client._api.reservations</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `ReservationsAPI` | |
| `get_reservations` | `async def get_reservations(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `create_reservation` | `async def create_reservation(self, network_id: str, reservation_data: Dict[str, Any]) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `update_reservation` | `async def update_reservation(self, network_id: str, reservation_id: str, reservation_data: Dict[str, Any]) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete_reservation` | `async def delete_reservation(self, network_id: str, reservation_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |

</details>

<details>
<summary>📦 ForwardsAPI (<code>client._api.forwards</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `ForwardsAPI` | |
| `get_forwards` | `async def get_forwards(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `create_forward` | `async def create_forward(self, network_id: str, forward_data: Dict[str, Any]) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete_forward` | `async def delete_forward(self, network_id: str, forward_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |

</details>

<details>
<summary>📦 BlacklistAPI (<code>client._api.blacklist</code>)</summary>

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` | `BlacklistAPI` | |
| `get_blacklist` | `async def get_blacklist(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `add_to_blacklist` | `async def add_to_blacklist(self, network_id: str, mac: str) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |
| `remove_from_blacklist` | `async def remove_from_blacklist(self, network_id: str, mac_or_device_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |

</details>

<details>
<summary>📦 DiagnosticsAPI, InsightsAPI, RoutingAPI, ThreadAPI, SupportAPI (single-purpose domains)</summary>

| Class | Attribute | Method | Signature | Notes |
|-------|-----------|--------|-----------|-------|
| `DiagnosticsAPI` | `client._api.diagnostics` | `get_diagnostics` | `async def get_diagnostics(self, network_id: str) -> Dict[str, Any]` | |
| `DiagnosticsAPI` | `client._api.diagnostics` | `run_diagnostics` | `async def run_diagnostics(self, network_id: str) -> Dict[str, Any]` | |
| `InsightsAPI` | `client._api.insights` | `get_insights` | `async def get_insights(self, network_id: str, *, start: str, end: str, insight_type: str, cadence: str='daily') -> Dict[str, Any]` | keyword-only args |
| `RoutingAPI` | `client._api.routing` | `get_routing` | `async def get_routing(self, network_id: str) -> Dict[str, Any]` | |
| `ThreadAPI` | `client._api.thread` | `get_thread` | `async def get_thread(self, network_id: str) -> Dict[str, Any]` | |
| `SupportAPI` | `client._api.support` | `get_support` | `async def get_support(self, network_id: str) -> Dict[str, Any]` | |
| `SupportAPI` | `client._api.support` | `request_support` | `async def request_support(self, network_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]` | No `EeroClient` wrapper |

Each of these constructors is `def __init__(self, auth_api: AuthAPI) -> None`.

> **Note**: `InsightsAPI.run_insights` was removed in v8.0.0 — the API declares no such
> operation. `SettingsAPI` was removed entirely in v8.0.0 — the endpoint returns 404 on every
> path version; use `NetworksAPI.get_network` for the same fields.

</details>

<details>
<summary>📦 TransferAPI, DataUsageAPI, BurstReportersAPI, ACCompatAPI, OUICheckAPI, UpdatesAPI (stats & misc)</summary>

| Class | Attribute | Method | Signature | Notes |
|-------|-----------|--------|-----------|-------|
| `TransferAPI` | `client._api.transfer` | `get_transfer_stats` | `async def get_transfer_stats(self, network_id: str, device_id: Optional[str]=None) -> Dict[str, Any]` | |
| `DataUsageAPI` | `client._api.data_usage` | `get_data_usage` | `async def get_data_usage(self, network_id: str, payload: Dict[str, Any], resource: Optional[str]=None) -> Dict[str, Any]` | `payload` is required here (unlike the `EeroClient` wrapper, where it defaults to `None`) |
| `BurstReportersAPI` | `client._api.burst_reporters` | `create_burst_reporter` | `async def create_burst_reporter(self, network_id: str, reporter_data: Dict[str, Any]) -> Dict[str, Any]` | No `EeroClient` wrapper |
| `ACCompatAPI` | `client._api.ac_compat` | `get_ac_compat` | `async def get_ac_compat(self, network_id: str) -> Dict[str, Any]` | |
| `OUICheckAPI` | `client._api.ouicheck` | `get_ouicheck` | `async def get_ouicheck(self, network_id: str) -> Dict[str, Any]` | |
| `UpdatesAPI` | `client._api.updates` | `get_updates` | `async def get_updates(self, network_id: str) -> Dict[str, Any]` | |

Each of these constructors is `def __init__(self, auth_api: AuthAPI) -> None`.

> **Note**: `BurstReportersAPI.get_burst_reporters` and `OUICheckAPI.run_ouicheck` were removed
> in v8.0.0 (both returned 404 / declared no such operation upstream). `PasswordAPI` was removed
> entirely in v8.0.0 — the endpoint returns 404 on every path version; use
> `NetworksAPI.get_network` for the same fields.

</details>

---

## Exceptions

| Name | Base class | Raised when |
|------|-----------|-------------|
| `EeroException` | `Exception` | Base for all SDK errors; `__init__(self, message: str='An error occurred')`, has `is_auth_error()` |
| `EeroAuthenticationException` | `EeroException` | Login/session failures; `is_auth_error()` always `True` |
| `EeroRateLimitException` | `EeroException` | HTTP 429 from the Eero Cloud API |
| `EeroNetworkException` | `EeroException` | Low-level connection/transport failures |
| `EeroAPIException` | `EeroException` | Generic HTTP error mapping (`status_code`, `message`); `is_auth_error()` checks `status_code == 401` |
| `EeroTimeoutException` | `EeroException` | Request exceeded the client timeout |
| `EeroNotFoundException` | `EeroException` | **Never raised anywhere in `src/`** and not in `eero.__all__` — see [Error Handling](Error-Handling) |
| `EeroPremiumRequiredException` | `EeroException` | **Never raised anywhere in `src/`** and not in `eero.__all__` — see [Error Handling](Error-Handling) |
| `EeroFeatureUnavailableException` | `EeroException` | **Never raised anywhere in `src/`** and not in `eero.__all__` — see [Error Handling](Error-Handling) |
| `EeroValidationException` | `EeroException` | `__init__(self, field: str, message: str)` — client-side input validation failure |

Full hierarchy, matching, and handling patterns: [Error Handling](Error-Handling).

---

## Module-level exports

`from eero import ...` — the package `__all__` verbatim from `src/eero/__init__.py`:

```python
__all__ = [
    "EeroAPI",
    "EeroClient",
    "EeroException",
    "EeroAPIException",
    "EeroAuthenticationException",
    "EeroNetworkException",
    "EeroRateLimitException",
    "EeroTimeoutException",
    "EeroValidationException",
    # URL / ID utilities
    "id_from_url",
    # Secure logging utilities
    "get_secure_logger",
    "SecureLoggerAdapter",
    "redact_sensitive",
]
```

> ⚠️ **Warning:** Only the exceptions in `__all__` above are importable from the package root
> (`from eero import ...`) — everything else in `src/eero/exceptions.py` must be imported from
> `eero.exceptions` directly.

| Root-importable (`from eero import ...`) | `eero.exceptions`-only (`from eero.exceptions import ...`) |
|---|---|
| `EeroException` | `EeroNotFoundException` |
| `EeroAPIException` | `EeroPremiumRequiredException` |
| `EeroAuthenticationException` | `EeroFeatureUnavailableException` |
| `EeroNetworkException` | |
| `EeroRateLimitException` | |
| `EeroTimeoutException` | |
| `EeroValidationException` | |

> ⚠️ **Warning:** `EeroDeviceType`, `EeroNetworkStatus`, and `EeroDeviceStatus` (defined in
> `src/eero/const.py`) are **NOT** re-exported from the package root. `eero/__init__.py` does
> not import from `const.py` at all. Import them explicitly:
> `from eero.const import EeroDeviceType`.

---

## Constants

Public, useful constants from `src/eero/const.py` (import via `from eero.const import ...`):

| Constant | Value | Purpose |
|----------|-------|---------|
| `API_ENDPOINT` | `"https://api-user.e2ro.com/2.2"` | Base URL for reads and most writes |
| `DEVICE_UPDATE_ENDPOINT` | `"https://api-user.e2ro.com/2.3"` | Base URL for device-mutation writes only |
| `LOGIN_ENDPOINT` | `f"{API_ENDPOINT}/login"` | |
| `LOGIN_VERIFY_ENDPOINT` | `f"{API_ENDPOINT}/login/verify"` | |
| `LOGOUT_ENDPOINT` | `f"{API_ENDPOINT}/logout"` | |
| `ACCOUNT_ENDPOINT` | `f"{API_ENDPOINT}/account"` | |
| `LOGIN_REFRESH_ENDPOINT` | `f"{API_ENDPOINT}/login/refresh"` | Tried first for session refresh |
| `ACCOUNT_REFRESH_ENDPOINT` | `f"{API_ENDPOINT}/account/refresh"` | Fallback refresh path |
| `REFRESH_ENDPOINTS` | `(LOGIN_REFRESH_ENDPOINT, ACCOUNT_REFRESH_ENDPOINT)` | Tried in order |
| `DEFAULT_HEADERS` | `{"User-Agent": "eero/3.0 (iPhone; iOS 17.0)", "Content-Type": "application/json"}` | Mobile UA reduces rate-limiting risk |
| `CACHE_TIMEOUT` | `60` | Unused — not imported anywhere in `src/`. `EeroClient` hardcodes `cache_timeout: int = 60` instead |
| `MAX_RESPONSE_BYTES` | `10 * 1024 * 1024` (10 MiB) | Guards against unbounded response bodies |
| `MAX_ERROR_BODY_CHARS` | `512` | Caps how much of a hostile/oversized body is embedded in error messages and logs |
| `SESSION_TOKEN_KEY` | `"session_token"` | Keyring/file storage key |
| `REFRESH_TOKEN_KEY` | `"refresh_token"` | Keyring/file storage key |

> ⚠️ **Warning:** The `/2.2` vs `/2.3` split matters for device mutations, but only for two
> methods: `set_device_nickname` and `pause_device`. These route through
> `DevicesAPI._update_device()` to `DEVICE_UPDATE_ENDPOINT` (`/2.3`) because the mutation is
> silently dropped on `/2.2` — the backend returns 200 OK but the change never persists
> server-side. See issue #102. `block_device` is NOT one of these — it writes via `/2.2`
> `POST`/`DELETE /networks/{id}/blacklist` (issue #109). Reads and every other domain continue
> to use `API_ENDPOINT` (`/2.2`).

`EeroDeviceType`, `EeroNetworkStatus`, and `EeroDeviceStatus` are `str, Enum` classes also
defined in `const.py` — see [Module-level exports](#module-level-exports) for their
(non-)export status.

---

## 🔗 Related Pages

- [Python API](Python-API) — Task-oriented guide to `EeroClient`, grouped by topic with examples
- [Raw Response Format](Raw-Response-Format) — The `{"meta": ..., "data": ...}` envelope shape
- [Network Targeting](Network-Targeting) — How `network_id` resolution works on `EeroClient`
- [Error Handling](Error-Handling) — The `EeroException` hierarchy and handling patterns
- [Deprecations](Deprecations) — No-op and removed surface, and what replaces it
- [Credential Storage](Credential-Storage) — Keyring, file, and memory storage backends
