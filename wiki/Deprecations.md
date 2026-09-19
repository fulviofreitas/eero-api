# ⚠️ Deprecations

A live register of SDK surface that still runs but should not be used, plus the surface that has
already been removed entirely.

---

## Summary

| Surface | Since | What happens when you call it | Replacement | Status |
|---|---|---|---|---|
| ❌ `eero.models` | removed v2.0.0 | `ImportError` | Raw `dict` access on `{"meta": ..., "data": ...}` | Removed |
| ❌ `EeroAPI.set_preferred_network` / `.preferred_network_id` | removed v5.0.0 (deprecated v4.7.0) | `AttributeError` | `EeroClient.set_preferred_network` / `.preferred_network_id`, or explicit `network_id=` | Removed |
| ❌ `DevicesAPI.set_device_priority` / `EeroClient.set_device_priority` | removed v8.0.0 | `AttributeError` | SQM (`SqmAPI` / `EeroClient` `set_sqm_enabled`, `configure_sqm`) | Removed |
| ❌ `ActivityAPI.*` / `EeroClient.get_activity*` | removed v8.0.0 | `AttributeError` | `InsightsAPI.get_insights` / `DataUsageAPI.get_data_usage` | Removed |
| ❌ `DnsAPI.set_ipv6_dns` / `EeroClient.set_ipv6_dns` | removed v8.0.0 | `AttributeError` | `SecurityAPI.set_ipv6` / `EeroClient.set_ipv6` for the connectivity toggle, `set_custom_dns_ipv6` for IPv6 DNS servers | Removed |
| ❌ `InsightsAPI.run_insights` | removed v8.0.0 | `AttributeError` | No replacement — the API declares no such operation | Removed |
| ❌ `OUICheckAPI.run_ouicheck` | removed v8.0.0 | `AttributeError` | No replacement — the API declares no such operation | Removed |
| ❌ `SecurityAPI.set_thread` / `EeroClient.set_thread_enabled` / `thread=` on `configure_security` | removed v8.0.0 | `AttributeError` / `TypeError` (unexpected keyword) | No replacement yet — Thread write support is planned for a future release | Removed |
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
| `DevicesAPI.set_device_priority` / `EeroClient.set_device_priority` | The API does not accept a `prioritized` field on the device object and has no `/priority` or `/qos` endpoint. Use SQM instead — `SqmAPI.set_sqm_enabled` / `EeroClient.set_sqm_enabled`, `SqmAPI.configure_sqm` / `EeroClient.configure_sqm` |
| `ActivityAPI` (module) / `EeroClient.get_activity`, `get_activity_clients`, `get_activity_for_device`, `get_activity_history`, `get_activity_categories` | The API no longer serves `/networks/{id}/activity*`. Use `InsightsAPI.get_insights` / `EeroClient.get_insights` for category, adblock, and inspected breakdowns, or `DataUsageAPI.get_data_usage` / `EeroClient.get_data_usage` for bandwidth per client or node |
| `DnsAPI.set_ipv6_dns` / `EeroClient.set_ipv6_dns` | This wrote the IPv6 connectivity toggle, not IPv6 DNS servers. Use `SecurityAPI.set_ipv6` / `EeroClient.set_ipv6` for the connectivity toggle, or `DnsAPI.set_custom_dns_ipv6` / `EeroClient.set_custom_dns_ipv6` for IPv6 DNS servers |
| `InsightsAPI.run_insights` | The API declares no such operation. No replacement |
| `OUICheckAPI.run_ouicheck` | The API declares no such operation. No replacement |
| `SecurityAPI.set_thread`, `EeroClient.set_thread_enabled`, and the `thread=` keyword on `configure_security` | The API does not accept a `thread` field on the settings write. Thread write support is planned for a future release; there is no substitute today |
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

See [Migration#v7x--v800](Migration#v7x--v800) for call-site replacement examples.

---

## 🔗 Related Pages

- [Migration](Migration) — full upgrade guide with before/after code for every breaking version
- [API Reference](API-Reference) — every domain API and method signature
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
