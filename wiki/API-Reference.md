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
BaseAPI / AuthenticatedAPI → HTTP transport, error mapping, credential placement (X-User-Token header)
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
def __init__(self, session: Optional[ClientSession]=None, cookie_file: Optional[str]=None, use_keyring: bool=True, cache_timeout: int=60, *, send_legacy_cookie: bool=True, accept_language: str='en-US', get_retries: int=0) -> None
```

The three keyword-only options (`send_legacy_cookie`, `accept_language`, `get_retries`) are forwarded unchanged to `EeroAPI` → `AuthAPI` → the transport; see [Configuration](Configuration#-constructor-reference).

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
> Every eero restarts and all clients lose Wi-Fi and internet while they do. Verified
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
| `get_data_usage` | `async def get_data_usage(self, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `start`/`end`/`cadence` are keyword-only; `cadence` is `"daily"` or `"hourly"`, required by the API here. All data-usage reads send query parameters only and are never cached |
| `get_data_usage_breakdown` | `async def get_data_usage_breakdown(self, network_id: Optional[str]=None, *, start: str, end: str, cadence: Optional[str]=None, timezone: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Wraps `DataUsageAPI.get_breakdown` |
| `get_devices_data_usage` | `async def get_devices_data_usage(self, network_id: Optional[str]=None, *, start: str, end: str, cadence: Optional[str]=None, timezone: Optional[str]=None, profile_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Wraps `DataUsageAPI.get_devices_usage` |
| `get_device_data_usage` | `async def get_device_data_usage(self, device_mac: str, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Wraps `DataUsageAPI.get_device_usage`; `device_mac` is the leading positional |
| `get_eeros_data_usage_summary` | `async def get_eeros_data_usage_summary(self, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Wraps `DataUsageAPI.get_eeros_summary` |
| `get_eero_data_usage` | `async def get_eero_data_usage(self, eero_id: str, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Wraps `DataUsageAPI.get_eero_usage` |
| `get_profile_data_usage` | `async def get_profile_data_usage(self, profile_id: str, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Wraps `DataUsageAPI.get_profile_usage` |
| `get_unprofiled_devices_data_usage` | `async def get_unprofiled_devices_data_usage(self, network_id: Optional[str]=None, *, start: str, end: str, cadence: Optional[str]=None, timezone: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Wraps `DataUsageAPI.get_unprofiled_devices` |
| `get_unprofiled_data_usage_summary` | `async def get_unprofiled_data_usage_summary(self, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Wraps `DataUsageAPI.get_unprofiled_summary` |
| `get_data_usage_report_settings` | `async def get_data_usage_report_settings(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Wraps `DataUsageAPI.get_report_settings` |
| `set_data_usage_report_settings` | `async def set_data_usage_report_settings(self, *, cadence: str, notification_day: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | **Unverified write** — read first, write only on a difference, never retry. Invalidates that network's cache entry |
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
| `get_ouicheck` | `async def get_ouicheck(self, network_id: Optional[str]=None, *, serial: str, version: str) -> Dict[str, Any]` | `Dict[str, Any]` | `serial` and `version` are keyword-only and required — the API returns `404` without them. Take them from an eero envelope (`get_eeros()`) |
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
| Constructor | `def __init__(self, session: Optional[ClientSession]=None, cookie_file: Optional[str]=None, base_url: str='', *, send_legacy_cookie: bool=True, accept_language: str='en-US', get_retries: int=0) -> None` | `BaseAPI` | `base_url`'s hostname is the only host the session token is ever sent to |
| `session` | `def session(self) -> ClientSession` | `ClientSession` | Property-style accessor |
| `get` | `async def get(self, url: str, auth_token: Optional[str]=None, **kwargs) -> Dict[str, Any]` | `Dict[str, Any]` | Subject to the bounded `get_retries` policy |
| `post` | `async def post(self, url: str, auth_token: Optional[str]=None, **kwargs) -> Dict[str, Any]` | `Dict[str, Any]` | Never retried |
| `put` | `async def put(self, url: str, auth_token: Optional[str]=None, **kwargs) -> Dict[str, Any]` | `Dict[str, Any]` | Never retried |
| `delete` | `async def delete(self, url: str, auth_token: Optional[str]=None, **kwargs) -> Dict[str, Any]` | `Dict[str, Any]` | Never retried |

`**kwargs` are forwarded to the aiohttp request. `json=` selects a JSON body, `data=` a form
body, `encoding=RequestEncoding.EMPTY_JSON_STRING` the two-character `""` body; only one may be
supplied. `params=` is independent of the body. `headers=` may add per-call headers (validated;
`X-User-Token` / `Cookie` / `Authorization` are rejected). `allow_redirects=True` is rejected.

`AuthenticatedAPI.__init__(self, auth_api: AuthAPI, base_url: str='', *, send_legacy_cookie: bool=True, accept_language: str='en-US', get_retries: int=0)` takes the same three options; every domain class passes only `auth_api` and inherits the values `AuthAPI` was built with.

Module-level exports of `eero.api.base`:

| Symbol | Signature / values | Notes |
|--------|--------------------|-------|
| `id_from_url` | `id_from_url(id_or_url: str) -> str` | Re-exported from the package root (`from eero import id_from_url`) |
| `RequestEncoding` | `str, Enum`: `JSON`, `FORM`, `EMPTY_JSON_STRING`, `NONE` | The body encoding active on a single request |
| `build_request_headers` | `build_request_headers(*, accept_language: str, extra_headers: Optional[Dict[str, str]]=None) -> Dict[str, str]` | Returns `Accept`, `User-Agent`, `X-Accept-Language` plus validated extras; never sets `Content-Type` |

### AuthAPI (`client._api.auth`)

Owns login/session lifecycle and credential storage.

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| Constructor | `def __init__(self, session: Optional[ClientSession]=None, cookie_file: Optional[str]=None, use_keyring: bool=True, *, send_legacy_cookie: bool=True, accept_language: str='en-US', get_retries: int=0) -> None` | `AuthAPI` | |
| `is_authenticated` | `def is_authenticated(self) -> bool` | `bool` | **Property** — `True` when a session token is present; no client-side expiry |
| `login` | `async def login(self, user_identifier: str) -> bool` | `bool` | Form-encoded `login=` body |
| `verify` | `async def verify(self, verification_code: str) -> bool` | `bool` | Form-encoded `code=` body |
| `resend_verification_code` | `async def resend_verification_code(self) -> bool` | `bool` | No `EeroClient` wrapper; sends `{}` |
| `logout` | `async def logout(self) -> bool` | `bool` | Form-encoded body, field `Cookie` = `s=<token>` |
| `refresh_session` | `async def refresh_session(self) -> bool` | `bool` | No `EeroClient` wrapper; `POST /2.2/login/refresh` with body `""`, authenticated by the session token; concurrent calls coalesced; `True` on 200, `False` on any API error from the refresh endpoint; network/timeout failures still raise |
| `ensure_authenticated` | `async def ensure_authenticated(self) -> bool` | `bool` | No `EeroClient` wrapper; returns `is_authenticated` |
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
| `AuthCredentials` | field | `session_id: Optional[str] = None` — the only field |
| `AuthCredentials` | — | `to_dict(self) -> Dict[str, Any]` — `{"session_id": ..., "schema_version": 2}` |
| `AuthCredentials` | classmethod | `from_dict(cls, data: Dict[str, Any]) -> 'AuthCredentials'` — for records already carrying `schema_version`; legacy records are migrated by each backend's `load()` |
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
| `BurstReportersAPI` | `client._api.burst_reporters` | `create_burst_reporter` | `async def create_burst_reporter(self, network_id: str, reporter_data: Dict[str, Any]) -> Dict[str, Any]` | No `EeroClient` wrapper |
| `ACCompatAPI` | `client._api.ac_compat` | `get_ac_compat` | `async def get_ac_compat(self, network_id: str) -> Dict[str, Any]` | |
| `OUICheckAPI` | `client._api.ouicheck` | `get_ouicheck` | `async def get_ouicheck(self, network_id: str, *, serial: str, version: str) -> Dict[str, Any]` | Both keyword-only arguments are required; sent as query parameters. The API returns `404` without them. Empty/non-string values raise `EeroValidationException` |
| `UpdatesAPI` | `client._api.updates` | `get_updates` | `async def get_updates(self, network_id: str) -> Dict[str, Any]` | |

Each of these constructors is `def __init__(self, auth_api: AuthAPI) -> None`.

**`DataUsageAPI` (`client._api.data_usage`).** Every read is a `GET` on
`networks/{network_id}/data_usage…` taking query parameters only — `start` and `end` (ISO 8601
timestamps), an optional IANA `timezone`, and `cadence` (`"daily"` or `"hourly"`). Where
`cadence` is typed `str` below it is required by the API; where it is `Optional[str]` it is
omitted from the request when `None`. An invalid `cadence` raises `EeroValidationException`
locally. Every method has an `EeroClient` wrapper (listed under [Stats & Usage](#stats--usage))
with the `*_data_usage*` naming shown there.

| Method | Signature | Notes |
|--------|-----------|-------|
| `get_data_usage` | `async def get_data_usage(self, network_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | Network-level series |
| `get_breakdown` | `async def get_breakdown(self, network_id: str, *, start: str, end: str, cadence: Optional[str]=None, timezone: Optional[str]=None) -> Dict[str, Any]` | |
| `get_devices_usage` | `async def get_devices_usage(self, network_id: str, *, start: str, end: str, cadence: Optional[str]=None, timezone: Optional[str]=None, profile_id: Optional[str]=None) -> Dict[str, Any]` | `profile_id` scopes to one profile's devices |
| `get_device_usage` | `async def get_device_usage(self, network_id: str, device_mac: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | One device, addressed by MAC |
| `get_eeros_summary` | `async def get_eeros_summary(self, network_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | |
| `get_eero_usage` | `async def get_eero_usage(self, network_id: str, eero_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | |
| `get_profile_usage` | `async def get_profile_usage(self, network_id: str, profile_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | |
| `get_unprofiled_devices` | `async def get_unprofiled_devices(self, network_id: str, *, start: str, end: str, cadence: Optional[str]=None, timezone: Optional[str]=None) -> Dict[str, Any]` | |
| `get_unprofiled_summary` | `async def get_unprofiled_summary(self, network_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None) -> Dict[str, Any]` | |
| `get_report_settings` | `async def get_report_settings(self, network_id: str) -> Dict[str, Any]` | No query parameters |
| `set_report_settings` | `async def set_report_settings(self, network_id: str, *, cadence: str, notification_day: str) -> Dict[str, Any]` | `PUT` with a JSON body. **Unverified write** — its side effects have not been characterised against a live network. Read `get_report_settings` first, write only when the stored values differ, never retry |

> **Note**: `BurstReportersAPI.get_burst_reporters` and `OUICheckAPI.run_ouicheck` were removed
> in v8.0.0 (both returned 404 / declared no such operation upstream). `PasswordAPI` was removed
> entirely in v8.0.0 — the endpoint returns 404 on every path version; use
> `NetworksAPI.get_network` for the same fields.

</details>

---

## Exceptions

| Name | Base class | Raised when |
|------|-----------|-------------|
| `EeroException` | `Exception` | Base for all SDK errors; `__init__(self, message: str='An error occurred', *, envelope: Optional[Dict[str, Any]]=None, error_code: Optional[str]=None)`; attributes `message`, `envelope` (raw response envelope or `None`), `error_code` (`meta.error` or `None`); `is_auth_error()` → `False` |
| `EeroAuthenticationException` | `EeroException` | Every HTTP 401 (after the refresh-and-replay attempt) and local "no session token" failures; `is_auth_error()` → `True` |
| `EeroRateLimitException` | `EeroException` | HTTP 429, or `error.rate.limit` on any status |
| `EeroNetworkException` | `EeroException` | Low-level connection/transport failures; `envelope` is `None` |
| `EeroTimeoutException` | `EeroException` | Request exceeded the client timeout; `envelope` is `None` |
| `EeroValidationException` | `EeroException` | `__init__(self, field: str, message: str, *, envelope=None, error_code=None)` for client-side validation; `from_response(message, *, envelope=None, error_code=None)` (sets `field="request"`) for an API 400 carrying a `VALIDATION` catalogue string. **Not** an `EeroAPIException` |
| `EeroAPIException` | `EeroException` | `__init__(self, status_code: Optional[int], message: str, *, envelope=None, error_code=None)`; `str(err)` is `API error <status>: <catalogue string or "unrecognised error string">`; `is_auth_error()` → `status_code == 401` (never produced by the transport, which raises `EeroAuthenticationException` for 401). Raised for 3xx, oversized/invalid bodies, every `DOMAIN` string, and any status not claimed by a subclass |
| `EeroAccessDeniedException` | `EeroAPIException` | HTTP 403 with `error.access.denied`; not an auth error |
| `EeroClientBlockedException` | `EeroAPIException` | `error.app.version.blocked` on any status |
| `EeroNotFoundException` | `EeroAPIException` | Every HTTP 404. `__init__(self, resource_type: str, resource_id: str, *, envelope=None, error_code=None)` for direct construction; `from_response(message, *, status_code: int=404, envelope=None, error_code=None)` (both resource attributes `None`) is what the transport uses |
| `EeroPremiumRequiredException` | `EeroAPIException` | A `PREMIUM` string on any status. `__init__(self, feature: str='This feature', *, envelope=None, error_code=None)`; `from_response(message, *, status_code: Optional[int]=None, envelope=None, error_code=None)` |
| `EeroFeatureUnavailableException` | `EeroAPIException` | A `FEATURE_UNAVAILABLE` string on any status. `__init__(self, feature: str, reason: str='not supported on this device', *, envelope=None, error_code=None)`; `from_response(message, *, status_code: Optional[int]=None, envelope=None, error_code=None)` sets `feature` to the `error_code` and `reason` to the message |

Full hierarchy, the catalogue groups, and handling patterns: [Error Handling](Error-Handling).

### The error catalogue (`eero.errors`)

| Symbol | Signature / values | Root-importable? |
|--------|--------------------|------------------|
| `ErrorGroup` | `str, Enum`: `SESSION`, `SESSION_REFRESH`, `VERIFICATION`, `ACCESS_DENIED`, `NOT_FOUND`, `RATE_LIMIT`, `VALIDATION`, `PREMIUM`, `FEATURE_UNAVAILABLE`, `CLIENT_BLOCKED`, `DOMAIN` | Yes |
| `classify_error_code` | `classify_error_code(error_code: Optional[str]) -> Optional[ErrorGroup]` — case-insensitive, whitespace-trimmed; `None` for unrecognised/free-text/absent input | Yes |
| `exception_for_error` | `exception_for_error(status_code: int, *, envelope: Optional[Dict[str, Any]], error_code: Optional[str]) -> EeroException` — builds (never raises) the exception for a non-2xx/3xx response; status first, catalogue string second | Yes |
| `message_for_error_code` | `message_for_error_code(error_code: Optional[str]) -> str` — the normalised catalogue string or `"unrecognised error string"` | `eero.errors` only |
| `SESSION_ERRORS`, `SESSION_REFRESH_ERRORS`, `VERIFICATION_ERRORS`, `ACCESS_DENIED_ERRORS`, `NOT_FOUND_ERRORS`, `RATE_LIMIT_ERRORS`, `VALIDATION_ERRORS`, `PREMIUM_ERRORS`, `FEATURE_UNAVAILABLE_ERRORS`, `CLIENT_BLOCKED_ERRORS`, `DOMAIN_ERRORS` | `FrozenSet[str]` — the member strings of each group | `eero.errors` only |

The full string list per group is in [Error Handling](Error-Handling#the-groups).

---

## Module-level exports

`from eero import ...` — the package `__all__` verbatim from `src/eero/__init__.py`:

```python
__all__ = [
    "EeroAPI",
    "EeroClient",
    "EeroException",
    "EeroAccessDeniedException",
    "EeroAPIException",
    "EeroAuthenticationException",
    "EeroClientBlockedException",
    "EeroFeatureUnavailableException",
    "EeroNetworkException",
    "EeroNotFoundException",
    "EeroPremiumRequiredException",
    "EeroRateLimitException",
    "EeroTimeoutException",
    "EeroValidationException",
    # Error catalogue
    "ErrorGroup",
    "classify_error_code",
    "exception_for_error",
    # URL / ID utilities
    "id_from_url",
    "join_api_path",
    "resolve_link",
    "resource_url",
    "self_url",
    "sub_resource_url",
    # Secure logging utilities
    "get_secure_logger",
    "SecureLoggerAdapter",
    "redact_sensitive",
]
```

Every exception class is importable from the package root. `message_for_error_code` and the
per-group `*_ERRORS` frozensets are `eero.errors`-only (`from eero.errors import ...`).

> ⚠️ **Warning:** `EeroDeviceType`, `EeroNetworkStatus`, and `EeroDeviceStatus` (defined in
> `src/eero/const.py`) are **NOT** re-exported from the package root. `eero/__init__.py` does
> not import from `const.py` at all. Import them explicitly:
> `from eero.const import EeroDeviceType`.

---

## Constants

Public, useful constants from `src/eero/const.py` (import via `from eero.const import ...`):

| Constant | Value | Purpose |
|----------|-------|---------|
| `API_HOST` | `"https://api-user.e2ro.com"` | The only host the session token is ever sent to |
| `API_VERSION` | `"2.2"` | Path version for reads and most writes |
| `API_ENDPOINT` | `f"{API_HOST}/{API_VERSION}"` | Base URL for reads and most writes |
| `DEVICE_UPDATE_ENDPOINT` | `f"{API_HOST}/2.3"` | Base URL for device-mutation writes only |
| `LOGIN_ENDPOINT` | `f"{API_ENDPOINT}/login"` | Form-encoded `login=` body |
| `LOGIN_VERIFY_ENDPOINT` | `f"{API_ENDPOINT}/login/verify"` | Form-encoded `code=` body |
| `LOGIN_RESEND_ENDPOINT` | `f"{LOGIN_ENDPOINT}/resend"` | JSON `{}` body |
| `LOGIN_REFRESH_ENDPOINT` | `f"{API_ENDPOINT}/login/refresh"` | The only refresh path; JSON `""` body, authenticated by the session token |
| `LOGOUT_ENDPOINT` | `f"{API_ENDPOINT}/logout"` | Form-encoded body |
| `LOGOUT_COOKIE_FIELD_NAME` | `"Cookie"` | Name of the single form field the logout endpoint expects |
| `SESSION_COOKIE_PREFIX` | `"s="` | Prefix of that field's value (`s=<token>`), and of the legacy cookie |
| `ACCOUNT_ENDPOINT` | `f"{API_ENDPOINT}/account"` | |
| `DEFAULT_USER_AGENT` | `"eero/3.0 (iPhone; iOS 17.0)"` | Sent on every request; mobile UA reduces rate-limiting risk |
| `DEFAULT_ACCEPT_LANGUAGE` | `"en-US"` | Default for the `accept_language` constructor option (`X-Accept-Language` header) |
| `CACHE_TIMEOUT` | `60` | Unused — not imported anywhere in `src/`. `EeroClient` hardcodes `cache_timeout: int = 60` instead |
| `MAX_RESPONSE_BYTES` | `10 * 1024 * 1024` (10 MiB) | Guards against unbounded response bodies |
| `GET_RETRY_DELAY_SECONDS` | `0.5` | Fixed pause between bounded GET retries (`get_retries`) |
| `CREDENTIAL_SCHEMA_VERSION` | `2` | Written into every persisted credential record as `schema_version`; a record without it is migrated on load |

> **Note**: Six constants (the old header dict, the refresh-endpoint tuple and its account
> fallback, the two storage-key names, and the error-body cap) were removed in v8.0.0 — they are
> listed with their replacements in [Migration](Migration#removed-constants).

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
