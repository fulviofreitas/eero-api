# 📚 API Reference

Exhaustive signature reference for every public class and method in the SDK.

---

## Orientation

The SDK is a layered stack:

```
EeroClient   → high-level facade: caching, network_id resolution, cached envelopes passed as parent=, one method per operation
    ↓
EeroAPI      → composition root: aggregates 37 domain APIs + AuthAPI (38 API classes total) as attributes (client._api.<domain>)
    ↓
Domain APIs  → one class per Eero Cloud resource family (NetworksAPI, DevicesAPI, DnsPoliciesAPI, WanAPI, ...)
    ↓
eero.api.links → resolves a bare ID / API path / absolute URL, or the link published on a parent envelope, to the request URL
    ↓
BaseAPI / AuthenticatedAPI → HTTP transport, error mapping, credential placement (X-User-Token header)
```

Use `EeroClient` for almost everything — it's the only layer with the 60s TTL cache and
`network_id` auto-resolution, and it passes its cached envelopes as `parent=` so domain calls
follow the links the API published. Drop to `EeroAPI` (or a domain API directly) when you need
explicit control over which network a call targets, when you want to pass `parent=` yourself,
or when a domain method has no `EeroClient` wrapper (flagged per-domain below).

> ⚠️ **Warning:** Preferred-network resolution (`set_preferred_network()` / `preferred_network_id`)
> exists on `EeroClient` ONLY. The same-named symbols were removed from `EeroAPI` in v5.0.0 —
> they never wired through to any domain API. When using `EeroAPI` or a domain API directly,
> pass `network_id` explicitly on every call.

Every method (both `EeroClient` and the domain APIs) returns a raw `Dict[str, Any]` envelope
shaped `{"meta": {...}, "data": {...}}` unless noted otherwise. See [Raw Response Format](Raw-Response-Format).

### Reading the tables

