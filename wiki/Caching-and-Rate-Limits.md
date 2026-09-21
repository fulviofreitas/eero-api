# ⚡ Caching and Rate Limits

`EeroClient` caches reads in memory to stay well under the Eero Cloud API's rate ceiling — here's exactly how it works.

---

## How the Cache Works

- **In-memory, per-instance** — the cache is a plain `dict` on the `EeroClient` instance (`self._cache`). It is created fresh in `__init__` and lives only as long as the client object.
- **Does NOT persist across processes.** Restarting your script, CLI invocation, or worker starts with an empty cache.
- **Not shared between `EeroClient` instances.** Two clients in the same process (or two processes) each keep their own cache; writes made through one are not visible to the other's cache until it re-fetches.
- **TTL in seconds, default 60**, set via the `cache_timeout` constructor argument:

```python
from eero import EeroClient

client = EeroClient(cache_timeout=120)  # cache entries valid for 120 seconds
```

> **Note**: `cache_timeout` only affects the SDK's own in-memory cache. It has no relationship to server-side caching. The `CACHE_TIMEOUT` constant in `src/eero/const.py` is unused — it's never imported anywhere in `src/`. The real default (`60`) is hardcoded directly on `EeroClient.__init__` (`cache_timeout: int = 60`).

---

## Which Methods Are Cached

Only these `EeroClient` read methods check and populate the cache. Every other `get_*` method on `EeroClient` hits the API on every call:

| Method | Cache key |
|---|---|
| `get_account()` | `"account"` |
| `get_networks()` | `"networks"` |
| `get_network(network_id)` | `"network"` keyed by `network_id` |
| `get_eeros(network_id)` | `"eeros"` keyed by `f"{network_id}_eeros"` |
| `get_devices(network_id)` | `"devices"` keyed by `f"{network_id}_devices"` |
| `get_device(device_id, network_id)` | `"devices"` keyed by `f"{network_id}_{device_id}"` |
| `get_profiles(network_id)` | `"profiles"` keyed by `f"{network_id}_profiles"` |
| `get_profile(profile_id, network_id)` | `"profiles"` keyed by `f"{network_id}_{profile_id}"` |

> ⚠️ **Warning:** `get_eero(eero_id, network_id, refresh_cache=False)` accepts a `refresh_cache` kwarg in its signature, but its implementation never checks or populates the cache — every call goes straight to the API. The kwarg currently has no effect. Every other method not in the table above (`get_diagnostics`, `get_security_settings`, `get_dns_settings`, `get_sqm_settings`, `get_led_status`, `get_nightlight`, `get_backup_internet`, `get_blacklist`, `get_reservations`, `get_forwards`, `get_transfer_stats`, `get_data_usage`, `get_speed_tests`, `get_schedules`, and every read in the families added in v8.0.0 — entitlements, events, permissions, notifications, DNS policies, members, WPA3, power saving, backup access points, subnets, WAN) is likewise never cached — it always makes a fresh request.

> **Note**: `get_devices(thread=...)` / `get_devices(proxied_node=...)` bypass the cache in both directions — a filtered list is neither served from nor written to the `devices` entry, because the cached list is the unfiltered one.

### The cache also feeds `parent=`

