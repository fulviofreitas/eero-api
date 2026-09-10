# ⚠️ Deprecations

A live register of SDK surface that still runs but should not be used, plus the surface that has
already been removed entirely.

---

## Summary

| Surface | Since | What happens when you call it | Replacement | Status |
|---|---|---|---|---|
| 🚫 `DevicesAPI.set_device_priority` / `EeroClient.set_device_priority` | deprecated (no upstream endpoint) | `DeprecationWarning`, HTTP 200, **no effect** | SQM (`SqmAPI` / `EeroClient` `set_sqm_enabled`, `configure_sqm`) | Live, still present as of v6.2.0 — removal date unannounced despite the deprecation message |
| 🚫 `ActivityAPI.*` / `EeroClient.get_activity*` | deprecated v6.0.0 | `DeprecationWarning`, then `EeroAPIException` (HTTP 404) | `InsightsAPI.get_insights` / `DataUsageAPI.get_data_usage` | Live, scheduled for removal in v6.0.0 |
| ❌ `eero.models` | removed v2.0.0 | `ImportError` | Raw `dict` access on `{"meta": ..., "data": ...}` | Removed |
| ❌ `EeroAPI.set_preferred_network` / `.preferred_network_id` | removed v5.0.0 (deprecated v4.7.0) | `AttributeError` | `EeroClient.set_preferred_network` / `.preferred_network_id`, or explicit `network_id=` | Removed |

---

## `DevicesAPI.set_device_priority` (and `EeroClient.set_device_priority`)

This is the most important entry on this page — it is easy to believe it works when it doesn't.

- **What it is**: A method that accepts `network_id`, `device_id`, `prioritized: bool`, and an
  optional `duration_minutes`, intending to set bandwidth priority for a device.
- **What actually happens**: Eero's cloud API no longer exposes device-level priority — there is
  no `/priority` or `/qos` endpoint, and the `prioritized` field does not exist on the device
  object. The SDK still sends `PUT` with `{"prioritized": bool}` to the device-update endpoint,
  which returns **HTTP 200** — but nothing about the device's state changes
  (live-verified). Calling it emits a `DeprecationWarning` but otherwise fails silently from the
  caller's perspective. See [issue #111](https://github.com/fulviofreitas/eero-api/issues/111).
- **Replacement**: Use SQM (Smart Queue Management / QoS) instead:
  - `SqmAPI.get_sqm_settings(network_id)` / `EeroClient.get_sqm_settings(network_id=None)`
  - `SqmAPI.set_sqm_enabled(network_id, enabled)` / `EeroClient.set_sqm_enabled(enabled, network_id=None)`
  - `SqmAPI.set_sqm_bandwidth(network_id, upload_mbps=None, download_mbps=None)`
  - `SqmAPI.configure_sqm(network_id, enabled, upload_mbps=None, download_mbps=None)` /
    `EeroClient.configure_sqm(enabled, upload_mbps=None, download_mbps=None, network_id=None)`
  - `SqmAPI.set_sqm_auto(network_id)`

  SQM manages bandwidth allocation network-wide rather than per-device priority flags, so it is
  the closest working equivalent to what `set_device_priority` was meant to do.
- **Removal status**: Scheduled for removal in v6.0.0 per the deprecation message baked into
  `src/eero/api/devices.py`; still present as of the current 6.2.0 release. Treat it as gone —
  do not add new callers.

```python
# Looks like it works, does nothing:
await client.set_device_priority(device_id, prioritized=True)  # DeprecationWarning, HTTP 200, no-op

# Use SQM instead:
await client.set_sqm_enabled(True)
await client.configure_sqm(enabled=True, upload_mbps=20, download_mbps=200)
```

> ⚠️ **Warning:** Do not build retry logic or error handling around
> `set_device_priority` "not working" — it will never raise. The HTTP 200 makes it
> indistinguishable from success unless you check device state afterward (which will show
> nothing changed).

---

## `ActivityAPI.*` / `client.get_activity*`

- **What it is**: `ActivityAPI` (`get_activity`, `get_activity_clients`,
  `get_activity_for_device`, `get_activity_history`, `get_activity_categories`) and their
  `EeroClient` wrappers of the same names.
- **Since**: Deprecated in v6.0.0.
- **What actually happens**: Every `/networks/{id}/activity*` endpoint has been removed from
  Eero's cloud API — live-verified against a real account on both API versions 2.2 and 2.3, and
  against the network's own resource map (which lists `insights` but no `activity` resource).
  Calling any of these methods emits a `DeprecationWarning`, then the request itself raises
  `EeroAPIException` for the HTTP 404 response — unlike `set_device_priority`, this is a loud
  failure, not a silent no-op.
- **Replacement**:
  - `InsightsAPI.get_insights(network_id, start=..., end=..., insight_type=...)` /
    `EeroClient.get_insights(network_id=None, *, start=..., end=..., insight_type=..., cadence="daily")`
    for category / adblock / inspected breakdowns.
  - `DataUsageAPI.get_data_usage(network_id, payload, resource=None)` /
    `EeroClient.get_data_usage(network_id=None, payload=None, resource=None)` for bandwidth per
    client or node.
- **Removal status**: Scheduled for removal in v6.0.0 per the module docstring in
  `src/eero/api/activity.py`; retained for one release cycle so downstream consumers
  (`eeroctl`, `eero-prometheus-exporter`) get a migration signal instead of a silent
  `ImportError`. Treat it as gone — see [issue #107](https://github.com/fulviofreitas/eero-api/issues/107).

```python
# Deprecated — raises EeroAPIException (404) after warning:
await client.get_activity_history(period="week")

# Replacement:
await client.get_insights(
    start="2026-07-01T00:00:00Z",
    end="2026-07-21T00:00:00Z",
    insight_type="blocked",
    cadence="weekly",
)
```

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

---

## 🔗 Related Pages

- [Migration](Migration) — full upgrade guide with before/after code for every breaking version
- [API Reference](API-Reference) — every domain API and method signature
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