- **Resource arguments are polymorphic.** Every `network_id` / `eero_id` / `mac` / `profile` /
  `forward` / `reservation` / `invite_id` argument accepts a bare ID, the resource's API path,
  or an absolute API-host URL. See [Network Targeting](Network-Targeting#resource-links-ids-paths-and-urls-are-interchangeable).
- **`parent=`** is a keyword-only, read-only envelope on every domain method. The "Parent"
  note in each table says which envelope the method uses it for (network / eero / device /
  profile / guest network) and which link it reads. "unused" means the argument is accepted
  for signature consistency and ignored. `EeroClient` wrappers never expose `parent=` — the
  facade supplies its cached envelope automatically.
- **Status** is one of: *verified read*, *read* (verification not stated), *verified write*,
  *unverified write* (logs one `WARNING` before the request), *settings-class* (unverified
  write that may reboot the whole mesh), *disconnects* (unverified write that disconnects
  clients while it takes effect). See [Python API — Writes and safety](Python-API#writes-and-safety).
- **Request** gives the verb, the path or link name, and the body encoding: *JSON*, *form*
  (`application/x-www-form-urlencoded`), *`""`* (the two-character JSON-string body), *none*
  (no body), or *query* (parameters only). Paths are relative to `API_HOST/<version>`; the
  version is `2.2` unless stated.

---

## EeroClient

`from eero import EeroClient`. Constructor:

```python
def __init__(self, session: Optional[ClientSession]=None, cookie_file: Optional[str]=None, use_keyring: bool=True, cache_timeout: int=60, *, send_legacy_cookie: bool=True, accept_language: str='en-US', get_retries: int=0) -> None
```

The three keyword-only options (`send_legacy_cookie`, `accept_language`, `get_retries`) are forwarded unchanged to `EeroAPI` → `AuthAPI` → the transport; see [Configuration](Configuration#-constructor-reference).

All `network_id` parameters below are optional kwargs (trailing on most methods; leading on the
few whose other parameters are all keyword-only) — when omitted, `EeroClient` resolves the
network via `preferred_network_id` (if set); only 24 methods will additionally auto-discover by
fetching the account's networks. Every other method raises `EeroException` if neither is
available. See [Network Targeting](Network-Targeting) for the exact list. `device_id` on the
facade is the device's MAC address (the domain methods name it `mac`).

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
| `get_account` | `async def get_account(self, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | Cached |
| `set_account_name` | `async def set_account_name(self, name: str) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `set_account_email` | `async def set_account_email(self, email: str) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; confirm with `verify_account_email` |
| `verify_account_email` | `async def verify_account_email(self, code: str) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `set_account_phone` | `async def set_account_phone(self, phone: str) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; confirm with `verify_account_phone` |
| `verify_account_phone` | `async def verify_account_phone(self, code: str) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `set_account_consents` | `async def set_account_consents(self, *, marketing_emails: bool) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `get_sms_countries` | `async def get_sms_countries(self) -> Dict[str, Any]` | `Dict[str, Any]` | Read |
| `set_push_settings` | `async def set_push_settings(self, settings: Mapping[str, bool]) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; account-level push toggles (`networkOffline`, `nodeOffline`) |
| `get_premium_customer` | `async def get_premium_customer(self) -> Dict[str, Any]` | `Dict[str, Any]` | Read; not network-scoped |
| `query_invite` | `async def query_invite(self, invite_code: str) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified; not network-scoped; the code is never logged |

### Networks

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_networks` | `async def get_networks(self, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | Cached |
| `get_network` | `async def get_network(self, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | Cached; the cached envelope becomes `parent=` for every network-scoped call |
| `set_preferred_network` | `def set_preferred_network(self, network_id: str) -> None` | `None` | EeroClient-only; not a property |
| `preferred_network_id` | `def preferred_network_id(self) -> Optional[str]` | `Optional[str]` | **Property** — EeroClient-only |
| `get_premium_status` | `async def get_premium_status(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | The network envelope |
| `set_network_name` | `async def set_network_name(self, name: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Disconnects; form-encoded to the `settings` link |
| `set_network_password` | `async def set_network_password(self, password: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Disconnects; form-encoded to the `password` link |
| `clear_network_password` | `async def clear_network_password(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Disconnects; DELETE on the `password` link |
| `get_guest_network` | `async def get_guest_network(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Read |
| `set_guest_network` | `async def set_guest_network(self, enabled: bool, name: Optional[str]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Disconnects guest clients; no `password=` — see `set_guest_password` |
| `set_guest_password` | `async def set_guest_password(self, password: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Disconnects guest clients |
| `clear_guest_password` | `async def clear_guest_password(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Disconnects guest clients |
| `run_speed_test` | `async def run_speed_test(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | POST `""` to the `speedtest` link |
| `get_speed_tests` | `async def get_speed_tests(self, network_id: Optional[str]=None, *, limit: Optional[int]=None, start_time: Optional[str]=None, end_time: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Read; query params `limit`, `startTime`, `endTime` |
| `get_diagnostics` | `async def get_diagnostics(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `run_diagnostics` | `async def run_diagnostics(self, network_id: Optional[str]=None, *, device: Optional[str]=None, symptom: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified body shape |
| `get_routing` | `async def get_routing(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_support` | `async def get_support(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_updates` | `async def get_updates(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `apply_update` | `async def apply_update(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified; reboots every node |
| `get_ac_compat` | `async def get_ac_compat(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_ouicheck` | `async def get_ouicheck(self, network_id: Optional[str]=None, *, serial: str, version: str) -> Dict[str, Any]` | `Dict[str, Any]` | `serial` and `version` are keyword-only and required — the API returns `404` without them |
| `get_permissions` | `async def get_permissions(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_entitlement_features` | `async def get_entitlement_features(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_upsell_features` | `async def get_upsell_features(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_model_capabilities` | `async def get_model_capabilities(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Read; `network_id` is sent as the `networkId` query parameter, bare ID only |

### Thread

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_thread` | `async def get_thread(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | GET the `thread` link |
| `set_thread_enabled` | `async def set_thread_enabled(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `update_thread` | `async def update_thread(self, *, thread_enable: Optional[bool]=None, enable_credential_syncing: Optional[bool]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; at least one field required |
| `regenerate_thread_credentials` | `async def regenerate_thread_credentials(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |

### Eeros

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_eeros` | `async def get_eeros(self, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | Cached; the matching entry becomes `parent=` for eero calls |
| `get_eero` | `async def get_eero(self, eero_id: str, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | Never cached (`refresh_cache` has no effect) |
| `reboot_eero` | `async def reboot_eero(self, eero_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | POST `""` to the `reboot` link |
| `set_location` | `async def set_location(self, eero_id: str, location: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; form-encoded |
| `get_connections` | `async def get_connections(self, eero_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Read |
| `get_eero_support` | `async def get_eero_support(self, eero_serial: str) -> Dict[str, Any]` | `Dict[str, Any]` | Read; `EeroNotFoundException` on some nodes |
| `node_action` | `async def node_action(self, eero_id: str, action: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; `POWER_CYCLE_ALL_PORTS` / `POWER_CYCLE_ALL_PORTS_AND_REBOOT` (reboots the eero) |
| `port_action` | `async def port_action(self, eero_id: str, interface_number: str, action: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; disruptive to the port |
| `led_cycle` | `async def led_cycle(self, eero_serial: str, *, colors: Any, duration: str, time_per_color: str) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; form-encoded `colors[]` |
| `get_led_status` | `async def get_led_status(self, eero_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | The eero envelope (`led_on`, `led_brightness`) |
| `set_led` | `async def set_led(self, eero_id: str, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified write (2026-09-20): form-encoded to the `led_action` link; turns the node's light off and on with no reboot. The pre-v8.0.0 write was verified to change nothing |
| `set_led_brightness` | `async def set_led_brightness(self, eero_id: str, brightness: int, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; 0–100 |
| `get_nightlight` | `async def get_nightlight(self, eero_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `EeroFeatureUnavailableException` without a nightlight |
| `set_nightlight` | `async def set_nightlight(self, eero_id: str, enabled: Optional[bool]=None, brightness_percentage: Optional[int]=None, schedule: Optional[Dict[str, Any]]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; at least one field |
| `set_nightlight_brightness` | `async def set_nightlight_brightness(self, eero_id: str, brightness_percentage: int, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Delegates to `set_nightlight` |
| `set_nightlight_schedule` | `async def set_nightlight_schedule(self, eero_id: str, schedule: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Delegates to `set_nightlight`; `schedule` forwarded unchanged |
| `nightlight_override` | `async def nightlight_override(self, eero_id: str, *, brightness_percentage: int, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; preview |
| `set_pppoe` | `async def set_pppoe(self, eero_serial_or_id: str, *, username: str, password: str) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; returns the encrypted credential blob |

### Devices

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_devices` | `async def get_devices(self, network_id: Optional[str]=None, refresh_cache: bool=False, *, thread: Optional[bool]=None, proxied_node: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Cached; a filtered call (`thread=` / `proxied_node=`, sent as query params) bypasses the cache |
| `get_device` | `async def get_device(self, device_id: str, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | Cached |
| `set_device_nickname` | `async def set_device_nickname(self, device_id: str, nickname: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | **Verified** write on `2.3` — see [Constants](#constants) |
| `pause_device` | `async def pause_device(self, device_id: str, paused: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | **Verified** write on `2.3` |
| `block_device` | `async def block_device(self, device_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified (form-encoded `mac`); POST `networks/{id}/blacklist` |
| `unblock_device` | `async def unblock_device(self, device_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified; DELETE `networks/{id}/blacklist/{mac}` |
| `update_device_via_link` | `async def update_device_via_link(self, device_id: str, *, nickname: Optional[str]=None, paused: Optional[bool]=None, profile: Optional[str]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; JSON PUT to the device's own URL on `2.2`. Prefer the two verified methods for nickname/pause |
| `set_device_type` | `async def set_device_type(self, device_id: str, device_type: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `get_device_labels` | `async def get_device_labels(self, device_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Read |
| `set_device_labels` | `async def set_device_labels(self, device_id: str, *, make_label: Optional[str]=None, model_label: Optional[str]=None, version_label: Optional[str]=None, type_label: Optional[str]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; labels sent as query parameters |
| `set_device_secondary_wan_access` | `async def set_device_secondary_wan_access(self, mac: str, *, deny: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; `2.3` |
| `get_device_priority` | `async def get_device_priority(self, device_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | No dedicated domain endpoint — internally calls `get_device()` and returns the full device payload |

> **Note**: `set_device_priority` was removed in v8.0.0 — the API never exposed device-level
> priority. Use [SQM](#sqm--qos) instead.

### Profiles

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_profiles` | `async def get_profiles(self, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | Cached |
| `get_profile` | `async def get_profile(self, profile_id: str, network_id: Optional[str]=None, refresh_cache: bool=False) -> Dict[str, Any]` | `Dict[str, Any]` | Cached |
| `pause_profile` | `async def pause_profile(self, profile_id: str, paused: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `create_profile` | `async def create_profile(self, name: str, *, devices: Optional[List[str]]=None, paused: Optional[bool]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `devices` are device URLs, sent as `[{"url": ...}]` |
| `rename_profile` | `async def rename_profile(self, profile_id: str, name: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete_profile` | `async def delete_profile(self, profile_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `get_profile_devices` | `async def get_profile_devices(self, profile_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `set_profile_devices` | `async def set_profile_devices(self, profile_id: str, device_urls: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

> **Note**: A profile has exactly four fields (`devices`, `name`, `paused`, `url`). The former
> blocked-applications wrappers and the domain content-filter / block-list writes were removed
> in v8.0.0 — see [DNS policies](#dns-policies) and [Deprecations](Deprecations#800--removals).

### Schedules

Scheduled pauses are sub-resources of a profile (`networks/{id}/profiles/{profile}/schedules`).
Every write is unverified.

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_schedules` | `async def get_schedules(self, profile_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `data` is a list |
| `create_schedule` | `async def create_schedule(self, profile_id: str, *, name: str, days: List[str], start: str, end: str, enabled: bool=True, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `update_schedule` | `async def update_schedule(self, schedule: Any, *, name: Optional[str]=None, days: Optional[List[str]]=None, start: Optional[str]=None, end: Optional[str]=None, enabled: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `schedule` is the pause's own path/URL or envelope; no `network_id` |
| `delete_schedule` | `async def delete_schedule(self, schedule: Any) -> Dict[str, Any]` | `Dict[str, Any]` | As above |
| `clear_profile_schedule` | `async def clear_profile_schedule(self, profile_id: str, network_id: Optional[str]=None) -> List[Dict[str, Any]]` | `List[Dict[str, Any]]` | One read + one DELETE per pause; returns every DELETE's envelope |
| `enable_bedtime` | `async def enable_bedtime(self, profile_id: str, start_time: str, end_time: str, days: Optional[List[str]]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Creates one pause |

> **Note**: `EeroClient` has no wrapper for `ScheduleAPI.set_weekday_bedtime()` or
> `ScheduleAPI.set_weekend_bedtime()` — call them via `client._api.schedule` directly.

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
| `enable_ddns` | `async def enable_ddns(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; PUT with no body |
| `disable_ddns` | `async def disable_ddns(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; PUT with no body |

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
> This applies to every DNS write method — including `set_dns_caching` — and the SDK treats
> every other settings-class write the same way. See
> [Python API — Writes and safety](Python-API#writes-and-safety).

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

### DNS policies

Premium feature. Removal on the list endpoints is `is_delete=True` on the same PUT.

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_advanced_content_filter` | `async def get_advanced_content_filter(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read; `allowed_list` / `blocked_list` |
| `allow_domain` | `async def allow_domain(self, domain: str, network_id: Optional[str]=None, *, add_cname: Optional[bool]=None, reason_to_allow: Optional[int]=None, is_delete: Optional[bool]=None, keep_profiles: Optional[List[str]]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `allow_cnames` | `async def allow_cnames(self, domains: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `block_domain` | `async def block_domain(self, domain: str, network_id: Optional[str]=None, *, is_delete: Optional[bool]=None, keep_profiles: Optional[List[str]]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `allow_domain_for_profiles` | `async def allow_domain_for_profiles(self, domain: str, network_id: Optional[str]=None, *, profiles: List[str], override: Optional[bool]=None, add_cname: Optional[bool]=None, reason_to_allow: Optional[int]=None, is_delete: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `allow_cnames_for_profiles` | `async def allow_cnames_for_profiles(self, domains: List[str], network_id: Optional[str]=None, *, profiles: List[str]) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `block_domain_for_profiles` | `async def block_domain_for_profiles(self, domain: str, network_id: Optional[str]=None, *, profiles: List[str], is_delete: Optional[bool]=None, override: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `get_dns_policy_applications` | `async def get_dns_policy_applications(self, profile_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read; `applications` / `categories_list` |
| `set_profile_blocked_applications` | `async def set_profile_blocked_applications(self, profile_id: str, applications: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; replaces the full list |
| `get_subnet_content_filters` | `async def get_subnet_content_filters(self, subnet_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `set_subnet_content_filters` | `async def set_subnet_content_filters(self, filters: Mapping[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; forwarded unchanged |

> **Not exposed**: the network- and profile-level DNS-policy *settings* (content-category
> toggles, ad-block on/off). No field on the network or profile envelope carries a URL for
> those endpoints, so the SDK has no link to follow and does not guess one.

### SQM / QoS

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_sqm_settings` | `async def get_sqm_settings(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | The network envelope; `data["sqm"]` |
| `set_sqm` | `async def set_sqm(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; `sqm` query parameter, no body |

> **Note**: The former bandwidth and auto SQM variants were removed in v8.0.0 — the API declares
> no such fields. See [Deprecations](Deprecations#800--removals).

### Security

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_security_settings` | `async def get_security_settings(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | The network envelope |
| `set_wpa3` | `async def set_wpa3(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `settings` link |
| `set_band_steering` | `async def set_band_steering(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `settings` link |
| `set_upnp` | `async def set_upnp(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `settings` link |
| `set_ipv6` | `async def set_ipv6(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `settings` link |
| `configure_security` | `async def configure_security(self, wpa3: Optional[bool]=None, band_steering: Optional[bool]=None, upnp: Optional[bool]=None, ipv6: Optional[bool]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `settings` link |
| `get_wpa3_per_band` | `async def get_wpa3_per_band(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `set_wpa3_per_band` | `async def set_wpa3_per_band(self, network_id: Optional[str]=None, *, band_2_4_ghz: Optional[str]=None, band_5_ghz: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; values `WPA2` / `WPA2_WPA3` / `WPA3` |
| `set_mlo_mode` | `async def set_mlo_mode(self, mode: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; `disabled` / `single` / `multi` |
| `get_fast_transition` | `async def get_fast_transition(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `set_fast_transition` | `async def set_fast_transition(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class |
| `set_passpoint_enabled` | `async def set_passpoint_enabled(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `set_proxied_nodes` | `async def set_proxied_nodes(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |

> **Note**: `SecurityAPI.set_thread` and the `thread=` keyword on `configure_security` were
> removed in v8.0.0 — the API does not accept a `thread` field on the settings write. Thread is
> its own resource; see [Thread](#thread).

### DHCP & WAN

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `set_dhcp` | `async def set_dhcp(self, network_id: Optional[str]=None, *, mode: Optional[str]=None, custom: Optional[Mapping[str, Any]]=None, custom_v2: Optional[Mapping[str, Any]]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; `mode` is `automatic` / `manual` |
| `set_connection_mode` | `async def set_connection_mode(self, mode: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; `BRIDGE` / `NAT` |
| `set_nat_port_randomization` | `async def set_nat_port_randomization(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class |
| `get_multistaticip` | `async def get_multistaticip(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read on `2.3`; `EeroNotFoundException` without the feature |
| `set_multistaticip` | `async def set_multistaticip(self, config: Mapping[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; `2.3`; forwarded unchanged |
| `set_secondary_wan_config` | `async def set_secondary_wan_config(self, config: Mapping[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; `2.3`; forwarded unchanged |
| `get_subnets_config` | `async def get_subnets_config(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `set_subnets_config` | `async def set_subnets_config(self, config: Mapping[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; forwarded unchanged |
| `delete_subnet` | `async def delete_subnet(self, subnet_type: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class |
| `set_power_saving` | `async def set_power_saving(self, network_id: Optional[str]=None, *, enable: Optional[bool]=None, power_saving_schedule_enabled: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Settings-class; at least one field |
| `get_power_saving_schedules` | `async def get_power_saving_schedules(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `create_power_saving_schedule` | `async def create_power_saving_schedule(self, network_id: Optional[str]=None, *, name: str, days: Any, start_time: str, end_time: str, enabled: bool=True) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `update_power_saving_schedule` | `async def update_power_saving_schedule(self, schedule_id: str, network_id: Optional[str]=None, *, name: Optional[str]=None, days: Optional[Any]=None, start_time: Optional[str]=None, end_time: Optional[str]=None, enabled: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `delete_power_saving_schedule` | `async def delete_power_saving_schedule(self, schedule_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |

### Backup

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_backup_internet` | `async def get_backup_internet(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Read |
| `set_backup_internet` | `async def set_backup_internet(self, enabled: bool, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `get_cellular_backup_usage` | `async def get_cellular_backup_usage(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Read |
| `get_cellular_backup_events` | `async def get_cellular_backup_events(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Read |
| `list_backup_access_points` | `async def list_backup_access_points(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `add_backup_access_point` | `async def add_backup_access_point(self, network_id: Optional[str]=None, *, ssid: str, password: str, uuid: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `update_backup_access_point` | `async def update_backup_access_point(self, backup_network_id: str, network_id: Optional[str]=None, *, ssid: Optional[str]=None, password: Optional[str]=None, enabled: Optional[bool]=None, uuid: Optional[str]=None, connectivity: Optional[Mapping[str, Any]]=None, created: Optional[str]=None, last_updated_at: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `delete_backup_access_point` | `async def delete_backup_access_point(self, backup_network_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `rearrange_backup_access_points` | `async def rearrange_backup_access_points(self, order: List[str], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `discover_backup_ssids` | `async def discover_backup_ssids(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `start_backup_ssid_discovery` | `async def start_backup_ssid_discovery(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; POST `""` |
| `backup_connectivity_check` | `async def backup_connectivity_check(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; POST `""` |

> **Note**: The four former `*backup_network` methods were removed in v8.0.0 in favour of the
> backup-internet resource above. See [Deprecations](Deprecations#800--removals).

### Reservations

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_reservations` | `async def get_reservations(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `create_reservation` | `async def create_reservation(self, reservation_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Body passed through; declared fields `description`, `ip`, `mac`, `public_static_ip` |
| `update_reservation` | `async def update_reservation(self, reservation_id: str, reservation_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete_reservation` | `async def delete_reservation(self, reservation_id: str, network_id: Optional[str]=None, *, delete_forwards: Optional[bool]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `delete_forwards` is sent as a query parameter when supplied |

### Forwards

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_forwards` | `async def get_forwards(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `create_forward` | `async def create_forward(self, forward_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Body passed through; declared fields `client_port`, `description`, `enabled`, `gateway_port`, `ip`, `protocol` |
| `update_forward` | `async def update_forward(self, forward_id: str, forward_data: Dict[str, Any], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |
| `delete_forward` | `async def delete_forward(self, forward_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | |

### Members & Invites

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_members` | `async def get_members(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_invites` | `async def get_invites(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified read — access denied on some accounts |
| `create_invite` | `async def create_invite(self, *, role: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; `owner` / `admin` |
| `update_invite` | `async def update_invite(self, invite_id: str, *, invite_nickname: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `delete_invite` | `async def delete_invite(self, invite_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `respond_to_invite` | `async def respond_to_invite(self, *, accept: bool, invite_id: Optional[str]=None, invite_code: Optional[str]=None, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; exactly one of `invite_id` / `invite_code` |
| `cancel_pending_admin` | `async def cancel_pending_admin(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; POST `""` |
| `promote_member` | `async def promote_member(self, member_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |
| `remove_admin` | `async def remove_admin(self, user_id: str, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write |

### Notifications

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_notification_settings` | `async def get_notification_settings(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `set_notification_settings` | `async def set_notification_settings(self, settings: Mapping[str, bool], network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; sent as-is |
| `has_unread_notifications` | `async def has_unread_notifications(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `mark_notifications_read` | `async def mark_notifications_read(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Unverified write; POST `""` |
| `get_notification_history` | `async def get_notification_history(self, network_id: Optional[str]=None, *, timestamp: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |

### Events & Insights

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_app_events` | `async def get_app_events(self, network_id: Optional[str]=None, *, page_size: Optional[int]=None, timestamp: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_network_scan` | `async def get_network_scan(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_channel_utilization` | `async def get_channel_utilization(self, network_id: Optional[str]=None, *, start: str, end: str, busy_threshold: Optional[int]=None, eero_id: Optional[int]=None, band: Optional[str]=None, granularity: Optional[int]=None, gap_data_placeholder: Optional[int]=None) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read with `start`/`end`; `band` from `CHANNEL_UTILIZATION_BANDS`; `granularity` is an integer |
| `get_insights` | `async def get_insights(self, network_id: Optional[str]=None, *, start: str, end: str, insight_type: str, cadence: str='daily') -> Dict[str, Any]` | `Dict[str, Any]` | `start`/`end`/`insight_type` are keyword-only |
| `get_devices_insights` | `async def get_devices_insights(self, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, insight_type: str) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_device_insights` | `async def get_device_insights(self, device_id: str, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, insight_type: str) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_profiles_insights` | `async def get_profiles_insights(self, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, insight_type: str) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_profile_insights` | `async def get_profile_insights(self, profile_id: str, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, insight_type: str) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |
| `get_profile_devices_insights` | `async def get_profile_devices_insights(self, profile_id: str, network_id: Optional[str]=None, *, start: str, end: str, cadence: str, insight_type: str) -> Dict[str, Any]` | `Dict[str, Any]` | Verified read |

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

> **Note**: `get_burst_reporters` was removed in v8.0.0 — the endpoint returns 404; the resource
> is POST-only. `client._api.burst_reporters.create_burst_reporter(...)` remains available.

### Blacklist

| Method | Signature | Returns | Notes |
|--------|-----------|---------|-------|
| `get_blacklist` | `async def get_blacklist(self, network_id: Optional[str]=None) -> Dict[str, Any]` | `Dict[str, Any]` | `block_device` / `unblock_device` (under [Devices](#devices)) are the facade's add/remove |

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
session/cookie/keyring plumbing. Every method below returns `Dict[str, Any]` unless stated.
`parent` is always `Optional[Mapping[str, Any]]`, keyword-only, default `None`.

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

### Link resolution (`src/eero/api/links.py`)

The one place URLs are built. No I/O; never mutates an envelope. All five are re-exported from
the package root.

| Symbol | Signature | Notes |
|--------|-----------|-------|
| `join_api_path` | `join_api_path(path: str) -> str` | `API_HOST` + host-relative path; version prefix preserved; `EeroValidationException` on empty/non-string |
| `resolve_link` | `resolve_link(parent: Envelope, name: str) -> Optional[str]` | `parent["resources"][name]` (full envelope or `data` object) joined onto the host; `None` when absent |
| `self_url` | `self_url(parent: Envelope) -> Optional[str]` | The envelope's own `url` joined onto the host |
| `resource_url` | `resource_url(id_or_url: str, template: str, *, version: str=API_VERSION_DEFAULT) -> str` | Bare ID → `template` (exactly one `{id}`) on `version`; path → joined, suffix after `{id}` appended; absolute URL → validated (API host + scheme only), suffix appended |
| `sub_resource_url` | `sub_resource_url(id_or_url: str, template: str, *, link: str, parent: Optional[Envelope]=None, version: str=API_VERSION_DEFAULT) -> str` | `resolve_link(parent, link)` if it yields a URL, else `resource_url(...)` |
| `Envelope` | `Dict[str, Any]` | Type alias |

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

`parent` = the network envelope, except the guest-password methods, which take the guest-network envelope (`get_guest_network`'s response).

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_networks` | `async def get_networks(self)` | GET `networks` | read |
| `get_network` | `async def get_network(self, network_id: str, *, parent=None)` | GET the network's own URL | read |
| `get_premium_status` | `async def get_premium_status(self, network_id: str, *, parent=None)` | GET the network's own URL | read |
| `reboot_network` | `async def reboot_network(self, network_id: str, *, parent=None)` | POST `""` to the `reboot` link | write; no `EeroClient` wrapper |
| `run_speed_test` | `async def run_speed_test(self, network_id: str, *, parent=None)` | POST `""` to the `speedtest` link | write |
| `get_speed_tests` | `async def get_speed_tests(self, network_id: str, *, limit: Optional[int]=None, start_time: Optional[str]=None, end_time: Optional[str]=None, parent=None)` | GET the `speedtest` link, query `limit` / `startTime` / `endTime` | read |
| `set_network_name` | `async def set_network_name(self, network_id: str, name: str, *, parent=None)` | PUT form `name=` to the `settings` link | disconnects; unverified |
| `set_network_password` | `async def set_network_password(self, network_id: str, password: str, *, parent=None)` | PUT form `password=` to the `password` link | disconnects; unverified |
| `clear_network_password` | `async def clear_network_password(self, network_id: str, *, parent=None)` | DELETE the `password` link | disconnects; unverified |
| `get_guest_network` | `async def get_guest_network(self, network_id: str, *, parent=None)` | GET the `guestnetwork` link | read |
| `set_guest_network` | `async def set_guest_network(self, network_id: str, *, enabled: bool, name: Optional[str]=None, parent=None)` | PUT form `enabled=` (+ `name=`) to the `guestnetwork` link | disconnects guests; unverified |
| `set_guest_password` | `async def set_guest_password(self, network_id: str, password: str, *, parent=None)` | PUT form `password=` to the guest network's `password` link | disconnects guests; unverified |
| `clear_guest_password` | `async def clear_guest_password(self, network_id: str, *, parent=None)` | DELETE the guest network's `password` link | disconnects guests; unverified |

</details>

<details>
<summary>📦 EerosAPI (<code>client._api.eeros</code>)</summary>

`parent` = the eero's own envelope (for `get_eeros`, the network envelope). `network_id` is accepted for compatibility and unused for URL resolution where noted.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_eeros` | `async def get_eeros(self, network_id: str, *, parent=None)` | GET the network's `eeros` link | read |
| `get_eero` | `async def get_eero(self, network_id: str, eero_id: str, *, parent=None)` | GET the eero's own URL (`eeros/{id}`) | read |
| `reboot_eero` | `async def reboot_eero(self, network_id: str, eero_id: str, *, parent=None)` | POST `""` to the `reboot` link | write |
| `get_led_status` | `async def get_led_status(self, network_id: str, eero_id: str, *, parent=None)` | GET the eero's own URL | read |
| `set_led` | `async def set_led(self, network_id: str, eero_id: str, enabled: bool, *, parent=None)` | PUT form `led_on=true|false` to the `led_action` link (`eeros/{id}/led`) | verified write (2026-09-20, light off and on, no reboot); the previous JSON write was verified to change nothing |
| `set_led_brightness` | `async def set_led_brightness(self, network_id: str, eero_id: str, brightness: int, *, parent=None)` | PUT form `led_brightness=<0-100>` to the `led_action` link | unverified write |
| `set_location` | `async def set_location(self, network_id: str, eero_id: str, location: str, *, parent=None)` | PUT form `location=` to the eero's own URL | unverified write |
| `get_nightlight` | `async def get_nightlight(self, network_id: str, eero_id: str, *, parent=None)` | GET `data.nightlight.url` (read from `parent`, else one eero read to discover it) | read; `EeroFeatureUnavailableException` without a nightlight |
| `set_nightlight` | `async def set_nightlight(self, network_id: str, eero_id: str, *, enabled: Optional[bool]=None, brightness_percentage: Optional[int]=None, schedule: Optional[Mapping[str, Any]]=None, parent=None)` | PUT JSON of the supplied fields to the nightlight URL | unverified write |
| `set_nightlight_brightness` | `async def set_nightlight_brightness(self, network_id: str, eero_id: str, brightness_percentage: int, *, parent=None)` | as `set_nightlight` | unverified write |
| `set_nightlight_schedule` | `async def set_nightlight_schedule(self, network_id: str, eero_id: str, schedule: Mapping[str, Any], *, parent=None)` | as `set_nightlight` | unverified write |
| `get_connections` | `async def get_connections(self, network_id: str, eero_id: str, *, parent=None)` | GET the `connections` link | read |
| `node_action` | `async def node_action(self, eero_id: str, action: str, *, parent=None)` | POST JSON `{"action": ...}` to the `action` link | unverified write; `POWER_CYCLE_ALL_PORTS` / `POWER_CYCLE_ALL_PORTS_AND_REBOOT` |
| `port_action` | `async def port_action(self, eero_id: str, interface_number: str, action: str)` | POST JSON `{"action": ...}` to `eeros/{id}/ports/{interface_number}/action` | unverified write |
| `led_cycle` | `async def led_cycle(self, eero_serial: str, *, colors: Any, duration: str, time_per_color: str)` | POST form `colors[]`, `duration`, `time_per_color` to `eeros/{id}/led_cycle` | unverified write |
| `nightlight_override` | `async def nightlight_override(self, eero_id: str, *, brightness_percentage: int)` | POST form `brightness_percentage=` to `eeros/{id}/nightlight/override` | unverified write |
| `get_eero_support` | `async def get_eero_support(self, eero_serial: str)` | GET `eeros/{id}/support` | read; `EeroNotFoundException` on some nodes |

</details>

<details>
<summary>📦 DevicesAPI (<code>client._api.devices</code>)</summary>

The device parameter is named `mac` on every method. `parent` = the network envelope for `get_devices`; the device's own envelope for `get_device` / `update_device_via_link`.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_devices` | `async def get_devices(self, network: str, *, thread: Optional[bool]=None, proxied_node: Optional[bool]=None, parent=None)` | GET the `devices` link, query `thread` / `proxied_node` when supplied | read |
| `get_device` | `async def get_device(self, network: str, mac: str, *, parent=None)` | GET the device's own URL (`networks/{network}/devices/{mac}`) | read |
| `set_device_nickname` | `async def set_device_nickname(self, network_id: str, mac: str, nickname: str)` | PUT JSON to `networks/{id}/devices/{mac}` on **2.3** | **verified** write |
| `pause_device` | `async def pause_device(self, network_id: str, mac: str, paused: bool)` | PUT JSON to `networks/{id}/devices/{mac}` on **2.3** | **verified** write |
| `update_device_via_link` | `async def update_device_via_link(self, network: str, mac: str, *, nickname: Optional[str]=None, paused: Optional[bool]=None, profile: Optional[str]=None, parent=None)` | PUT JSON of the supplied fields to the device's own URL on 2.2 | unverified write |
| `set_device_type` | `async def set_device_type(self, network: str, mac: str, device_type: str)` | PUT JSON `{"device_type": ...}` to the device URL | unverified write |
| `get_device_labels` | `async def get_device_labels(self, network: str, mac: str)` | GET `networks/{id}/devices/{mac}/labels` | read |
| `set_device_labels` | `async def set_device_labels(self, network: str, mac: str, *, make_label: Optional[str]=None, model_label: Optional[str]=None, version_label: Optional[str]=None, type_label: Optional[str]=None)` | PUT `.../labels` with the labels as query parameters | unverified write |
| `block_device` | `async def block_device(self, network: str, mac: str)` | delegates to `BlacklistAPI.add_to_blacklist` | unverified (form) |
| `unblock_device` | `async def unblock_device(self, network: str, mac: str)` | delegates to `BlacklistAPI.remove_from_blacklist` | verified |

</details>

<details>
<summary>📦 ProfilesAPI (<code>client._api.profiles</code>)</summary>

`parent` = the network envelope for `get_profiles` / `create_profile`; the profile's own envelope elsewhere. A profile has exactly `devices`, `name`, `paused`, `url`.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_profiles` | `async def get_profiles(self, network: str, *, parent=None)` | GET the `profiles` link | read |
| `get_profile` | `async def get_profile(self, network: str, profile: str, *, parent=None)` | GET the profile's own URL | read |
| `pause_profile` | `async def pause_profile(self, network: str, profile: str, paused: bool, *, parent=None)` | PUT JSON to the profile's own URL | write |
| `get_profile_devices` | `async def get_profile_devices(self, network: str, profile: str, *, parent=None)` | GET the profile's own URL | read |
| `set_profile_devices` | `async def set_profile_devices(self, network: str, profile: str, device_urls: List[str], *, parent=None)` | PUT JSON `{"devices": [...]}` | write |
| `create_profile` | `async def create_profile(self, network: str, name: str, *, devices: Optional[List[str]]=None, paused: Optional[bool]=None, parent=None)` | POST JSON (`name`, `devices` as `[{"url": ...}]`, `paused`) to the `profiles` link | write |
| `rename_profile` | `async def rename_profile(self, network: str, profile: str, name: str, *, parent=None)` | PUT JSON to the profile's own URL | write |
| `delete_profile` | `async def delete_profile(self, network: str, profile: str)` | DELETE the profile's own URL | write |

> The former profile content-filter, block-list, and blocked-applications writes were removed
> in v8.0.0 — see `DnsPoliciesAPI` below and [Deprecations](Deprecations#800--removals).

</details>

<details>
<summary>📦 ScheduleAPI (<code>client._api.schedule</code>)</summary>

Scheduled pauses live at `networks/{id}/profiles/{profile}/schedules` (the profile's `schedules` link when `parent` is the profile envelope). Every write is unverified.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_schedules` | `async def get_schedules(self, network: str, profile: str, *, parent=None)` | GET the schedules collection | read |
| `create_schedule` | `async def create_schedule(self, network: str, profile: str, *, name: str, days: List[str], start: str, end: str, enabled: bool=True, parent=None)` | POST JSON to the collection | unverified write |
| `update_schedule` | `async def update_schedule(self, schedule: Any, *, name: Optional[str]=None, days: Optional[List[str]]=None, start: Optional[str]=None, end: Optional[str]=None, enabled: Optional[bool]=None)` | PUT JSON of the supplied fields to the pause's own URL (`schedule` is a path/URL or envelope) | unverified write |
| `delete_schedule` | `async def delete_schedule(self, schedule: Any)` | DELETE the pause's own URL | unverified write |
| `clear_profile_schedule` | `async def clear_profile_schedule(self, network: str, profile: str, *, parent=None) -> List[Dict[str, Any]]` | one GET + one DELETE per pause | unverified write; never retried |
| `enable_bedtime` | `async def enable_bedtime(self, network: str, profile: str, start_time: str, end_time: str, days: Optional[List[str]]=None, *, parent=None)` | one `create_schedule` | unverified write |
| `set_weekday_bedtime` | `async def set_weekday_bedtime(self, network: str, profile: str, start_time: str, end_time: str, *, parent=None)` | one `create_schedule` (Mon–Fri) | unverified write; no `EeroClient` wrapper |
| `set_weekend_bedtime` | `async def set_weekend_bedtime(self, network: str, profile: str, start_time: str, end_time: str, *, parent=None)` | one `create_schedule` (Sat–Sun) | unverified write; no `EeroClient` wrapper |

</details>

<details>
<summary>📦 DnsAPI (<code>client._api.dns</code>)</summary>

`parent` = the network envelope (its `settings` link). Every write reboots the mesh — see the DNS warning above.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_dns_settings` | `async def get_dns_settings(self, network_id: str)` | GET `networks/{id}` | read |
| `set_dns_caching` | `async def set_dns_caching(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON to the `settings` link | verified write; reboots |
| `set_custom_dns` | `async def set_custom_dns(self, network_id: str, dns_servers: List[str], *, parent=None)` | PUT JSON, split by family | verified write; reboots |
| `set_custom_dns_ipv4` | `async def set_custom_dns_ipv4(self, network_id: str, dns_servers: List[str], *, parent=None)` | PUT JSON `dns.custom.ips` | verified write; reboots |
| `set_custom_dns_ipv6` | `async def set_custom_dns_ipv6(self, network_id: str, dns_servers: List[str], *, parent=None)` | PUT JSON `ipv6.name_servers.custom` | verified write; reboots |
| `clear_custom_dns` | `async def clear_custom_dns(self, network_id: str, family: Optional[str]=None, *, parent=None)` | PUT JSON mode `automatic` | verified write; reboots |
| `set_dns_mode` | `async def set_dns_mode(self, network_id: str, mode: str, custom_servers: Optional[List[str]]=None, *, parent=None)` | PUT JSON | verified write; reboots |

</details>

<details>
<summary>📦 DnsPoliciesAPI (<code>client._api.dns_policies</code>)</summary>

Premium feature. `parent` = the network envelope. Removal is `is_delete=True` on the same PUT; there is no DELETE verb.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_advanced_content_filter` | `async def get_advanced_content_filter(self, network_id: str, *, parent=None)` | GET the `advanced_content_filter` link (`networks/{id}/dns_policies/advanced_content_filter`) | verified read |
| `allow_domain` | `async def allow_domain(self, network_id: str, domain: str, *, add_cname: Optional[bool]=None, reason_to_allow: Optional[int]=None, is_delete: Optional[bool]=None, keep_profiles: Optional[List[str]]=None, parent=None)` | PUT JSON to `.../dns_policies/network/allowed` | unverified write |
| `allow_cnames` | `async def allow_cnames(self, network_id: str, domains: List[str], *, parent=None)` | PUT JSON `{"domains": [...]}` to `.../network/allowed/cnames` | unverified write |
| `block_domain` | `async def block_domain(self, network_id: str, domain: str, *, is_delete: Optional[bool]=None, keep_profiles: Optional[List[str]]=None, parent=None)` | PUT JSON to `.../network/blocked` | unverified write |
| `allow_domain_for_profiles` | `async def allow_domain_for_profiles(self, network_id: str, domain: str, *, profiles: List[str], override: Optional[bool]=None, add_cname: Optional[bool]=None, reason_to_allow: Optional[int]=None, is_delete: Optional[bool]=None, parent=None)` | PUT JSON to `.../profiles/allowed` | unverified write |
| `allow_cnames_for_profiles` | `async def allow_cnames_for_profiles(self, network_id: str, domains: List[str], *, profiles: List[str], parent=None)` | PUT JSON `{"domains", "profiles"}` to `.../profiles/allowed/cnames` | unverified write |
| `block_domain_for_profiles` | `async def block_domain_for_profiles(self, network_id: str, domain: str, *, profiles: List[str], is_delete: Optional[bool]=None, override: Optional[bool]=None, parent=None)` | PUT JSON to `.../profiles/blocked` | unverified write |
| `get_profile_applications` | `async def get_profile_applications(self, network_id: str, profile_id: str)` | GET `.../dns_policies/profiles/{profile}/applications` | verified read |
| `set_profile_blocked_applications` | `async def set_profile_blocked_applications(self, network_id: str, profile_id: str, applications: List[str])` | PUT JSON `{"applications": [...]}` to `.../applications/blocked` | unverified write |

Not exposed: network/profile DNS-policy settings and ad-block settings — no envelope field carries their URL.

</details>

<details>
<summary>📦 SqmAPI (<code>client._api.sqm</code>)</summary>

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_sqm_settings` | `async def get_sqm_settings(self, network_id: str, *, parent=None)` | GET the network's own URL | read |
| `set_sqm` | `async def set_sqm(self, network_id: str, enabled: bool, *, parent=None)` | PUT to the `settings` link, no body, query `sqm=true|false` | settings-class |

</details>

<details>
<summary>📦 SecurityAPI (<code>client._api.security</code>)</summary>

`parent` = the network envelope.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_security_settings` | `async def get_security_settings(self, network_id: str, *, parent=None)` | GET the network's own URL | read |
| `set_wpa3` | `async def set_wpa3(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON to the `settings` link | write; settings link |
| `set_band_steering` | `async def set_band_steering(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON to the `settings` link | write; settings link |
| `set_upnp` | `async def set_upnp(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON to the `settings` link | write; settings link |
| `set_ipv6` | `async def set_ipv6(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON to the `settings` link | write; settings link |
| `configure_security` | `async def configure_security(self, network_id: str, wpa3: Optional[bool]=None, band_steering: Optional[bool]=None, upnp: Optional[bool]=None, ipv6: Optional[bool]=None, *, parent=None)` | PUT JSON to the `settings` link | write; settings link |
| `set_mlo_mode` | `async def set_mlo_mode(self, network_id: str, mode: str, *, parent=None)` | PUT JSON `{"mlo_mode": ...}` to the `mlo_mode` link | settings-class |
| `get_fast_transition` | `async def get_fast_transition(self, network_id: str, *, parent=None)` | GET the `fast_transition` link | verified read |
| `set_fast_transition` | `async def set_fast_transition(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON `{"fast_transition": bool}` | unverified write |
| `set_passpoint_enabled` | `async def set_passpoint_enabled(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON `{"enabled": bool}` to `networks/{id}/passpoint/enabled` (`passpoint` link) | unverified write |
| `set_proxied_nodes` | `async def set_proxied_nodes(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON `{"enabled": bool}` to the `proxied_nodes` link | unverified write |

</details>

<details>
<summary>📦 Wpa3API (<code>client._api.wpa3</code>)</summary>

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_wpa3_per_band` | `async def get_wpa3_per_band(self, network_id: str, *, parent=None)` | GET the `wpa3_per_band` link | verified read |
| `set_wpa3_per_band` | `async def set_wpa3_per_band(self, network_id: str, *, band_2_4_ghz: Optional[str]=None, band_5_ghz: Optional[str]=None, parent=None)` | PUT JSON of the supplied bands; values `WPA2` / `WPA2_WPA3` / `WPA3` | unverified write; devices may need to reconnect |

</details>

<details>
<summary>📦 DhcpAPI (<code>client._api.dhcp</code>)</summary>

Writes go to the network's `settings` link — the same endpoint as DNS — so they are settings-class.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `set_dhcp` | `async def set_dhcp(self, network_id: str, *, mode: Optional[str]=None, custom: Optional[Mapping[str, Any]]=None, custom_v2: Optional[Mapping[str, Any]]=None, parent=None)` | PUT JSON `{"dhcp": {...}}`; `custom` keys `start_ip` / `end_ip` / `subnet_ip` / `subnet_mask`; `custom_v2` keys `main` / `guest` / `subnetA` / `subnetB` / `supernet` | settings-class |
| `set_connection_mode` | `async def set_connection_mode(self, network_id: str, mode: str, *, parent=None)` | PUT JSON `{"connection": {"mode": "BRIDGE"|"NAT"}}` | settings-class |
| `set_nat_port_randomization` | `async def set_nat_port_randomization(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON `{"nat_port_randomization": bool}` | settings-class |
| `set_pppoe` | `async def set_pppoe(self, eero_serial_or_id: str, *, username: str, password: str)` | POST JSON `{"pppoe": {...}}` to `eeros/{id}/pppoe`; response carries the encrypted blob | unverified write |

</details>

<details>
<summary>📦 ThreadAPI (<code>client._api.thread</code>)</summary>

The read uses the `thread` link; the writes target the literal `networks/{id}/thread` path (`parent` unused).

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_thread` | `async def get_thread(self, network_id: str, *, parent=None)` | GET the `thread` link | read |
| `set_thread_enabled` | `async def set_thread_enabled(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON `{"enabled": bool}` | unverified write |
| `update_thread` | `async def update_thread(self, network_id: str, *, thread_enable: Optional[bool]=None, enable_credential_syncing: Optional[bool]=None, parent=None)` | PUT JSON of the supplied keys | unverified write |
| `regenerate_thread_credentials` | `async def regenerate_thread_credentials(self, network_id: str, *, parent=None)` | POST `""` | unverified write |

</details>

<details>
<summary>📦 BackupAPI (<code>client._api.backup</code>)</summary>

Literal paths (not published links); `parent` unused.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_backup_internet` | `async def get_backup_internet(self, network_id: str, *, parent=None)` | GET `networks/{id}/backupinternet` | read |
| `set_backup_internet` | `async def set_backup_internet(self, network_id: str, enabled: bool, *, parent=None)` | PUT JSON `{"backup_internet_enabled": bool}` | unverified write |
| `get_cellular_backup_usage` | `async def get_cellular_backup_usage(self, network_id: str, *, parent=None)` | GET `networks/{id}/cellular_backup_usage` | read |
| `get_cellular_backup_events` | `async def get_cellular_backup_events(self, network_id: str, *, parent=None)` | GET `networks/{id}/cellular_backup_events` | read |

</details>

<details>
<summary>📦 BackupAccessPointsAPI (<code>client._api.backup_access_points</code>)</summary>

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `list` | `async def list(self, network_id: str, *, parent=None)` | GET the `backup_access_points` link | verified read |
| `add` | `async def add(self, network_id: str, *, ssid: str, password: str, uuid: Optional[str]=None)` | POST JSON to `networks/{id}/backup_access_points` | unverified write |
| `update` | `async def update(self, network_id: str, backup_network_id: str, *, ssid=None, password=None, enabled=None, uuid=None, connectivity=None, created=None, last_updated_at=None)` | PUT JSON of the supplied fields to `.../backup_access_points/{backup_network_id}` | unverified write |
| `delete_backup_access_point` | `async def delete_backup_access_point(self, network_id: str, backup_network_id: str)` | DELETE `.../backup_access_points/{backup_network_id}` | unverified write |
| `rearrange` | `async def rearrange(self, network_id: str, order: List[str])` | POST JSON `{"rearranged_ids": [...]}` to `.../rearrange` | unverified write |
| `discover_ssids` | `async def discover_ssids(self, network_id: str)` | GET `.../ssid_discovery` | verified read |
| `start_ssid_discovery` | `async def start_ssid_discovery(self, network_id: str)` | POST `""` to `.../ssid_discovery` | unverified write |
| `connectivity_check` | `async def connectivity_check(self, network_id: str)` | POST `""` to `.../connectivity_check` | unverified write |

</details>

<details>
<summary>📦 ReservationsAPI (<code>client._api.reservations</code>)</summary>

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_reservations` | `async def get_reservations(self, network: str, *, parent=None)` | GET the `reservations` link | read |
| `create_reservation` | `async def create_reservation(self, network: str, reservation_data: Dict[str, Any], *, parent=None)` | POST JSON (passed through) to the `reservations` link | write |
| `update_reservation` | `async def update_reservation(self, reservation: Any, data: Dict[str, Any], *, network: Optional[str]=None)` | PUT JSON to the reservation's own URL; `reservation` is a bare ID (needs `network=`), path/URL, or envelope | write |
| `delete_reservation` | `async def delete_reservation(self, network: str, reservation: str, *, delete_forwards: Optional[bool]=None)` | DELETE `networks/{network}/reservations/{id}`, query `delete_forwards` when supplied | write |

</details>

<details>
<summary>📦 ForwardsAPI (<code>client._api.forwards</code>)</summary>

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_forwards` | `async def get_forwards(self, network: str, *, parent=None)` | GET the `forwards` link | read |
| `create_forward` | `async def create_forward(self, network: str, forward_data: Dict[str, Any], *, parent=None)` | POST JSON (passed through) to the `forwards` link | write |
| `update_forward` | `async def update_forward(self, forward: Any, data: Dict[str, Any], *, network: Optional[str]=None)` | PUT JSON to the forward's own URL; `forward` is a bare ID (needs `network=`), path/URL, or envelope | write |
| `delete_forward` | `async def delete_forward(self, network: str, forward: str)` | DELETE `networks/{network}/forwards/{id}` | write |

</details>

<details>
<summary>📦 BlacklistAPI (<code>client._api.blacklist</code>)</summary>

Reached through the network's `device_blacklist` link when `parent` is supplied.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_blacklist` | `async def get_blacklist(self, network: str, *, parent=None)` | GET `networks/{id}/blacklist` | read |
| `add_to_blacklist` | `async def add_to_blacklist(self, network: str, mac: str, *, parent=None)` | POST form `mac=` | unverified write (a JSON body was verified in the past) |
| `remove_from_blacklist` | `async def remove_from_blacklist(self, network: str, mac_or_device_id: str, *, parent=None)` | DELETE `.../blacklist/{mac}` (colon-stripped `device_id` also accepted) | verified write |

</details>

<details>
<summary>📦 InsightsAPI (<code>client._api.insights</code>)</summary>

All reads take `start`, `end`, `cadence`, `insight_type` as query parameters. `cadence` is validated locally (`daily` / `hourly`; `get_insights` also accepts `weekly`).

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_insights` | `async def get_insights(self, network_id: str, *, start: str, end: str, insight_type: str, cadence: str='daily')` | GET `networks/{id}/insights` | read |
| `get_devices_insights` | `async def get_devices_insights(self, network: str, *, start: str, end: str, cadence: str, insight_type: str, parent=None)` | GET the `insights_devices` link | verified read |
| `get_device_insights` | `async def get_device_insights(self, network: str, mac: str, *, start: str, end: str, cadence: str, insight_type: str)` | GET `networks/{id}/insights/devices/{mac}` | verified read |
| `get_profiles_insights` | `async def get_profiles_insights(self, network: str, *, start: str, end: str, cadence: str, insight_type: str, parent=None)` | GET the `insights_profiles` link | verified read |
| `get_profile_insights` | `async def get_profile_insights(self, network: str, profile: str, *, start: str, end: str, cadence: str, insight_type: str)` | GET `.../insights/profiles/{profile}` | verified read |
| `get_profile_devices_insights` | `async def get_profile_devices_insights(self, network: str, profile: str, *, start: str, end: str, cadence: str, insight_type: str)` | GET `.../insights/profiles/{profile}/devices` | verified read |

</details>

<details>
<summary>📦 EntitlementsAPI (<code>client._api.entitlements</code>)</summary>

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_features` | `async def get_features(self, network_id: str)` | GET `entitlements/networks/{id}/features` | verified read |
| `get_upsell_features` | `async def get_upsell_features(self, network_id: str)` | GET `entitlements/networks/{id}/upsell_features` | verified read |
| `get_model_capabilities` | `async def get_model_capabilities(self, network_id: str)` | GET `eero_models/capabilities`, query `networkId=<bare id>` | read |
| `get_premium_customer` | `async def get_premium_customer(self)` | GET `premium/customer` | read |

</details>

<details>
<summary>📦 EventsAPI (<code>client._api.events</code>)</summary>

Module export: `CHANNEL_UTILIZATION_BANDS = ("band_2_4GHz", "band_5GHz_low", "band_5GHz_high", "band_5GHz_full", "band_6GHz")`.

| Method | Signature | Request | Status |
|--------|-----------|---------|--------|
| `get_app_events` | `async def get_app_events(self, network_id: str, *, page_size: Optional[int]=None, timestamp: Optional[str]=None, parent=None)` | GET `networks/{id}/app_events`, query `page_size` / `timestamp` | verified read |
| `get_network_scan` | `async def get_network_scan(self, network_id: str, *, parent=None)` | GET `networks/{id}/network_scan` | verified read |
| `get_channel_utilization` | `async def get_channel_utilization(self, network_id: str, *, start: str, end: str, busy_threshold: Optional[int]=None, eero_id: Optional[int]=None, band: Optional[str]=None, granularity: Optional[int]=None, gap_data_placeholder: Optional[int]=None, parent=None)` | GET `networks/{id}/channel_utilization`, all as query parameters | verified read (with `start`/`end` only) |

</details>

<details>
<summary>📦 PermissionsAPI, NotificationsAPI, MembersAPI, AccountAPI</summary>

| Class | Method | Signature | Request | Status |
|-------|--------|-----------|---------|--------|
| `PermissionsAPI` | `get_permissions` | `async def get_permissions(self, network_id: str, *, parent=None)` | GET `networks/{id}/permissions` | verified read |
| `NotificationsAPI` | `get_settings` | `async def get_settings(self, network_id: str, *, parent=None)` | GET `networks/{id}/notifications` | verified read |
| `NotificationsAPI` | `set_settings` | `async def set_settings(self, network_id: str, settings: Mapping[str, bool], *, parent=None)` | PUT JSON (as supplied) | unverified write |
| `NotificationsAPI` | `has_unread` | `async def has_unread(self, network_id: str, *, parent=None)` | GET `.../notifications/has_unread` | verified read |
| `NotificationsAPI` | `mark_read` | `async def mark_read(self, network_id: str, *, parent=None)` | POST `""` to `.../notifications/mark_read` | unverified write |
| `NotificationsAPI` | `get_history` | `async def get_history(self, network_id: str, *, timestamp: Optional[str]=None, parent=None)` | GET `networks/{id}/notifications_history`, query `timestamp` | verified read |
| `NotificationsAPI` | `set_push_settings` | `async def set_push_settings(self, settings: Mapping[str, bool])` | PUT JSON to `account/push_settings` | unverified write |
| `MembersAPI` | `get_members` | `async def get_members(self, network_id: str, *, parent=None)` | GET the `members` link | verified read |
| `MembersAPI` | `get_invites` | `async def get_invites(self, network_id: str)` | GET `networks/{id}/invites` | unverified read |
| `MembersAPI` | `create_invite` | `async def create_invite(self, network_id: str, *, role: str)` | POST JSON `{"invite_role": "owner"|"admin"}` | unverified write |
| `MembersAPI` | `update_invite` | `async def update_invite(self, network_id: str, invite_id: str, *, invite_nickname: str)` | PUT JSON to `.../invites/{invite}` | unverified write |
| `MembersAPI` | `delete_invite` | `async def delete_invite(self, network_id: str, invite_id: str)` | DELETE `.../invites/{invite}` | unverified write |
| `MembersAPI` | `respond_to_invite` | `async def respond_to_invite(self, network_id: str, *, accept: bool, invite_id: Optional[str]=None, invite_code: Optional[str]=None)` | POST JSON to `.../invites/response` | unverified write |
| `MembersAPI` | `cancel_pending_admin` | `async def cancel_pending_admin(self, network_id: str)` | POST `""` to `.../invites/cancel_pending_admin` | unverified write |
| `MembersAPI` | `promote_member` | `async def promote_member(self, network_id: str, member_id: str)` | POST JSON `{"member_id": ...}` to `.../member_promotion` | unverified write |
| `MembersAPI` | `remove_admin` | `async def remove_admin(self, network_id: str, user_id: str)` | DELETE `.../admins/{user}` | unverified write |
| `MembersAPI` | `query_invite` | `async def query_invite(self, invite_code: str)` | POST JSON `{"invite_code": ...}` to `inviteQuery` | unverified |
| `AccountAPI` | `set_name` | `async def set_name(self, name: str)` | PUT form `name=` to `account/name` | unverified write |
| `AccountAPI` | `set_email` | `async def set_email(self, email: str)` | PUT form `email=` to `account/email` | unverified write |
| `AccountAPI` | `verify_email` | `async def verify_email(self, code: str)` | POST form `code=` to `account/email/verify` | unverified write |
| `AccountAPI` | `set_phone` | `async def set_phone(self, phone: str)` | PUT form `phone=` to `account/phone` | unverified write |
| `AccountAPI` | `verify_phone` | `async def verify_phone(self, code: str)` | POST form `code=` to `account/phone/verify` | unverified write |
| `AccountAPI` | `set_consents` | `async def set_consents(self, *, marketing_emails: bool)` | PUT form `marketing_emails=true|false` to `account/consents` | unverified write |
| `AccountAPI` | `get_sms_countries` | `async def get_sms_countries(self)` | GET `countries/sms` | read |

Account deletion is deliberately not exposed. Identifier values passed to `AccountAPI` and `query_invite` are never logged.

</details>

<details>
<summary>📦 PowerSavingAPI, DdnsAPI, SubnetsAPI, WanAPI</summary>

| Class | Method | Signature | Request | Status |
|-------|--------|-----------|---------|--------|
| `PowerSavingAPI` | `set_power_saving` | `async def set_power_saving(self, network_id: str, *, enable: Optional[bool]=None, power_saving_schedule_enabled: Optional[bool]=None, parent=None)` | PUT JSON of the supplied fields to the `power_saving` link | unverified write (settings-class on the facade) |
| `PowerSavingAPI` | `get_schedules` | `async def get_schedules(self, network_id: str, *, parent=None)` | GET `networks/{id}/power_saving/schedules` | verified read |
| `PowerSavingAPI` | `create_schedule` | `async def create_schedule(self, network_id: str, *, name: str, days: Any, start_time: str, end_time: str, enabled: bool=True)` | POST JSON to `.../power_saving/schedules` | unverified write |
| `PowerSavingAPI` | `update_schedule` | `async def update_schedule(self, network_id: str, schedule_id: str, *, name=None, days=None, start_time=None, end_time=None, enabled=None)` | PUT JSON of the supplied fields to `.../schedules/{schedule_id}` | unverified write |
| `PowerSavingAPI` | `delete_schedule` | `async def delete_schedule(self, network_id: str, schedule_id: str)` | DELETE `.../schedules/{schedule_id}` | unverified write |
| `DdnsAPI` | `enable` | `async def enable(self, network_id: str, *, parent=None)` | PUT, no body, to the `ddns_enable` link (`networks/{id}/ddns/enable`) | unverified write |
| `DdnsAPI` | `disable` | `async def disable(self, network_id: str, *, parent=None)` | PUT, no body, to the `ddns_disable` link | unverified write |
| `SubnetsAPI` | `get_config` | `async def get_config(self, network_id: str, *, parent=None)` | GET the `subnets_config` link | verified read |
| `SubnetsAPI` | `set_config` | `async def set_config(self, network_id: str, config: Mapping[str, Any])` | PUT JSON (forwarded unchanged) to `networks/{id}/subnets_config` | unverified write (settings-class on the facade) |
| `SubnetsAPI` | `delete_subnet` | `async def delete_subnet(self, network_id: str, subnet_type: str)` | DELETE `.../subnets_config/{subnet_type}` | unverified write (settings-class on the facade) |
| `SubnetsAPI` | `set_content_filters` | `async def set_content_filters(self, network_id: str, filters: Mapping[str, Any])` | PUT JSON to `.../subnets_config/dns_policies/content_filters` | unverified write |
| `SubnetsAPI` | `get_content_filters` | `async def get_content_filters(self, network_id: str, subnet_id: str)` | GET `.../subnets_config/{subnet_id}/dns_policies/content_filters` | verified read |
| `WanAPI` | `get_multistaticip` | `async def get_multistaticip(self, network_id: str, *, parent=None)` | GET the `multistaticip` link on **2.3** | verified read; `EeroNotFoundException` without the feature |
| `WanAPI` | `set_multistaticip` | `async def set_multistaticip(self, network_id: str, config: Mapping[str, Any])` | PUT JSON (forwarded unchanged) to `networks/{id}/multistaticip` on **2.3** | unverified write (settings-class on the facade) |
| `WanAPI` | `set_secondary_wan_config` | `async def set_secondary_wan_config(self, network_id: str, config: Mapping[str, Any])` | PUT JSON `{"devices": [{"mac", "secondary_wan_deny_access"}]}` to `.../devices/secondary_wan_config` on **2.3** | settings-class |
| `WanAPI` | `set_device_secondary_wan_access` | `async def set_device_secondary_wan_access(self, network_id: str, mac: str, *, deny: bool)` | PUT JSON `{"secondary_wan_deny_access": bool}` to `.../devices/{mac}` on **2.3** | settings-class |

</details>

<details>
<summary>📦 DiagnosticsAPI, RoutingAPI, SupportAPI, UpdatesAPI, TransferAPI, BurstReportersAPI, ACCompatAPI, OUICheckAPI</summary>

| Class | Method | Signature | Request | Status |
|-------|--------|-----------|---------|--------|
| `DiagnosticsAPI` | `get_diagnostics` | `async def get_diagnostics(self, network_id: str, *, parent=None)` | GET the `diagnostics` link | read |
| `DiagnosticsAPI` | `run_diagnostics` | `async def run_diagnostics(self, network_id: str, *, device: Optional[str]=None, symptom: Optional[str]=None, parent=None)` | POST JSON of the supplied keys (`{}` otherwise) to the `diagnostics` link | unverified body shape |
| `RoutingAPI` | `get_routing` | `async def get_routing(self, network: str, *, parent=None)` | GET the `routing` link (served on `2.3`; template fallback `2.2`) | read |
| `SupportAPI` | `get_support` | `async def get_support(self, network_id: str, *, parent=None)` | GET the `support` link | read |
| `SupportAPI` | `request_support` | `async def request_support(self, network_id: str, request_data: Dict[str, Any], *, parent=None)` | POST (forwarded unchanged) to the `support` link | write; no `EeroClient` wrapper |
| `UpdatesAPI` | `get_updates` | `async def get_updates(self, network_id: str, *, parent=None)` | GET the `updates` link | read |
| `UpdatesAPI` | `apply_update` | `async def apply_update(self, network_id: str, *, parent=None)` | POST `""` to the `updates` link | unverified write; reboots every node |
| `TransferAPI` | `get_transfer_stats` | `async def get_transfer_stats(self, network_id: str, device_id: Optional[str]=None, *, parent=None)` | GET the `transfer` link, or `networks/{id}/devices/{device_id}/transfer` | read |
| `BurstReportersAPI` | `create_burst_reporter` | `async def create_burst_reporter(self, network_id: str, reporter_data: Dict[str, Any], *, parent=None)` | POST to the `burst_reporters` link | write; no `EeroClient` wrapper |
| `ACCompatAPI` | `get_ac_compat` | `async def get_ac_compat(self, network_id: str, *, parent=None)` | GET the `ac_compat` link | read |
| `OUICheckAPI` | `get_ouicheck` | `async def get_ouicheck(self, network_id: str, *, serial: str, version: str, parent=None)` | GET `networks/{id}/ouicheck`, query `serial` / `version` (404 without them) | read |

</details>

<details>
<summary>📦 DataUsageAPI (<code>client._api.data_usage</code>)</summary>

Every read is a `GET` on `networks/{network_id}/data_usage…` taking query parameters only —
`start` and `end` (ISO 8601 timestamps), an optional IANA `timezone`, and `cadence` (`"daily"`
or `"hourly"`). Where `cadence` is typed `str` below it is required by the API; where it is
`Optional[str]` it is omitted from the request when `None`. An invalid `cadence` raises
`EeroValidationException` locally. `parent` = the network envelope (its own `url`). Every method
has an `EeroClient` wrapper (listed under [Stats & Usage](#stats--usage)).

| Method | Signature | Notes |
|--------|-----------|-------|
| `get_data_usage` | `async def get_data_usage(self, network_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None, parent=None)` | Network-level series |
| `get_breakdown` | `async def get_breakdown(self, network_id: str, *, start: str, end: str, cadence: Optional[str]=None, timezone: Optional[str]=None, parent=None)` | |
| `get_devices_usage` | `async def get_devices_usage(self, network_id: str, *, start: str, end: str, cadence: Optional[str]=None, timezone: Optional[str]=None, profile_id: Optional[str]=None, parent=None)` | `profile_id` scopes to one profile's devices |
| `get_device_usage` | `async def get_device_usage(self, network_id: str, device_mac: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None, parent=None)` | One device, addressed by MAC |
| `get_eeros_summary` | `async def get_eeros_summary(self, network_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None, parent=None)` | |
| `get_eero_usage` | `async def get_eero_usage(self, network_id: str, eero_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None, parent=None)` | |
| `get_profile_usage` | `async def get_profile_usage(self, network_id: str, profile_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None, parent=None)` | |
| `get_unprofiled_devices` | `async def get_unprofiled_devices(self, network_id: str, *, start: str, end: str, cadence: Optional[str]=None, timezone: Optional[str]=None, parent=None)` | |
| `get_unprofiled_summary` | `async def get_unprofiled_summary(self, network_id: str, *, start: str, end: str, cadence: str, timezone: Optional[str]=None, parent=None)` | |
| `get_report_settings` | `async def get_report_settings(self, network_id: str, *, parent=None)` | No query parameters |
| `set_report_settings` | `async def set_report_settings(self, network_id: str, *, cadence: str, notification_day: str, parent=None)` | `PUT` with a JSON body. **Unverified write** — read `get_report_settings` first, write only when the stored values differ, never retry |

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
| `EeroValidationException` | `EeroException` | `__init__(self, field: str, message: str, *, envelope=None, error_code=None)` for client-side validation (including a link on a foreign host or scheme, an invalid `band` / `cadence` / `action` / `mode`); `from_response(message, *, envelope=None, error_code=None)` (sets `field="request"`) for an API 400 carrying a `VALIDATION` catalogue string. **Not** an `EeroAPIException` |
| `EeroAPIException` | `EeroException` | `__init__(self, status_code: Optional[int], message: str, *, envelope=None, error_code=None)`; `str(err)` is `API error <status>: <catalogue string or "unrecognised error string">`; `is_auth_error()` → `status_code == 401` (never produced by the transport, which raises `EeroAuthenticationException` for 401). Raised for 3xx, oversized/invalid bodies, every `DOMAIN` string, and any status not claimed by a subclass |
| `EeroAccessDeniedException` | `EeroAPIException` | HTTP 403 with `error.access.denied`; not an auth error |
| `EeroClientBlockedException` | `EeroAPIException` | `error.app.version.blocked` on any status |
| `EeroNotFoundException` | `EeroAPIException` | Every HTTP 404. `__init__(self, resource_type: str, resource_id: str, *, envelope=None, error_code=None)` for direct construction; `from_response(message, *, status_code: int=404, envelope=None, error_code=None)` (both resource attributes `None`) is what the transport uses |
| `EeroPremiumRequiredException` | `EeroAPIException` | A `PREMIUM` string on any status. `__init__(self, feature: str='This feature', *, envelope=None, error_code=None)`; `from_response(message, *, status_code: Optional[int]=None, envelope=None, error_code=None)` |
| `EeroFeatureUnavailableException` | `EeroAPIException` | A `FEATURE_UNAVAILABLE` string on any status, and locally when an eero has no nightlight. `__init__(self, feature: str, reason: str='not supported on this device', *, envelope=None, error_code=None)`; `from_response(message, *, status_code: Optional[int]=None, envelope=None, error_code=None)` sets `feature` to the `error_code` and `reason` to the message |

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
`CHANNEL_UTILIZATION_BANDS` is `eero.api.events`-only.

> ⚠️ **Warning:** `EeroDeviceType`, `EeroNetworkStatus`, and `EeroDeviceStatus` (defined in
> `src/eero/const.py`) are **NOT** re-exported from the package root. `eero/__init__.py` does
> not import from `const.py` at all. Import them explicitly:
> `from eero.const import EeroDeviceType`.

---

## Constants

Public, useful constants from `src/eero/const.py` (import via `from eero.const import ...`):

| Constant | Value | Purpose |
|----------|-------|---------|
| `API_HOST` | `"https://api-user.e2ro.com"` | The only host the session token is ever sent to, and the only host a link or absolute URL is accepted for |
| `api_endpoint(version)` | `f"{API_HOST}/{version}"` | The single function that joins a version onto the host |
| `API_VERSION_DEFAULT` | `"2.2"` | Path version for networks, eeros, profiles, and every family not listed below |
| `API_VERSION_DEVICE_WRITES` | `"2.3"` | `set_device_nickname` / `pause_device` — the same write on `2.2` returns 200 and changes nothing |
| `API_VERSION_MULTISTATICIP` | `"2.3"` | `WanAPI.get_multistaticip` / `set_multistaticip` |
| `API_VERSION_SECONDARY_WAN` | `"2.3"` | `WanAPI.set_secondary_wan_config` / `set_device_secondary_wan_access` |
| `API_VERSION` | `API_VERSION_DEFAULT` | Alias kept for existing imports |
| `API_ENDPOINT` | `api_endpoint(API_VERSION_DEFAULT)` | Base URL for reads and most writes |
| `DEVICE_UPDATE_ENDPOINT` | `api_endpoint(API_VERSION_DEVICE_WRITES)` | Base URL for the verified device-mutation writes |
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

> ⚠️ **Warning:** The `2.2` vs `2.3` split matters for three groups: `set_device_nickname` and
> `pause_device` (routed through `DevicesAPI._update_device()` to `API_VERSION_DEVICE_WRITES`
> because the mutation is silently dropped on `2.2` — see issue #102), the multi-static-IP
> family, and the secondary-WAN family. `block_device` / `unblock_device` are NOT on `2.3` —
> they write `POST`/`DELETE networks/{id}/blacklist` on `2.2` (issue #109). Reads and every
> other family use `API_VERSION_DEFAULT`, except that a link read from an envelope keeps
> whatever version prefix the API put on it.

`EeroDeviceType`, `EeroNetworkStatus`, and `EeroDeviceStatus` are `str, Enum` classes also
defined in `const.py` — see [Module-level exports](#module-level-exports) for their
(non-)export status.

---

## 🔗 Related Pages

- [Python API](Python-API) — Task-oriented guide to `EeroClient`, grouped by topic with examples
- [Raw Response Format](Raw-Response-Format) — The `{"meta": ..., "data": ...}` envelope shape and the `resources` links
- [Network Targeting](Network-Targeting) — How `network_id` resolution works on `EeroClient`; IDs, paths, URLs and `parent=`
- [Caching and Rate Limits](Caching-and-Rate-Limits) — Which reads are cached, which writes invalidate what
- [Error Handling](Error-Handling) — The `EeroException` hierarchy and handling patterns
- [Deprecations](Deprecations) — No-op and removed surface, and what replaces it
- [Credential Storage](Credential-Storage) — Keyring, file, and memory storage backends