Beyond serving repeat reads, three cached entries are reused as the `parent=` envelope for
domain calls (see [Network Targeting](Network-Targeting#parent--use-the-link-the-api-published)):
a fresh `network` entry is passed to the network-scoped calls whose domain method resolves a
published network link (network reads, the settings-class writes, guest network, speed test,
diagnostics, updates, notifications, DNS writes and DNS policies, members, events, permissions,
WPA3, power saving, subnets/multi-static-IP reads, blacklist, the eero/device/profile lists,
the network-wide device and profile insights, reservations/forwards list+create); calls that
address a child resource (a device, profile, schedule, invite, reservation or forward by id)
or a literal sub-path (DNS read, data usage, the network/per-device/per-profile insights,
entitlements, Thread writes, backup, subnet/WAN writes) run without it. A fresh `eeros` list
supplies the matching eero's envelope to the eero calls, and a fresh single-device entry is
passed to `update_device_via_link`. This is read-only — the cached envelope is forwarded as-is and never
merged into a response. When the entry is stale or absent the call simply falls back to the
template URL; nothing is fetched to populate `parent=`.

---

## `refresh_cache=True`

The eight cached methods listed above accept a `refresh_cache: bool = False` keyword argument. Passing `refresh_cache=True` skips the cache lookup entirely, forces a live API call, and overwrites the cached entry with the fresh response:

```python
# Uses the cache if it's still within cache_timeout
networks = await client.get_networks()

# Bypasses the cache and re-fetches from the API
networks = await client.get_networks(refresh_cache=True)
```

---

## `clear_cache()`

Wipes every cache entry immediately, regardless of TTL:

```python
client.clear_cache()
```

The SDK also calls `clear_cache()` for you automatically after `verify()`, `logout()`, `set_session_token()`, and `clear_session_token()` — any operation that changes which session/account you're authenticated as.

---

## Automatic Invalidation on Writes

Write methods invalidate the specific cache entries they affect via internal helpers (`_invalidate_network_cache`, `_invalidate_eeros_cache`, `_invalidate_device_cache`, `_invalidate_profile_cache`, `_invalidate_profiles_list_cache`, `_invalidate_all_profile_caches`). Confirmed from `src/eero/client.py` at v8.0.0:

| Write method | Invalidates |
|---|---|
| `set_device_nickname`, `block_device`, `unblock_device`, `pause_device`, `set_device_type`, `set_device_labels`, `set_device_secondary_wan_access` | that device's cache entry + the network's device list |
| `update_device_via_link` | that device's cache entry + the network's device list; when `profile=` is given, also every cached profile of the network and the profile list (the previous profile is unknown, so all are dropped) |
| `pause_profile`, `set_profile_devices`, `set_profile_blocked_applications` | that profile's cache entry + the network's profile list |
| `create_profile`, `allow_domain_for_profiles`, `allow_cnames_for_profiles`, `block_domain_for_profiles` | the network's profile list |
| `rename_profile`, `delete_profile` | that profile's cache entry + the network's profile list |
| `reboot_eero`, `set_location`, `set_led`, `set_led_brightness`, `set_nightlight`, `node_action`, `port_action`, `nightlight_override` | the network's eeros list |
| `set_network_name`, `set_network_password`, `clear_network_password`, `set_guest_network`, `set_guest_password`, `clear_guest_password`, `run_speed_test`, `set_thread_enabled`, `update_thread`, `regenerate_thread_credentials`, `set_data_usage_report_settings`, `apply_update`, `set_backup_internet`, the DNS writes, `set_sqm`, `set_wpa3`, `set_band_steering`, `set_upnp`, `set_ipv6`, `configure_security`, `set_notification_settings`, `allow_domain`, `allow_cnames`, `block_domain`, `set_dhcp`, `set_connection_mode`, `set_nat_port_randomization`, `set_wpa3_per_band`, `set_mlo_mode`, `set_fast_transition`, `set_passpoint_enabled`, `set_proxied_nodes`, `set_power_saving`, `enable_ddns`, `disable_ddns`, `set_subnets_config`, `delete_subnet`, `set_multistaticip`, `set_secondary_wan_config` | that network's cache entry |

Invalidating the network entry also means the next network-scoped call runs without a cached
`parent=` envelope (template URL) until `get_network()` repopulates it.

> ⚠️ **Gotcha:** Not every write invalidates a related read. Confirmed **not** invalidated by this SDK version, despite mutating server-side state that a cached read reflects:
> - `create_schedule`, `update_schedule`, `delete_schedule`, `clear_profile_schedule`, `enable_bedtime` — do **not** invalidate the profile cache (the profile envelope is what `get_profile` caches; the schedules themselves are never cached)
> - `set_nightlight_brightness` / `set_nightlight_schedule` — these delegate to `set_nightlight`, so they *do* invalidate the eeros list; listed here only because their names are not in the table
> - `set_account_email`, `set_account_phone`, `set_push_settings` — do **not** invalidate the `account` entry (the first two only *start* a change; the matching `verify_*` call does invalidate it). `set_account_name`, `verify_account_email`, `verify_account_phone` and `set_account_consents` *do* reset the `account` entry.
> - `mark_notifications_read`, the invite/member writes, the power-saving schedule writes, the backup-access-point writes, `set_subnet_content_filters`, `set_pppoe`, `led_cycle` — nothing is invalidated; none of the reads they affect are cached anyway
>
> **Workaround**: after any write whose effect you need to see immediately, call the corresponding getter with `refresh_cache=True` (or, for uncached reads, simply call it — it is always fresh) rather than trusting the cache to have been cleared for you:
> ```python
> await client.set_push_settings({"<setting>": True})
> account = await client.get_account(refresh_cache=True)
> ```

---

## Writes: what "unverified" and "settings-class" mean

Every write in the families added in v8.0.0 — and the re-pointed writes listed in
[Migration](Migration#writes-now-use-the-forms-the-api-declares) — is **unverified against a
live network**: the request follows the field names, encoding, and path the API declares for the
operation, but the SDK has not confirmed on a real network that the write persists or what else
it does. Each of these logs one line at `WARNING` on the module's secure logger immediately
before the request is sent:

```
Issuing write (<operation>): its side effects have not been fully characterised against a live
network. Read the current state first and skip the write when it already matches -- never retry
a failed write in a loop.
```

**Settings-class writes may reboot the entire mesh.** The DNS write on `networks/{id}/settings`
is confirmed to restart every eero and drop every client; the SDK treats every other write to
that link and its settings-class siblings as capable of the same until proven otherwise —
`set_sqm`, `set_dhcp`, `set_connection_mode`, `set_nat_port_randomization`, `set_mlo_mode`,
`set_wpa3_per_band`, `set_fast_transition`, `set_power_saving`, `set_subnets_config`,
`delete_subnet`, `set_multistaticip`, `set_secondary_wan_config`,
`set_device_secondary_wan_access`, plus the security toggles (`set_wpa3`, `set_band_steering`,
`set_upnp`, `set_ipv6`, `configure_security`) that write the same `settings` link.
`apply_update` reboots every node by design, and `node_action("POWER_CYCLE_ALL_PORTS_AND_REBOOT")`
reboots that eero. The full statement of the discipline this implies, with a worked example, is
in [Python API — Writes and safety](Python-API#writes-and-safety); the short version is *read,
compare, skip if unchanged, never retry in a loop, and treat a 200 as "accepted", not
"settled"*.

---

## Rate Limits

The Eero Cloud API tolerates roughly **100 requests/minute**. Exceeding it returns HTTP `429`, which the SDK raises as `EeroRateLimitException` (see [Error Handling](Error-Handling)).

Practical guidance:

- **Lean on the cache** — the default 60-second TTL alone eliminates most redundant reads in interactive use.
- **Raise `cache_timeout` for polling workloads** — a monitoring loop checking network health every few minutes doesn't need fresh data every call.
- **Batch reads** — call `get_networks()` / `get_devices()` once and slice the response in memory rather than issuing one request per item.
- **Add backoff** — see the retry pattern in [Error Handling](Error-Handling#retry-with-exponential-backoff) for `EeroRateLimitException`. The SDK never retries a `429` itself, and never retries a write for any reason; the only built-in retry is the opt-in `get_retries` constructor option for `GET`s that fail with a transport error or a `5xx` (see [Configuration](Configuration#-retry-policy)).

### Example: a rate-limit-respecting monitoring loop

```python
import asyncio
from eero import EeroClient, EeroRateLimitException

async def main():
    async with EeroClient(cache_timeout=300) as client:
        while True:
            try:
                response = await client.get_eeros()
                eeros = response.get("data", [])
                for eero in eeros:
                    print(f"{eero.get('location')}: {eero.get('status')}")
            except EeroRateLimitException:
                await asyncio.sleep(60)
                continue

            await asyncio.sleep(300)  # poll every 5 minutes, matching cache_timeout

asyncio.run(main())
```

---

## Mobile User-Agent

The SDK sends a mobile-style `User-Agent` header on every request, defined in `src/eero/const.py`:

```python
DEFAULT_USER_AGENT: Final[str] = "eero/3.0 (iPhone; iOS 17.0)"
```

This exists because the Eero Cloud API rate-limits non-mobile clients more aggressively — presenting as the official mobile app reduces the chance of being throttled. It is not configurable. The full per-request header set (`Accept`, `User-Agent`, `X-Accept-Language`, and a per-request `Content-Type`) is described in [Configuration](Configuration#-request-headers-and-transport).

---

## `MAX_RESPONSE_BYTES` and Timeouts

`MAX_RESPONSE_BYTES` (10 MiB, `src/eero/const.py`) caps how much of a response body the SDK will buffer into memory. Streamed responses exceeding this are aborted mid-read and raised as `EeroAPIException` — a guard against unbounded memory consumption from a hostile or misbehaving upstream, not a rate-limit mechanism.

Request timeouts are hardcoded in `BaseAPI._request()` and are not configurable via `EeroClient`. See [Configuration](Configuration) for the exact values and how they interact with `EeroTimeoutException`.

---

## Tuning `cache_timeout`

| Workload | Suggested `cache_timeout` |
|---|---|
| Interactive CLI / one-off script | `60` (default) — fine as-is |
| Dashboard with a manual refresh button | `30`–`60` |
| Background monitoring / polling loop | `180`–`300` |
| Bulk reporting across many networks | `300`+, paired with `refresh_cache=True` only where freshness matters |
| Anything issuing writes immediately followed by reads | Use `refresh_cache=True` on the read — don't rely on cache invalidation for the gaps noted above |
| Anything issuing settings-class writes | Read, compare, and skip — the write itself is the expensive event (a possible mesh reboot), not the request |

---

## 🔗 Related Pages

- [Error Handling](Error-Handling) — `EeroRateLimitException`, `EeroTimeoutException`, and retry patterns
- [Configuration](Configuration) — client setup, options, and request timeouts
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope returned by every cached and uncached method alike
- [Network Targeting](Network-Targeting) — how `network_id` resolution interacts with cache keys, and how cached envelopes become `parent=`
- [Python API](Python-API#writes-and-safety) — the read-compare-skip discipline for every write
- [Troubleshooting](Troubleshooting) — common issues & fixes
