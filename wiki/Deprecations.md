# ⚠️ Deprecations

A live register of SDK surface that still runs but should not be used, plus the surface that has
already been removed entirely.

---

## Summary

| Surface | Since | What happens when you call it | Replacement | Status |
|---|---|---|---|---|
| ❌ `eero.models` | removed v2.0.0 | `ImportError` | Raw `dict` access on `{"meta": ..., "data": ...}` | Removed |
| ❌ `EeroAPI.set_preferred_network` / `.preferred_network_id` | removed v5.0.0 (deprecated v4.7.0) | `AttributeError` | `EeroClient.set_preferred_network` / `.preferred_network_id`, or explicit `network_id=` | Removed |
| ❌ `DevicesAPI.set_device_priority` / `EeroClient.set_device_priority` | removed v8.0.0 | `AttributeError` | SQM (`SqmAPI.set_sqm` / `EeroClient.set_sqm`) | Removed |
| ❌ `ActivityAPI.*` / `EeroClient.get_activity*` | removed v8.0.0 | `AttributeError` | `InsightsAPI.get_insights` / `DataUsageAPI.get_data_usage` | Removed |
| ❌ `DnsAPI.set_ipv6_dns` / `EeroClient.set_ipv6_dns` | removed v8.0.0 | `AttributeError` | `SecurityAPI.set_ipv6` / `EeroClient.set_ipv6` for the connectivity toggle, `set_custom_dns_ipv6` for IPv6 DNS servers | Removed |
| ❌ `InsightsAPI.run_insights` | removed v8.0.0 | `AttributeError` | No replacement — the API declares no such operation | Removed |
| ❌ `OUICheckAPI.run_ouicheck` | removed v8.0.0 | `AttributeError` | No replacement — the API declares no such operation | Removed |
| ❌ `SecurityAPI.set_thread` / `thread=` on `configure_security` | removed v8.0.0 | `AttributeError` / `TypeError` (unexpected keyword) | `ThreadAPI.set_thread_enabled` / `EeroClient.set_thread_enabled` (same facade name, now backed by a JSON PUT to `networks/{id}/thread` — unverified write) | Removed |
| ❌ `SqmAPI.set_sqm_enabled`, `set_sqm_bandwidth`, `configure_sqm`, `set_sqm_auto` / `EeroClient.set_sqm_enabled`, `configure_sqm` | removed v8.0.0 | `AttributeError` | `SqmAPI.set_sqm(network_id, enabled)` / `EeroClient.set_sqm(enabled)` — SQM is one boolean query parameter; the API has no bandwidth or auto variants | Removed |
| ❌ `BackupAPI.get_backup_network`, `get_backup_status`, `set_backup_network`, `configure_backup_network` and the `EeroClient` wrappers | removed v8.0.0 | `AttributeError` | `get_backup_internet` / `set_backup_internet(enabled)` / `get_cellular_backup_usage` / `get_cellular_backup_events` | Removed |
| ❌ `ProfilesAPI.update_profile_content_filter`, `update_profile_block_list`, `get_blocked_applications`, `set_blocked_applications` / `EeroClient.get_blocked_applications`, `set_blocked_applications` | removed v8.0.0 | `AttributeError` | The DNS-policies family: `allow_domain` / `block_domain` / `*_for_profiles`, `get_dns_policy_applications`, `set_profile_blocked_applications` | Removed |
| ❌ `ScheduleAPI.get_profile_schedule`, `set_profile_schedule` / `EeroClient.get_profile_schedule`, `set_profile_schedule` | removed v8.0.0 | `AttributeError` | Schedules are sub-resources: `get_schedules`, `create_schedule`, `update_schedule`, `delete_schedule`, `clear_profile_schedule` | Removed |
| ❌ `set_nightlight(..., brightness=, schedule_enabled=, schedule_on=, schedule_off=, ambient_light_enabled=)` and `set_nightlight_schedule(enabled, on_time, off_time)` | re-signatured v8.0.0 | `TypeError` | `set_nightlight(enabled=, brightness_percentage=, schedule=)`; `set_nightlight_schedule(schedule)`; `set_nightlight_brightness(brightness_percentage)` | Removed |
| ❌ `set_guest_network(enabled, name=, password=)` | re-signatured v8.0.0 | `TypeError` | `set_guest_network(enabled=, name=)` for enable/rename; `set_guest_password(password)` / `clear_guest_password()` for the password | Removed |
| ❌ `block_device(device_id, blocked)` / `DevicesAPI.block_device(network_id, device_id, blocked)` | re-signatured v8.0.0 | `TypeError` on `DevicesAPI`; on `EeroClient` the second positional is bound to `network_id` (no `TypeError`) — audit these calls by grep | `block_device(mac)` and the separate `unblock_device(mac)` | Removed |
| ❌ `device_id` parameter name on `DevicesAPI` methods | renamed v8.0.0 | `TypeError` if passed by keyword | `mac` — the device's MAC address (or its path / absolute URL). `EeroClient` wrappers keep `device_id` as the parameter name | Renamed |
| ❌ `SettingsAPI` / `EeroClient.get_settings` | removed v8.0.0 | `AttributeError` | `EeroClient.get_network` / `EeroClient.get_dns_settings` — the same fields are carried on the network envelope | Removed |
| ❌ `PasswordAPI` / `EeroClient.get_password` | removed v8.0.0 | `AttributeError` | `EeroClient.get_network` — the network envelope carries the same fields | Removed |
| ❌ `BurstReportersAPI.get_burst_reporters` / `EeroClient.get_burst_reporters` | removed v8.0.0 | `AttributeError` | None — the resource is POST-only; use `BurstReportersAPI.create_burst_reporter` | Removed |
| ❌ `AuthCredentials.refresh_token` / `.session_expiry` fields and `is_session_expired()` / `has_valid_session()` / `clear_session()` | removed v8.0.0 | `AttributeError` | None — there is no refresh token and no client-side expiry; the server decides session validity | Removed |
| ❌ `eero.const.DEFAULT_HEADERS`, `REFRESH_ENDPOINTS`, `ACCOUNT_REFRESH_ENDPOINT`, `SESSION_TOKEN_KEY`, `REFRESH_TOKEN_KEY`, `MAX_ERROR_BODY_CHARS` | removed v8.0.0 | `ImportError` | `DEFAULT_USER_AGENT`; `LOGIN_REFRESH_ENDPOINT` (the only refresh path); `CREDENTIAL_SCHEMA_VERSION`; nothing for the rest | Removed |
| ❌ `get_data_usage(network_id, payload, resource)` (positional `payload` dict and free-form `resource`) | removed v8.0.0 | `TypeError` | `get_data_usage(network_id, *, start, end, cadence, timezone=None)` plus the explicit `DataUsageAPI` reads (`get_breakdown`, `get_devices_usage`, …) | Removed |
| ❌ `get_ouicheck(network_id)` with no `serial` / `version` | removed v8.0.0 | `TypeError` | `get_ouicheck(network_id, *, serial, version)` — the API returns `404` without both | Removed |

