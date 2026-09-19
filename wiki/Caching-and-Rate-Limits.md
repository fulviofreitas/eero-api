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

> ⚠️ **Warning:** `get_eero(eero_id, network_id, refresh_cache=False)` accepts a `refresh_cache` kwarg in its signature, but its implementation never checks or populates the cache — every call goes straight to the API. The kwarg currently has no effect. Every other method not in the table above (`get_diagnostics`, `get_security_settings`, `get_dns_settings`, `get_sqm_settings`, `get_led_status`, `get_nightlight`, `get_backup_network`, `get_blacklist`, `get_reservations`, `get_forwards`, `get_transfer_stats`, `get_data_usage`, etc.) is likewise never cached — it always makes a fresh request.

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

Some write methods invalidate the specific cache entries they affect via two internal helpers, `_invalidate_device_cache(network_id, device_id)` and `_invalidate_profile_cache(network_id, profile_id)` (plus `_invalidate_profiles_list_cache(network_id)` for the profiles list only). Confirmed from `src/eero/client.py`:

| Write method | Invalidates |
|---|---|
| `set_device_nickname`, `block_device`, `pause_device` | that device's cache entry + the network's device list |
| `pause_profile`, `set_blocked_applications`, `set_profile_devices`, `set_profile_schedule` | that profile's cache entry + the network's profile list |
| `create_profile` | the network's profile list |
| `rename_profile`, `delete_profile` | that profile's cache entry + the network's profile list |
| `reboot_eero`, `set_led`, `set_nightlight` | the network's eeros list |
| `set_guest_network`, `run_speed_test`, `set_network_name` | that network's cache entry |

> ⚠️ **Gotcha:** Not every write invalidates a related read. Confirmed **not** invalidated by this SDK version, despite mutating server-side state that a cached read reflects:
> - `set_led_brightness` — does **not** invalidate the eeros cache (unlike `set_led` and `set_nightlight`, which do)
> - `enable_bedtime` and `clear_profile_schedule` — do **not** invalidate the profile cache (unlike `set_profile_schedule`, which does)
> - `set_wpa3`, `set_band_steering`, `set_upnp`, `set_ipv6`, `configure_security` — security settings aren't cached at all, so nothing to invalidate, but also nothing protects you from reading stale data elsewhere if you assumed otherwise
> - `configure_backup_network`, `set_backup_network` — no cache invalidation
>
> **Workaround**: after any write whose effect you need to see immediately, call the corresponding getter with `refresh_cache=True` rather than trusting the cache to have been cleared for you:
> ```python
> await client.set_led_brightness(eero_id, 50, network_id=network_id)
> eeros = await client.get_eeros(network_id=network_id, refresh_cache=True)
> ```

---

## Rate Limits

The Eero Cloud API tolerates roughly **100 requests/minute**. Exceeding it returns HTTP `429`, which the SDK raises as `EeroRateLimitException` (see [Error Handling](Error-Handling)).

Practical guidance:

- **Lean on the cache** — the default 60-second TTL alone eliminates most redundant reads in interactive use.
- **Raise `cache_timeout` for polling workloads** — a monitoring loop checking network health every few minutes doesn't need fresh data every call.
- **Batch reads** — call `get_networks()` / `get_devices()` once and slice the response in memory rather than issuing one request per item.
- **Add backoff** — see the retry pattern in [Error Handling](Error-Handling#retry-with-exponential-backoff) for `EeroRateLimitException`.

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

The SDK sends a mobile-style `User-Agent` header by default, defined in `src/eero/const.py`:

```python
DEFAULT_HEADERS: Final[Dict[str, str]] = {
    "User-Agent": "eero/3.0 (iPhone; iOS 17.0)",
    "Content-Type": "application/json",
}
```

Per the inline comment in `const.py`, this exists because the Eero Cloud API "has been observed to treat non-mobile clients more aggressively" for rate-limiting — presenting as the official mobile app reduces the chance of being throttled.

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

---

## 🔗 Related Pages

- [Error Handling](Error-Handling) — `EeroRateLimitException`, `EeroTimeoutException`, and retry patterns
- [Configuration](Configuration) — client setup, options, and request timeouts
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope returned by every cached and uncached method alike
- [Network Targeting](Network-Targeting) — how `network_id` resolution interacts with cache keys
- [Troubleshooting](Troubleshooting) — common issues & fixes
