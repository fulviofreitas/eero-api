# 📚 API Reference

Exhaustive signature reference for every public class and method in the SDK.

---

## Orientation

The SDK is a layered stack:

```
EeroClient   → high-level facade: caching, network_id resolution, one method per operation
    ↓
EeroAPI      → composition root: aggregates 27 domain APIs as attributes (client._api.<domain>)
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
resolves the network via `preferred_network_id` (if set) or by fetching the account's networks.

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
| `get_settings` | `async def get_settings(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
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
| `set_device_priority` | `async def set_device_priority(self, device_id: str, prioritized: bool, duration_minutes: Optional[int]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | ⚠️ **Deprecated / confirmed no-op** since v6.0.0 — returns 200 but changes nothing server-side (see issue #111). Use [SQM](#sqm--qos) instead |

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
| `set_custom_dns` | `async def set_custom_dns(self, dns_servers: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_dns_mode` | `async def set_dns_mode(self, mode: str, custom_servers: Optional[List[str]]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: `EeroClient` has no wrapper for `DnsAPI.clear_custom_dns()` or `DnsAPI.set_ipv6_dns()`
> — call them via `client._api.dns` directly.

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
| `set_thread_enabled` | `async def set_thread_enabled(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Named differently from `SecurityAPI.set_thread()` |
| `configure_security` | `async def configure_security(self, wpa3: Optional[bool]=None, band_steering: Optional[bool]=None, upnp: Optional[bool]=None, ipv6: Optional[bool]=None, thread: Optional[bool]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

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
| `get_reservations` | `async def get_reservations(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Added v6.1.0 |
| `create_reservation` | `async def create_reservation(self, reservation_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `update_reservation` | `async def update_reservation(self, reservation_id: str, reservation_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete_reservation` | `async def delete_reservation(self, reservation_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

### Forwards

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_forwards` | `async def get_forwards(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Added v6.2.0 |
| `create_forward` | `async def create_forward(self, forward_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete_forward` | `async def delete_forward(self, forward_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

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
| `get_burst_reporters` | `async def get_burst_reporters(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_insights` | see [Networks](#networks) | `Dict[str, Any]` | |

### Blacklist

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_blacklist` | see [Networks](#networks) | `Dict[str, Any]` | |

> **Note**: `EeroClient` has no wrapper for `BlacklistAPI.add_to_blacklist()` or
> `BlacklistAPI.remove_from_blacklist()` — call them via `client._api.blacklist` directly.

### Deprecated (Activity)

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_activity` | `async def get_activity(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | ⚠️ Deprecated since v6.0.0 — upstream endpoint returns 404 |
| `get_activity_clients` | `async def get_activity_clients(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | ⚠️ Deprecated since v6.0.0 — upstream endpoint returns 404 |
| `get_activity_for_device` | `async def get_activity_for_device(self, device_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | ⚠️ Deprecated since v6.0.0 — upstream endpoint returns 404 |
| `get_activity_history` | `async def get_activity_history(self, network_id: Optional[str]=None, period: str='day') -> Dict[str, Any]` | `Dict[str, Any]` | ⚠️ Deprecated since v6.0.0 — upstream endpoint returns 404 |
| `get_activity_categories` | `async def get_activity_categories(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | ⚠️ Deprecated since v6.0.0 — upstream endpoint returns 404 |

### Misc

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_ac_compat` | `async def get_ac_compat(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_ouicheck` | `async def get_ouicheck(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_password` | `async def get_password(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_updates` | `async def get_updates(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

### Cache

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `clear_cache` | `def clear_cache(self) -> None` | `None` | Synchronous; drops all cached entries regardless of TTL |

---

## Domain APIs

Reach every domain API through `client._api.<attr>` (on `EeroClient`) or directly on an
`EeroAPI` instance (`api.<attr>`). The attribute name is identical to the module name for
every domain in this SDK — there are no naming divergences.

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
| `block_device` | `async def block_device(self, network_id: str, device_id: str, blocked: bool) -> Dict[str, Any]` | `Dict[str, Any]` | Writes via `/2.3` endpoint |
| `pause_device` | `async def pause_device(self, network_id: str, device_id: str, paused: bool) -> Dict[str, Any]` | `Dict[str, Any]` | Writes via `/2.3` endpoint |
| `set_device_priority` | `async def set_device_priority(self, network_id: str, device_id: str, prioritized: bool, duration_minutes: Optional[int]=None) -> Dict[str, Any]` | `Dict[str, Any]` | ⚠️ Confirmed no-op (DeprecationWarning, returns 200, no server-side effect) — use SQM instead |

> Note: there is no `get_device_priority` on `DevicesAPI` — `EeroClient.get_device_priority()`
> is implemented by calling `get_device()` and returning the full payload.

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
| `set_custom_dns` | `async def set_custom_dns(self, network_id: str, dns_servers: List[str]) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `clear_custom_dns` | `async def clear_custom_dns(self, network_id: str) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |
| `set_dns_mode` | `async def set_dns_mode(self, network_id: str, mode: str, custom_servers: Optional[List[str]]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_ipv6_dns` | `async def set_ipv6_dns(self, network_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | No `EeroClient` wrapper |

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
| `set_thread` | `async def set_thread(self, network_id: str, enabled: bool) -> Dict[str, Any]` | `Dict[str, Any]` | `EeroClient` exposes this as `set_thread_enabled()` |
| `configure_security` | `async def configure_security(self, network_id: str, wpa3: Optional[bool]=None, band_steering: Optional[bool]=None, upnp: Optional[bool]=None, ipv6: Optional[bool]=None, thread: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

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
<summary>📦 DiagnosticsAPI, InsightsAPI, RoutingAPI, ThreadAPI, SupportAPI, SettingsAPI (single-purpose domains)</summary>

| Class | Attribute | Method | Signature | Notes |
|-------|-----------|--------|-----------|-------|
| `DiagnosticsAPI` | `client._api.diagnostics` | `get_diagnostics` | `async def get_diagnostics(self, network_id: str) -> Dict[str, Any]` | |
| `DiagnosticsAPI` | `client._api.diagnostics` | `run_diagnostics` | `async def run_diagnostics(self, network_id: str) -> Dict[str, Any]` | |
| `InsightsAPI` | `client._api.insights` | `get_insights` | `async def get_insights(self, network_id: str, *, start: str, end: str, insight_type: str, cadence: str='daily') -> Dict[str, Any]` | keyword-only args |
| `InsightsAPI` | `client._api.insights` | `run_insights` | `async def run_insights(self, network_id: str) -> Dict[str, Any]` | No `EeroClient` wrapper |
| `RoutingAPI` | `client._api.routing` | `get_routing` | `async def get_routing(self, network_id: str) -> Dict[str, Any]` | |
| `ThreadAPI` | `client._api.thread` | `get_thread` | `async def get_thread(self, network_id: str) -> Dict[str, Any]` | |
| `SupportAPI` | `client._api.support` | `get_support` | `async def get_support(self, network_id: str) -> Dict[str, Any]` | |
| `SupportAPI` | `client._api.support` | `request_support` | `async def request_support(self, network_id: str, request_data: Dict[str, Any]) -> Dict[str, Any]` | No `EeroClient` wrapper |
| `SettingsAPI` | `client._api.settings` | `get_settings` | `async def get_settings(self, network_id: str) -> Dict[str, Any]` | |

Each of these constructors is `def __init__(self, auth_api: AuthAPI) -> None`.

</details>

<details>
<summary>📦 TransferAPI, DataUsageAPI, BurstReportersAPI, ACCompatAPI, OUICheckAPI, PasswordAPI, UpdatesAPI (stats & misc)</summary>

| Class | Attribute | Method | Signature | Notes |
|-------|-----------|--------|-----------|-------|
| `TransferAPI` | `client._api.transfer` | `get_transfer_stats` | `async def get_transfer_stats(self, network_id: str, device_id: Optional[str]=None) -> Dict[str, Any]` | |
| `DataUsageAPI` | `client._api.data_usage` | `get_data_usage` | `async def get_data_usage(self, network_id: str, payload: Dict[str, Any], resource: Optional[str]=None) -> Dict[str, Any]` | `payload` is required here (unlike the `EeroClient` wrapper, where it defaults to `None`) |
| `BurstReportersAPI` | `client._api.burst_reporters` | `get_burst_reporters` | `async def get_burst_reporters(self, network_id: str) -> Dict[str, Any]` | |
| `BurstReportersAPI` | `client._api.burst_reporters` | `create_burst_reporter` | `async def create_burst_reporter(self, network_id: str, reporter_data: Dict[str, Any]) -> Dict[str, Any]` | No `EeroClient` wrapper |
| `ACCompatAPI` | `client._api.ac_compat` | `get_ac_compat` | `async def get_ac_compat(self, network_id: str) -> Dict[str, Any]` | |
| `OUICheckAPI` | `client._api.ouicheck` | `get_ouicheck` | `async def get_ouicheck(self, network_id: str) -> Dict[str, Any]` | |
| `OUICheckAPI` | `client._api.ouicheck` | `run_ouicheck` | `async def run_ouicheck(self, network_id: str) -> Dict[str, Any]` | No `EeroClient` wrapper |
| `PasswordAPI` | `client._api.password` | `get_password` | `async def get_password(self, network_id: str) -> Dict[str, Any]` | |
| `UpdatesAPI` | `client._api.updates` | `get_updates` | `async def get_updates(self, network_id: str) -> Dict[str, Any]` | |

Each of these constructors is `def __init__(self, auth_api: AuthAPI) -> None`.

</details>

<details>
<summary>📦 ActivityAPI (<code>client._api.activity</code>) — ⚠️ fully deprecated since v6.0.0</summary>

All methods return `Dict[str, Any]` but the upstream endpoints return HTTP 404 as of v6.0.0.
Kept for backward compatibility only.

| Method | Signature |
|--------|-----------|
| Constructor | `def __init__(self, auth_api: AuthAPI) -> None` |
| `get_activity` | `async def get_activity(self, network_id: str) -> Dict[str, Any]` |
| `get_activity_clients` | `async def get_activity_clients(self, network_id: str) -> Dict[str, Any]` |
| `get_activity_for_device` | `async def get_activity_for_device(self, network_id: str, device_id: str) -> Dict[str, Any]` |
| `get_activity_history` | `async def get_activity_history(self, network_id: str, period: str='day') -> Dict[str, Any]` |
| `get_activity_categories` | `async def get_activity_categories(self, network_id: str) -> Dict[str, Any]` |

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
| `EeroNotFoundException` | `EeroException` | `__init__(self, resource_type: str, resource_id: str)` — resource lookup miss |
| `EeroPremiumRequiredException` | `EeroException` | `__init__(self, feature: str='This feature')` — Eero Plus/Secure gate |
| `EeroFeatureUnavailableException` | `EeroException` | `__init__(self, feature: str, reason: str='not supported on this device')` |
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

> ⚠️ **Warning:** `EeroNotFoundException`, `EeroPremiumRequiredException`,
> `EeroFeatureUnavailableException`, and `EeroValidationException`'s siblings are importable
> from `eero.exceptions` but only `EeroValidationException` (and the six listed above) are
> re-exported at the package root. Import the others explicitly:
> `from eero.exceptions import EeroNotFoundException`.

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
| `CACHE_TIMEOUT` | `60` | Default `EeroClient` cache TTL, in seconds |
| `MAX_RESPONSE_BYTES` | `10 * 1024 * 1024` (10 MiB) | Guards against unbounded response bodies |
| `MAX_ERROR_BODY_CHARS` | `512` | Caps how much of a hostile/oversized body is embedded in error messages and logs |
| `SESSION_TOKEN_KEY` | `"session_token"` | Keyring/file storage key |
| `REFRESH_TOKEN_KEY` | `"refresh_token"` | Keyring/file storage key |

> ⚠️ **Warning:** The `/2.2` vs `/2.3` split matters for device mutations. `DevicesAPI`
> methods that pause, block, rename, or set priority on a device are silently no-ops on `/2.2`
> — the backend returns 200 OK but the change never persists server-side. `DevicesAPI` routes
> these specific writes to `DEVICE_UPDATE_ENDPOINT` (`/2.3`) instead of `API_ENDPOINT` (`/2.2`).
> Reads and every other domain continue to use `/2.2`. See issue #102.

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