---

## Already-removed surface

If you hit an `AttributeError` or `ImportError`, check this list before filing a bug — it's
probably intentional.

### `eero.models`

Removed entirely in v2.0.0. There is no `eero.models` module, and there never will be one again
— the SDK now returns raw `dict` responses from every method. See
[Migration#v1x--v200](Migration#v1x--v200) and [Raw Response Format](Raw-Response-Format).

### `EeroAPI.set_preferred_network` / `EeroAPI.preferred_network_id`

Deprecated in v4.7.0, removed in v5.0.0. They never wired through to any domain API call, so
their removal changes no observable runtime behavior beyond raising `AttributeError` instead of
silently doing nothing.

> **Note**: This only affects `EeroAPI`. `EeroClient.set_preferred_network()` and
> `EeroClient.preferred_network_id` are current, supported API — they were never deprecated.

See [Migration#v4x--v500](Migration#v4x--v500) for the exact replacement pattern.

### 8.0.0 — removals

Every symbol below is gone outright — no deprecation window, since each one either never worked
against the current API or the API stopped serving the underlying endpoint.

| Removed symbol | Replacement / reason |
|---|---|
| `DevicesAPI.set_device_priority` / `EeroClient.set_device_priority` | The API does not accept a `prioritized` field on the device object and has no `/priority` or `/qos` endpoint. Use SQM instead — `SqmAPI.set_sqm` / `EeroClient.set_sqm` |
| `ActivityAPI` (module) / `EeroClient.get_activity`, `get_activity_clients`, `get_activity_for_device`, `get_activity_history`, `get_activity_categories` | The API no longer serves `/networks/{id}/activity*`. Use `InsightsAPI.get_insights` / `EeroClient.get_insights` for category, adblock, and inspected breakdowns, or `DataUsageAPI.get_data_usage` / `EeroClient.get_data_usage` for bandwidth per client or node |
| `DnsAPI.set_ipv6_dns` / `EeroClient.set_ipv6_dns` | This wrote the IPv6 connectivity toggle, not IPv6 DNS servers. Use `SecurityAPI.set_ipv6` / `EeroClient.set_ipv6` for the connectivity toggle, or `DnsAPI.set_custom_dns_ipv6` / `EeroClient.set_custom_dns_ipv6` for IPv6 DNS servers |
| `InsightsAPI.run_insights` | The API declares no such operation. No replacement |
| `OUICheckAPI.run_ouicheck` | The API declares no such operation. No replacement |
| `SecurityAPI.set_thread` and the `thread=` keyword on `configure_security` | The API does not accept a `thread` field on the settings write. Thread is its own resource: `ThreadAPI.set_thread_enabled(network_id, enabled)` (JSON `{"enabled": bool}` PUT to `networks/{id}/thread`), `update_thread(*, thread_enable=, enable_credential_syncing=)`, and `regenerate_thread_credentials()`, each with an `EeroClient` wrapper of the same name. `EeroClient.set_thread_enabled` therefore keeps its name and signature but is a different, unverified write |
| `SettingsAPI` (module) / `EeroClient.get_settings` | The endpoint returns 404 on every path version. The same fields are carried on the network envelope — use `EeroClient.get_network` (or `get_dns_settings` / `get_security_settings` for the relevant subset) |
| `PasswordAPI` (module) / `EeroClient.get_password` | The endpoint returns 404 on every path version. The network envelope carries the same fields — use `EeroClient.get_network` |
| `BurstReportersAPI.get_burst_reporters` / `EeroClient.get_burst_reporters` | The endpoint returns 404; the resource is POST-only. Use `BurstReportersAPI.create_burst_reporter` (no `EeroClient` wrapper) via `client._api.burst_reporters` |
| `AuthCredentials.refresh_token`, `AuthCredentials.session_expiry`, `is_session_expired()`, `has_valid_session()`, `clear_session()` | The API issues no refresh token (refresh reuses the session token) and the SDK no longer tracks an expiry — `is_authenticated` means a token is present, and the server signals invalidity with a 401. The persisted record is now `{"session_id": ..., "schema_version": 2}`; old records are migrated on load |
| `DEFAULT_HEADERS` | Headers are built per request by `eero.api.base.build_request_headers`. The User-Agent string is `DEFAULT_USER_AGENT`; `Content-Type` is set per request by the body encoding |
| `REFRESH_ENDPOINTS`, `ACCOUNT_REFRESH_ENDPOINT` | The API has one refresh path, `LOGIN_REFRESH_ENDPOINT` (`/2.2/login/refresh`); `account/refresh` is not served |
| `SESSION_TOKEN_KEY`, `REFRESH_TOKEN_KEY` | Never used as storage keys by the current record shape. `CREDENTIAL_SCHEMA_VERSION` is the only storage-related constant |
| `MAX_ERROR_BODY_CHARS` | Error bodies are no longer embedded in messages or logs at all, so there is nothing to truncate. Read `err.envelope` / `err.error_code` instead |
| `get_data_usage(network_id, payload, resource)` | The data-usage endpoints accept query parameters only and reject a body. Use `get_data_usage(network_id, *, start, end, cadence, timezone=None)`; each former `resource` value is now an explicit `DataUsageAPI` method |
| `get_ouicheck(network_id)` | The API returns 404 unless `serial` and `version` are supplied. Use `get_ouicheck(network_id, *, serial, version)` |
| `SqmAPI.set_sqm_enabled`, `SqmAPI.set_sqm_bandwidth`, `SqmAPI.configure_sqm`, `SqmAPI.set_sqm_auto` / `EeroClient.set_sqm_enabled`, `EeroClient.configure_sqm` | SQM is a single boolean on the network's `settings` link, written as the `sqm` query parameter with no body; the API declares no per-direction bandwidth fields and no "auto" mode, so those variants could never have applied. Use `SqmAPI.set_sqm(network_id, enabled)` / `EeroClient.set_sqm(enabled)`. `get_sqm_settings` is unchanged |
| `BackupAPI.get_backup_network`, `get_backup_status`, `set_backup_network`, `configure_backup_network` / the four `EeroClient` wrappers of the same names | Replaced by the backup-internet resource: `get_backup_internet` (GET `networks/{id}/backupinternet`), `set_backup_internet(enabled)` (JSON `{"backup_internet_enabled": bool}` PUT — unverified), `get_cellular_backup_usage`, `get_cellular_backup_events`. There is no `phone_number` field |
| `ProfilesAPI.update_profile_content_filter`, `update_profile_block_list`, `get_blocked_applications`, `set_blocked_applications` / `EeroClient.get_blocked_applications`, `set_blocked_applications` | A profile has exactly four fields — `devices`, `name`, `paused`, `url`. Content filtering, block lists, and blocked applications were never profile fields, so these writes were silent no-ops. The DNS-policies family owns them: `DnsPoliciesAPI.allow_domain` / `block_domain` / `allow_cnames` (network-wide), `allow_domain_for_profiles` / `block_domain_for_profiles` / `allow_cnames_for_profiles`, `get_profile_applications` / `set_profile_blocked_applications` (`EeroClient.get_dns_policy_applications` / `set_profile_blocked_applications`) |
| `ScheduleAPI.get_profile_schedule`, `set_profile_schedule` / `EeroClient.get_profile_schedule`, `set_profile_schedule` | Scheduled pauses are sub-resources at `networks/{id}/profiles/{profile}/schedules`, not a `schedule` array on the profile. Use `get_schedules`, `create_schedule(*, name, days, start, end, enabled=True)`, `update_schedule(schedule, *, ...)`, `delete_schedule(schedule)`, `clear_profile_schedule` (one DELETE per pause). `enable_bedtime` / `set_weekday_bedtime` / `set_weekend_bedtime` remain and now create one pause each |
| `set_nightlight(enabled, brightness, schedule_enabled, schedule_on, schedule_off, ambient_light_enabled)`; `set_nightlight_brightness(brightness)`; `set_nightlight_schedule(enabled, on_time, off_time)` | The nightlight is its own sub-resource (`data.nightlight.url` on the eero) accepting exactly `enabled`, `brightness_percentage`, and `schedule`. New signatures: `set_nightlight(*, enabled=None, brightness_percentage=None, schedule=None)`, `set_nightlight_brightness(brightness_percentage)`, `set_nightlight_schedule(schedule)` — `schedule` is forwarded unchanged |
| `set_guest_network(enabled, name=None, password=None)` | The guest-network link takes `enabled` and `name` (form-encoded); the password is a separate resource. Use `set_guest_network(*, enabled, name=None)` plus `set_guest_password(password)` / `clear_guest_password()` |
| `DevicesAPI.block_device(network_id, device_id, blocked)` / `EeroClient.block_device(device_id, blocked)` | Blocking is `POST networks/{id}/blacklist` with a form-encoded `mac`; unblocking is a `DELETE`. Use `block_device(mac)` and `unblock_device(mac)` (facade: `block_device(device_id)` / `unblock_device(device_id)`) |
| `DevicesAPI.*(network_id, device_id, ...)` parameter name | Every `DevicesAPI` method names its device parameter `mac`; pass it positionally or as `mac=`. The `EeroClient` wrappers keep `device_id` |

See [Migration#v7x--v800](Migration#v7x--v800) for call-site replacement examples.

---

## 🔗 Related Pages

- [Migration](Migration) — full upgrade guide with before/after code for every breaking version
- [API Reference](API-Reference) — every domain API and method signature
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
