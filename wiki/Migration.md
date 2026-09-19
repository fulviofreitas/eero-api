# 🔀 Migration

Upgrade guide between eero-api major and preference-affecting minor releases.

---

## v1.x → v2.0.0

**What broke**: Pydantic models were deleted (`eero.models` no longer exists) and every API
method now returns the raw Eero Cloud API envelope — `{"meta": {...}, "data": {...}}` — instead
of a typed object. There is no field renaming (`wan_ip` is no longer surfaced as `public_ip`)
and no status normalization.

| Before (v1.x) | After (v2.0.0+) |
|---|---|
| `from eero.models import Network` | *(module does not exist — delete the import)* |
| `network.name` | `response["data"]["name"]` |
| `network.public_ip` | `response["data"]["wan_ip"]` |
| `for network in await client.get_networks():` | `data = response.get("data") or {}` / `networks = data if isinstance(data, list) else (data.get("networks") or data.get("data") or [])` — see [Raw Response Format](Raw-Response-Format#the-networks-shape-specifically) |

```python
# Before
networks = await client.get_networks()
for network in networks:
    print(network.name, network.status)

# After
response = await client.get_networks()
data = response.get("data") or {}
networks = data if isinstance(data, list) else (data.get("networks") or data.get("data") or [])
for network in networks:
    print(network["name"], network["status"])
```

> See [Raw Response Format](Raw-Response-Format#the-networks-shape-specifically) — the
> `data["networks"]` value is not guaranteed to be a list, so use the shape-tolerant
> extraction above instead of indexing `["data"]["networks"]` directly.

> **Note**: `EeroNetworkStatus` and `EeroDeviceStatus` still exist in `eero.const`, but they are
> no longer exported from top-level `eero` (`__all__`) and the SDK no longer normalizes any
> field into them — the raw string comes straight from the API.

Checklist:

- [ ] Delete every `from eero.models import ...` line — the module is gone.
- [ ] Replace all attribute access on API results (`x.foo`) with dict access (`x["data"]["foo"]`).
- [ ] Replace `for x in await client.get_X()` with `for x in (await client.get_X())["data"][...]`
      — iterating the raw return value directly walks the envelope's top-level keys
      (`"meta"`, `"data"`), not your records.
- [ ] Search for any renamed-field assumptions (e.g. `public_ip`) and switch to the raw
      upstream name (`wan_ip`).
- [ ] Confirm your exception handling already used the `*Exception` suffix
      (`EeroAuthenticationException`, `EeroAPIException`, etc.) — this SDK has never shipped
      `*Error`-suffixed exception classes, so no rename is needed here.

---

## v2.x → v3.0.0

**What broke**: Credential storage was simplified — `AuthCredentials` no longer stores redundant
legacy fields. If you have an older `cookies.json` on disk, `AuthCredentials.from_dict()`
transparently upgrades any legacy `user_token` field to `session_id` when the file is next
loaded.

> **Note**: This is a backward-compatible read-side migration, not a forced re-authentication.
> Existing stored sessions keep working; you do not need to call `login()`/`verify()` again
> purely because of this version bump.

Checklist:

- [ ] If you serialize/inspect `cookies.json` yourself (rather than only reading it through
      `FileStorage`/`KeyringStorage`), stop looking for a `user_token` key — read `session_id`
      instead.
- [ ] No code changes required if you only ever go through `AuthAPI` / `EeroClient` /
      `CredentialStorage` — the migration is internal to `from_dict()`.

---

## v3.x → v4.0.0

**What broke**: `preferred_network_id` is no longer part of credential storage.
`AuthCredentials` dropped the field, `AuthAPI` dropped the property/setter and
`save_preferred_network()`, and `cookies.json` now contains only `session_id`, `refresh_token`,
and `session_expiry`. Preferred-network selection moved to in-memory state on `EeroAPI` /
`EeroClient` — nothing about it is persisted by the SDK anymore.

| Before (v3.x) | After (v4.0.0+) |
|---|---|
| `auth_api.preferred_network_id` (persisted to `cookies.json`) | `client.preferred_network_id` (in-memory only, per `EeroClient` instance) |
| `await auth_api.save_preferred_network(id)` | *(method removed — no persistence layer in the SDK)* |

```python
# Before: relied on the SDK to remember your network choice across runs
async with EeroClient() as client:
    print(client.preferred_network_id)  # loaded from cookies.json

# After: the SDK only remembers it for the lifetime of this EeroClient instance;
# your application owns persistence if it wants any
async with EeroClient() as client:
    client.set_preferred_network("123456")
    ...  # persist "123456" yourself if you need it on the next run
```

Checklist:

- [ ] Stop expecting `preferred_network_id` to survive process restarts — it won't.
- [ ] If your application needs a durable "last used network" setting, store it in your own
      config file (this is exactly what [`eeroctl`](https://github.com/fulviofreitas/eeroctl)
      does — the CLI owns `config.json`, the SDK does not).
- [ ] Remove any code calling `save_preferred_network()` on `AuthAPI` — it's gone.

---

## v4.x → v5.0.0

**What broke**: `EeroAPI.set_preferred_network()` and `EeroAPI.preferred_network_id` — deprecated
since v4.7.0 — were removed. They never actually wired through to any domain API call, so
removing them changes no runtime behavior other than making the `AttributeError` explicit
instead of the calls being silently ineffective.

> **Note**: This ONLY affects `EeroAPI`. `EeroClient.set_preferred_network()` and
> `EeroClient.preferred_network_id` are unaffected and remain the supported way to set a
> default network for a client session.

| Before (v4.x, broken no-op on EeroAPI) | After (v5.0.0+) |
|---|---|
| `api.set_preferred_network("123456")` | `EeroClient.set_preferred_network("123456")` **or** pass `network_id="123456"` to every `EeroAPI`/domain method call |
| `api.preferred_network_id` | *(removed — read it back from `EeroClient`, or track it yourself)* |

```python
# Before (v4.x) — looked like it worked, did nothing
api = EeroAPI()
api.set_preferred_network("123456")
await api.networks.get_networks()  # network_id was never actually consulted here

# After (v5.0.0+) — explicit network_id on every call
api = EeroAPI()
await api.networks.get_network("123456")

# Or use EeroClient, which resolves network_id for you
async with EeroClient() as client:
    client.set_preferred_network("123456")
    await client.get_network()  # resolves to "123456" automatically
```

Checklist:

- [ ] Grep for `.set_preferred_network(` and `.preferred_network_id` calls on any `EeroAPI`
      instance (not `EeroClient`) — these now raise `AttributeError`.
- [ ] Switch to `EeroClient` if you want automatic network resolution, or pass `network_id=`
      explicitly on every domain API call if you stay on the low-level `EeroAPI`.

---

## v5.x → v6.0.0

**What broke**: Two independent changes landed together.

1. **`InsightsAPI.get_insights` / `EeroClient.get_insights` now require keyword-only
   parameters.** The Eero Cloud API always required `start`, `end`, `insight_type`, and
   `cadence` as query parameters — calling without them previously returned an unusable `400`.
   The SDK now enforces this at the Python level via keyword-only arguments, so a caller who was
   already only passing `network_id` (the only way the old signature worked) sees no regression
   in practice — that call was already 100% broken.
2. **`ActivityAPI` is deprecated.** Every `/networks/{id}/activity*` endpoint has been removed
   upstream and now returns `404`. All `ActivityAPI` methods, and the corresponding
   `EeroClient.get_activity*` wrappers, are retained for one release cycle with a
   `DeprecationWarning` before removal.

```python
# Before (v5.x) — only worked because it was already broken
await client.get_insights(network_id)  # HTTP 400 either way

# After (v6.0.0+) — required keyword arguments
await client.get_insights(
    network_id,
    start="2026-07-01T00:00:00Z",
    end="2026-07-21T00:00:00Z",
    insight_type="blocked",
    cadence="daily",  # optional, defaults to "daily"
)
```

`InsightsAPI.get_insights` required parameters (verified in `src/eero/api/insights.py`):

| Parameter | Required | Notes |
|---|---|---|
| `network_id` | yes (positional) | `EeroClient.get_insights` differs here: `network_id` defaults to `None` and is resolved like other `EeroClient` methods |
| `start` | yes (keyword-only) | ISO 8601 timestamp |
| `end` | yes (keyword-only) | ISO 8601 timestamp |
| `insight_type` | yes (keyword-only) | e.g. `"adblock"`, `"blocked"`, `"inspected"` |
| `cadence` | no (keyword-only) | `"hourly"` \| `"daily"` \| `"weekly"`, defaults to `"daily"` |

Checklist:

- [ ] Add `start=`, `end=`, and `insight_type=` to every `get_insights` call — they are
      keyword-only and mandatory; omitting any of them still raises via the upstream `400`.
- [ ] Replace any `ActivityAPI` / `client.get_activity*` usage with `InsightsAPI.get_insights`
      (category / adblock / inspected breakdowns) or `DataUsageAPI.get_data_usage` (bandwidth per
      client or node) — `ActivityAPI` was removed outright in v8.0.0, see
      [Migration#v7x--v800](Migration#v7x--v800).

---

## v6.x → v7.0.0

**Read this one even if you think you don't use DNS.**

**What broke**: the DNS write methods did nothing at all before this release, and now they work.

`DnsAPI` was sending a `custom_dns` field (and `dns_caching`) that does not exist in the Eero
Cloud API. The backend accepts unrecognised keys with HTTP 200 and silently discards them, so
these four methods returned a success response while changing nothing on the network — in every
release from v4.1.3 through v6.2.0:

- `set_custom_dns`
- `clear_custom_dns`
- `set_dns_mode` (every mode)
- `set_dns_caching`

**The practical consequence**: if your code calls any of them, it has been a no-op. After
upgrading it will alter real network configuration. **Review those call sites before you
upgrade**, particularly anything that runs unattended.

### Four behaviour changes beyond "it works now"

Everything in the "Before" column describes what the SDK *attempted*. Because the field it
wrote did not exist, none of it reached your network — the calls were no-ops. **Your stored
configuration was never altered by this SDK.**

| Before (v6.x) — intended, but a no-op | After (v7.0.0) |
|---|---|
| `set_custom_dns([a, b, c])` silently dropped everything past the second entry before sending | Raises `EeroValidationException`; the cap is now **2 per address family** |
| `set_dns_mode("auto")` built an empty server list, which *would* have erased your servers had the write worked | Switches the mode selector to `automatic` and **retains** the stored servers |
| An unrecognised mode returned a locally fabricated `{"meta": {"code": 400}}` | Raises `EeroValidationException` |
| `set_dns_mode("cloudflare"/"google"/"opendns")` resolved a hardcoded server list | Removed — read the API's own catalogue instead (below) |

Malformed IP literals, addresses of the wrong family, and zone-scoped addresses are now also
rejected locally, before any request.

### Provider presets are gone — use the API's catalogue

`set_dns_mode` no longer accepts `"cloudflare"`, `"google"` or `"opendns"`. Those resolved a
server list hardcoded in the SDK, duplicating data the API already serves — and the copy was
incomplete, omitting Quad9. Read the authoritative list instead:

```python
data = (await client.get_dns_settings())["data"]
chosen = next(p for p in data["dns"]["default_test_servers"] if p["name"] == "Cloudflare")
await client.set_custom_dns(chosen["ipv4"] + chosen["ipv6"])
```

Each entry has `name`, `ipv4` and `ipv6`. This is the SDK's raw-JSON contract applied
consistently: values come from the API or from you, never invented in between.

### New capability

IPv6 DNS servers are now supported. Each address family has an independent mode selector and
server list, matching the four slots in the eero app:

```python
# All four slots — the list is split by family.
await client.set_custom_dns([
    "1.1.1.1", "1.0.0.1",
    "2606:4700:4700::1111", "2606:4700:4700::1001",
])

# Or one family at a time, leaving the other alone.
await client.set_custom_dns_ipv4(["8.8.8.8", "8.8.4.4"])
await client.set_custom_dns_ipv6(["2001:4860:4860::8888"])
await client.clear_custom_dns(family="ipv6")

# Re-enable the stored servers without resupplying them.
await client.set_dns_mode("custom")
```

`set_dns_mode("custom")` with no `custom_servers` used to be a usage error. It now re-enables
whatever the network already stores — the inverse of `clear_custom_dns`, and the same thing
the app's radio does.

`clear_custom_dns`, `set_custom_dns_ipv4`, `set_custom_dns_ipv6` and `set_ipv6_dns` are now on
`EeroClient`, so `client._api.dns` is no longer needed for them.

> **⚠️** `set_ipv6_dns()` does not set IPv6 DNS servers — it toggles `ipv6_upstream`, the IPv6
> connectivity setting, and always has. Use `set_custom_dns_ipv6()` instead. See
> [#125](https://github.com/fulviofreitas/eero-api/issues/125).

### Reading DNS settings

`get_dns_settings` never changed, but if you were reading the fields the old docstring named,
they do not exist. The real paths:

```python
data = (await client.get_dns_settings())["data"]

data["dns"]["mode"]                     # "custom" | "automatic"
data["dns"]["custom"]["ips"]            # IPv4 servers
data["dns"]["caching"]                  # bool
data["ipv6"]["name_servers"]["mode"]    # "custom" | "automatic"
data["ipv6"]["name_servers"]["custom"]  # IPv6 servers, fully expanded
```

Note the asymmetry (`custom.ips` vs `custom`), and that IPv6 addresses read back expanded —
`2606:4700:4700::1111` becomes `2606:4700:4700:0:0:0:0:1111`. Compare with
`ipaddress.IPv6Address`, not string equality.

### Checklist

- [ ] Audit every call to `set_custom_dns`, `set_dns_mode`, `clear_custom_dns` and
      `set_dns_caching` — they now take effect.
- [ ] Wrap DNS writes in `except EeroValidationException` if you pass user-supplied input.
- [ ] Replace any call passing more than 2 servers for one family.
- [ ] Replace `set_dns_mode("cloudflare"/"google"/"opendns")` with addresses read from
      `dns.default_test_servers`.
- [ ] Replace reads of `custom_dns` / `dns_caching` / `dns_servers` with the real paths above.
- [ ] Replace `set_ipv6_dns` with `set_custom_dns_ipv6` if you wanted IPv6 DNS servers.
- [ ] Drop any `client._api.dns` reach-through for `clear_custom_dns` / `set_ipv6_dns`.

---

## v7.x → v8.0.0

**What broke**: Five groups of changes landed together. First, ten symbols that either never
worked against the current API, or that the API stopped serving outright, are gone (this
section). Second, the session transport, refresh flow, credential record, retry policy, and
error model (new exception classes, `envelope` / `error_code`) changed — see
[Session transport and authentication](#session-transport-and-authentication) and the
subsections that follow it, in particular [Error classes and attributes](#error-classes-and-attributes). Third, `get_data_usage` and `get_ouicheck` now take the
parameters the API actually requires — see [`get_data_usage`](#get_data_usage-and-the-data-usage-family)
and [`get_ouicheck`](#get_ouicheck). Fourth, every domain method resolves its URL through the
links the API publishes, and a further set of writes were re-pointed to the request forms the
API declares — several of them replacing methods that could never have worked; see
[Resource links and `parent=`](#resource-links-and-parent) and
[Writes now use the forms the API declares](#writes-now-use-the-forms-the-api-declares). Fifth,
fourteen new domain modules were added — additive, but the section
[New families and what they replace](#new-families-and-what-they-replace) notes where they take
over from a removed method.

There is no deprecation window for this release — every removed call now raises
`AttributeError` (or, for a removed keyword such as `configure_security(thread=...)` or
`set_guest_network(password=...)`, `TypeError`) instead of the previous no-op or 404.

| Removed | If you called it | Do this instead |
|---|---|---|
| `DevicesAPI.set_device_priority` / `EeroClient.set_device_priority` | Remove the call — it never changed anything server-side | Use SQM: `client.set_sqm(True)` (a single on/off toggle — the API declares no bandwidth fields) |
| `ActivityAPI` (module) / `client.get_activity*` (all five methods) | Remove the call — it always raised `EeroAPIException` (404) | Use `client.get_insights(start=..., end=..., insight_type=...)` for category/adblock/inspected data, or `client.get_data_usage(...)` for bandwidth per client or node |
| `DnsAPI.set_ipv6_dns` / `EeroClient.set_ipv6_dns` | Replace with the method matching what you actually wanted | For the IPv6 connectivity toggle: `client.set_ipv6(enabled)`. For IPv6 DNS servers: `client.set_custom_dns_ipv6(servers)` |
| `InsightsAPI.run_insights` | Remove the call — the API has no such operation | None |
| `OUICheckAPI.run_ouicheck` | Remove the call — the API has no such operation | None |
| `SecurityAPI.set_thread`, `configure_security(thread=...)` | Remove the call/argument — the API does not accept a `thread` field on the settings write | `client.set_thread_enabled(enabled)` — same facade name, now a JSON `{"enabled": bool}` PUT to `networks/{id}/thread` via `ThreadAPI` (unverified write); also `update_thread(...)` and `regenerate_thread_credentials()` |
| `SettingsAPI` (module) / `EeroClient.get_settings` | Replace with a network read | `client.get_network()` — the same fields live on the network envelope |
| `PasswordAPI` (module) / `EeroClient.get_password` | Replace with a network read | `client.get_network()` — the network envelope carries the same fields |
| `BurstReportersAPI.get_burst_reporters` / `EeroClient.get_burst_reporters` | Remove the call — the endpoint returns 404 | None; the resource is POST-only — `client._api.burst_reporters.create_burst_reporter(...)` remains available |

```python
# Before (v7.x) — silent no-op
await client.set_device_priority(device_id, prioritized=True)

# After (v8.0.0+) — use SQM (read first; this is a settings-class write)
sqm = (await client.get_sqm_settings())["data"].get("sqm")
if sqm is not True:
    await client.set_sqm(True)
```

```python
# Before (v7.x) — always raised EeroAPIException (404)
await client.get_activity_history(period="week")

# After (v8.0.0+)
await client.get_insights(
    start="2026-07-01T00:00:00Z",
    end="2026-07-21T00:00:00Z",
    insight_type="blocked",
    cadence="daily",
)
```

```python
# Before (v7.x) — toggled ipv6_upstream, not DNS servers
await client.set_ipv6_dns(True)

# After (v8.0.0+) — pick the one you actually meant
await client.set_ipv6(True)                       # IPv6 connectivity toggle
await client.set_custom_dns_ipv6(["2001:4860:4860::8888"])  # IPv6 DNS servers
```

Checklist:

- [ ] Grep for `set_device_priority(` — remove it, switch to SQM if bandwidth control was the goal.
- [ ] Grep for `get_activity`, `get_activity_clients`, `get_activity_for_device`,
      `get_activity_history`, `get_activity_categories`, and `client._api.activity` — replace
      with `get_insights` or `get_data_usage`.
- [ ] Grep for `set_ipv6_dns(` and `client._api.dns.set_ipv6_dns` — split into `set_ipv6` and/or
      `set_custom_dns_ipv6` depending on intent.
- [ ] Grep for `run_insights(` and `run_ouicheck(` — remove; no replacement exists.
- [ ] Grep for `set_thread(` and `configure_security(` calls passing `thread=` — remove the
      argument. `client.set_thread_enabled(` still exists but is now a different, unverified
      write to the Thread resource; read `get_thread()` first and skip when unchanged.
- [ ] Grep for `get_settings(` and `client._api.settings` — replace with `get_network()`.
- [ ] Grep for `get_password(` and `client._api.password` — replace with `get_network()`.
- [ ] Grep for `get_burst_reporters(` and `client._api.burst_reporters.get_burst_reporters` —
      remove; `create_burst_reporter` is unaffected.

### Resource links and `parent=`

Every domain method now resolves its URL through the links the API publishes rather than a
hardcoded path. Two things follow for callers:

1. **Every resource argument is polymorphic.** Wherever a method took a bare `network_id` /
   `eero_id` / `device_id` / `profile_id`, it now also accepts the resource's API path (the
   `url` value from its envelope, e.g. `/2.2/networks/<network-id>`) or that path joined onto
   the API host. Existing bare-ID calls keep working unchanged. A URL on any other host or
   scheme raises `EeroValidationException` before a request is made.
2. **Every domain method gained a keyword-only `parent=`.** Pass the envelope you already hold
   and the method uses the link the API published on it (`resources.settings`,
   `resources.led_action`, the resource's own `url`, …) instead of a template. `EeroClient`
   passes its cached network / eero / device envelopes automatically, so facade callers get
   this without changing anything.

Because `parent=` is keyword-only and optional, no existing positional call breaks. The one
behavioural difference you may notice: through `EeroClient`, a network-scoped call made while a
fresh `get_network()` result is cached goes to the link the API published for that network,
which can be on a different version than before (`routing` is served on `2.3`, for example).

Two `EeroClient` reads changed shape to match: `get_devices()` gained keyword-only
`thread=` / `proxied_node=` filters (sent as query parameters; a filtered call bypasses the
cache), and `delete_reservation()` gained keyword-only `delete_forwards=`.

The helpers are exported from the package root — `resolve_link`, `self_url`, `resource_url`,
`sub_resource_url`, `join_api_path` — and `eero.const` gained `api_endpoint(version)`,
`API_VERSION_DEFAULT`, `API_VERSION_DEVICE_WRITES`, `API_VERSION_MULTISTATICIP`, and
`API_VERSION_SECONDARY_WAN` (`API_VERSION`, `API_ENDPOINT`, `DEVICE_UPDATE_ENDPOINT` remain as
aliases). Full description: [Network Targeting](Network-Targeting#resource-links-ids-paths-and-urls-are-interchangeable).

### Writes now use the forms the API declares

A set of existing writes were re-pointed to the path, encoding, and field names the API
declares for the operation. Several of the old writes could not have applied — the API accepts
unrecognised JSON keys with a 200 and discards them — so "it returned 200 before" is not
evidence that your call site worked. **Every re-pointed write is unverified against a live
network and logs one `WARNING` before the request**; see
[Writes and safety](Python-API#writes-and-safety) for the discipline this implies.

| Write | Before (v7.x) | After (v8.0.0) |
|---|---|---|
| `set_led(eero_id, enabled)` | JSON `{"led_on": bool}` PUT to the eero's own URL — **verified to change nothing**. Any caller who "successfully" set the LED through the SDK never did | Form-encoded `led_on=true|false` PUT to the eero's `led_action` link. Unverified; a later live check is pending |
| `set_led_brightness(eero_id, brightness)` | JSON PUT to the eero's own URL | Form-encoded `led_brightness=<int>` PUT to the `led_action` link. Unverified |
| `set_location(eero_id, location)` | *(new on `EeroClient`)* | Form-encoded `location=` PUT to the eero's own URL. Unverified |
| `set_network_name(name)` | JSON `{"name": ...}` PUT to `settings` | Form-encoded `name=` PUT to the network's `settings` link. Disconnects clients while it takes effect; the form shape is unverified |
| `set_network_password(password)` / `clear_network_password()` | *(new)* | Form-encoded `password=` PUT / DELETE on the network's `password` link. Disconnects clients; unverified |
| `set_guest_network(enabled, name=, password=)` | One JSON PUT carrying the password | `set_guest_network(*, enabled, name=None)` — form-encoded PUT to the `guestnetwork` link with `enabled` and, when given, `name`. **`password=` is gone** — use `set_guest_password(password)` / `clear_guest_password()` (form PUT / DELETE on the *guest network's* `password` link). Unverified |
| `block_device(device_id, blocked)` | One method toggling both directions | `block_device(mac)` sends a form-encoded `mac` to `POST networks/{id}/blacklist`; `unblock_device(mac)` is a separate `DELETE networks/{id}/blacklist/{mac}`. The form encoding is unverified (a JSON body was verified in the past); the DELETE is verified |
| `set_sqm_enabled` / `configure_sqm` / `set_sqm_bandwidth` / `set_sqm_auto` | JSON bodies with bandwidth / mode fields the API never declared | **Removed.** `set_sqm(enabled)` — PUT with no body to the `settings` link, value in the `sqm` query parameter. Settings-class: may reboot the mesh |
| `reboot_network()`, `reboot_eero()`, `run_speed_test()`, `apply_update()` | A different body encoding | `POST` with the two-character JSON-string body `""` to the published `reboot` / `speedtest` / `updates` link. `apply_update` is new on `EeroClient` and reboots every node |
| `set_nightlight(...)` | JSON PUT to the eero's own URL with `brightness`, `schedule_enabled`, `schedule_on`, `schedule_off`, `ambient_light_enabled` | JSON PUT to the nightlight sub-resource (`data.nightlight.url`) with only `enabled`, `brightness_percentage`, `schedule` — the fields the API declares. `set_nightlight_schedule(schedule)` forwards the schedule object unchanged; `set_nightlight_brightness(brightness_percentage)`. Raises `EeroFeatureUnavailableException` on an eero without a nightlight |
| `run_diagnostics()` | Empty POST | JSON POST with whichever of `device=` / `symptom=` you supply (an empty object otherwise). Additive |
| Thread writes | `SecurityAPI.set_thread` wrote a `thread` field the settings endpoint ignores | `set_thread_enabled(enabled)` (JSON `{"enabled": bool}`), `update_thread(*, thread_enable=, enable_credential_syncing=)`, `regenerate_thread_credentials()` (`""` POST) — all to the literal `networks/{id}/thread` path |
| `get_backup_network` / `get_backup_status` / `set_backup_network` / `configure_backup_network` | Fields (`phone_number`) the API never declared | **Removed.** `get_backup_internet()`, `set_backup_internet(enabled)` (JSON `{"backup_internet_enabled": bool}`), `get_cellular_backup_usage()`, `get_cellular_backup_events()` |
| `get_profile_schedule` / `set_profile_schedule(time_blocks)` | Wrote a `schedule` array onto the profile — not a profile field | **Removed.** Schedules are sub-resources: `get_schedules(profile_id)`, `create_schedule(profile_id, *, name, days, start, end, enabled=True)`, `update_schedule(schedule, *, ...)`, `delete_schedule(schedule)` (both take the pause's own path/URL or envelope), `clear_profile_schedule(profile_id)` (one DELETE per pause, returns a list of responses). `enable_bedtime` / `set_weekday_bedtime` / `set_weekend_bedtime` now create one pause each |
| `update_profile_content_filter` / `update_profile_block_list` / `get_blocked_applications` / `set_blocked_applications` | Wrote fields a profile does not have — silent no-ops | **Removed.** Use the DNS-policies family (below) |
| `DevicesAPI.*(network_id, device_id, ...)` | Parameter named `device_id` | Parameter named `mac`; positional calls unaffected. `EeroClient` wrappers keep `device_id` |
| `set_device_nickname` / `pause_device` | 2.3 JSON PUT (verified) | Unchanged — still the verified 2.3 write. New alongside it: `update_device_via_link(device_id, *, nickname=, paused=, profile=)` — a JSON PUT of those fields to the device's own URL on the default version, **unverified**; prefer the two verified methods for nickname/pause |
| `update_reservation(reservation_id, data)` / `update_forward(forward_id, data)` | Built the URL from `network_id` + ID | Domain signatures are now `update_reservation(reservation, data, *, network=None)` / `update_forward(forward, data, *, network=None)` — `reservation` / `forward` may be a bare ID (then `network=` is required), the resource's path/URL, or its envelope. `EeroClient` wrappers keep `(id, data, network_id=None)` |

Added on `EeroClient` in the same change, all unverified writes unless marked: `set_device_type`,
`get_device_labels` (read), `set_device_labels` (labels go as query parameters on the PUT),
`get_connections` (read), `get_speed_tests(*, limit=, start_time=, end_time=)` (read),
`get_guest_network` (read), `get_devices_insights` / `get_device_insights` /
`get_profiles_insights` / `get_profile_insights` / `get_profile_devices_insights` (verified
reads), `create_profile(name, *, devices=None, paused=None)` (additive keywords).

```python
# Before (v7.x)
await client.set_guest_network(enabled=True, name="Guest", password="<new-password>")
await client.block_device("<mac>", blocked=True)
await client.block_device("<mac>", blocked=False)
await client.set_profile_schedule("<profile-id>", time_blocks=[...])
await client.set_nightlight("<eero-id>", brightness=30, schedule_on="22:00", schedule_off="06:00")

# After (v8.0.0+)
await client.set_guest_network(enabled=True, name="Guest")
await client.set_guest_password("<new-password>")
await client.block_device("<mac>")
await client.unblock_device("<mac>")
await client.create_schedule("<profile-id>", name="Bedtime", days=["monday"], start="22:00", end="06:00")
await client.set_nightlight("<eero-id>", brightness_percentage=30, schedule={...})
```

### New families and what they replace

Fourteen domain modules were added (each with `EeroClient` wrappers): `entitlements`, `events`,
`permissions`, `notifications`, `dns_policies`, `members`, `account`, `dhcp`, `wpa3`,
`power_saving`, `ddns`, `backup_access_points`, `subnets`, `wan`; plus node/port actions, LED
cycle, nightlight override and eero support reads on `EerosAPI`, and MLO / fast transition /
Passpoint / proxied nodes on `SecurityAPI`. They are additive except where noted in the table
above. The one you are most likely to need during migration is DNS policies, which replaces the
removed profile content-filter methods:

```python
# Before (v7.x) — never persisted
await client._api.profiles.update_profile_block_list("<network-id>", "<profile-id>", ["example.com"])
await client.set_blocked_applications("<profile-id>", ["<app-id>"])

# After (v8.0.0+) — the DNS-policies resource family (premium feature)
await client.block_domain_for_profiles("example.com", profiles=["<profile-id>"])
await client.block_domain_for_profiles("example.com", profiles=["<profile-id>"], is_delete=True)  # remove
await client.set_profile_blocked_applications("<profile-id>", ["<app-id>"])
apps = await client.get_dns_policy_applications("<profile-id>")
```

Every method in every new family is listed with verb, path, and verified/unverified status in
the [API Reference](API-Reference#domain-apis), with usage in [Python API](Python-API).

Checklist (links and writes):

- [ ] Grep for `set_sqm_enabled(`, `configure_sqm(`, `set_sqm_bandwidth(`, `set_sqm_auto(` —
      replace with `set_sqm(enabled)` behind a read-compare-skip.
- [ ] Grep for `get_backup_network(`, `get_backup_status(`, `set_backup_network(`,
      `configure_backup_network(` — replace with the `*_backup_internet` / `cellular_backup`
      methods; drop `phone_number`.
- [ ] Grep for `set_guest_network(` calls passing `password=` — split into `set_guest_network`
      + `set_guest_password`.
- [ ] Grep for `block_device(` calls passing `blocked=` or a second positional — split into
      `block_device(mac)` / `unblock_device(mac)`.
- [ ] Grep for `set_profile_schedule(`, `get_profile_schedule(`, `time_blocks` — move to the
      schedules sub-resource methods.
- [ ] Grep for `update_profile_content_filter(`, `update_profile_block_list(`,
      `get_blocked_applications(`, `set_blocked_applications(` — move to the DNS-policies
      family.
- [ ] Grep for `set_nightlight(` / `set_nightlight_schedule(` — switch to
      `brightness_percentage=` / `schedule=`; drop `schedule_enabled`, `schedule_on`,
      `schedule_off`, `ambient_light_enabled`, `on_time`, `off_time`.
- [ ] Grep for `set_led(` / `set_led_brightness(` — audit: the old write did nothing, so any
      logic that assumed the LED state was changed has never been exercised.
- [ ] Grep for `device_id=` passed by keyword to a `DevicesAPI` method (not `EeroClient`) —
      rename to `mac=`.
- [ ] Grep for `update_reservation(` / `update_forward(` on the domain APIs — the network is now
      keyword-only `network=` and only needed for a bare ID.
- [ ] Any automation issuing a settings-class write (`set_sqm`, `set_dhcp`, `set_connection_mode`,
      `set_nat_port_randomization`, `set_mlo_mode`, `set_wpa3_per_band`, `set_fast_transition`,
      `set_power_saving`, `set_subnets_config`, `set_multistaticip`, secondary WAN, the DNS
      writes) must read, compare, and skip — a write may reboot the whole mesh.

### Session transport and authentication

**What changes for a caller: usually nothing.** `login()`, `verify()`, `logout()`,
`set_session_token()`, `clear_session_token()`, and `is_authenticated` keep their signatures,
and a stored session from 7.x keeps working after the credential record is migrated (below).
What changed is underneath:

| Before (v7.x) | After (v8.0.0) |
|---|---|
| Session token stored in the shared `aiohttp` cookie jar and sent as the `s=` cookie | Sent as the `X-User-Token` header on every request to the API host over `https`, and never to any other host or scheme. The legacy `s=` cookie is still sent **per request** (not via the jar) while `send_legacy_cookie=True` (default) |
| `login` / `verify` / `logout` sent JSON bodies | They send `application/x-www-form-urlencoded` bodies (`login=`, `code=`, and a field named `Cookie` carrying `s=<token>` respectively). `resend` sends `{}`; refresh sends the JSON string `""` |
| `User-Agent` and `Content-Type: application/json` on every request (`DEFAULT_HEADERS`) | `Accept: application/json`, `User-Agent` (`DEFAULT_USER_AGENT`), and `X-Accept-Language` (constructor option `accept_language`, default `en-US`) on every request; `Content-Type` set per request by the body encoding |
| Redirects refused (`allow_redirects=False`) | Still refused, and now `allow_redirects=True` raises `EeroValidationException` — it cannot be re-enabled |

Two things that will break if you relied on them:

- **If you passed your own `aiohttp.ClientSession`** and read the session token back out of its
  cookie jar, that jar is now empty — the SDK never writes the credential into it. Use
  `client._api.auth.get_auth_token()` if you need the token value.
- **If you called `BaseAPI.get`/`post`/… directly** with a `headers=` dict containing
  `X-User-Token`, `Cookie`, or `Authorization`, the call now raises `EeroValidationException`.
  Drop those headers — the transport attaches the credential itself.

`AuthCredentials` lost `is_session_expired()`, `has_valid_session()`, and `clear_session()`
along with the `refresh_token` and `session_expiry` fields. There is no client-side expiry any
more: **`is_authenticated` means a session token is present**, nothing else. Any "days
remaining" logic built on `session_expiry` has nothing to read and must go — the server is the
only authority on whether a token is still valid, and it says so with a 401.

### The credential record

The persisted record (keyring entry or `cookie_file`) is now:

```json
{"session_id": "…", "schema_version": 2}
```

A record written by 7.x (or earlier) — one with no `schema_version`, possibly carrying
`refresh_token`, `session_expiry`, or the pre-v3.0.0 `user_token` key — is migrated in place
the first time it is loaded: only the token is kept, the other fields are dropped, and the
record is re-saved in the shape above. This happens once, is idempotent, and logs no values.
No re-authentication is needed.

> **If you serialise or parse the credential file yourself, stop reading `session_expiry`
> and `refresh_token`.** They are no longer written, and any copy left in an old file is
> removed on first load. Read `session_id` only. If you *write* the file yourself, write the
> shape above including `schema_version: 2` — a record without the marker is treated as legacy
> and rewritten.

### Refresh now works — and what that means for long-running processes

In 7.x `refresh_session()` looked for a `refresh_token` that the API never issues, so a
server-driven refresh signal could not succeed. In v8.0.0 refresh is
`POST /2.2/login/refresh` authenticated by the session token itself, with the JSON body `""`:

| Behaviour | v8.0.0 |
|---|---|
| Credential used | The current session token — there is no refresh token |
| Endpoint | `/2.2/login/refresh` only; the `account/refresh` fallback is gone |
| Concurrency | Coalesced: one refresh in flight, concurrent callers wait for its result, then their original request is replayed once |
| Return value | `True` on HTTP 200, `False` on any API error from the refresh endpoint (401, 429, 5xx, …); a network or timeout failure still raises |
| Stored credentials | Cleared when the refresh endpoint answers 401 with `error.session.expired`, `.invalid`, `.revoked`, or an unrecognised/absent `error_code`. **Kept** for a recognised non-session code such as `error.verification.required` |
| Token in the refresh response | Deliberately ignored — the current token stays in use |

For a daemon, exporter, or scheduled job this is the practical change: the process can now
hold one token indefinitely. When the server asks for a refresh (a 401 carrying
`error.session.refresh`), the SDK refreshes and replays the request transparently; the only
`EeroAuthenticationException` you will see is a terminal one (session expired / invalid /
revoked), after which the stored credential is already cleared and you need to re-seed a token
or run the OTP flow. Catch it, re-authenticate, continue — do not add your own periodic
`refresh_session()` calls.

### Error classes and attributes

The SDK now classifies every error response against the API's closed catalogue of
`meta.error` strings (`eero.errors`, matched case-insensitively): the HTTP status picks the
class first, the string second, and an unrecognised or free-text string never changes the
status-chosen class. Every `EeroException` carries `envelope` (the raw, unmodified JSON
response body, or `None`) and `error_code` (`meta.error`, or `None`). The exception
**message** no longer contains the response body — it is the status plus the recognised
catalogue string, or the fixed label `unrecognised error string` — and `MAX_ERROR_BODY_CHARS`
(with its `... [truncated, N chars total]` suffix) is gone.

**Class changes** (all still subclasses of `EeroException`, so broad handlers keep working):

| Response | Before (v7.x) | After (v8.0.0) |
|---|---|---|
| Any 404 | `EeroAPIException(status_code=404)` | `EeroNotFoundException` — a subclass of `EeroAPIException`, so `except EeroAPIException` still catches it |
| 403 with `error.access.denied` | `EeroAPIException(status_code=403)` | `EeroAccessDeniedException` (subclass of `EeroAPIException`); `is_auth_error()` is `False`, credentials kept |
| 400 with a form-error string (`error.form.errors`, `error.form.email.malformed`, …) | `EeroAPIException(status_code=400)` | `EeroValidationException` with `field == "request"` and the envelope attached. **Not** a subclass of `EeroAPIException` — it derives from `EeroException` only, because it is also the SDK's client-side validation error. **Handlers that catch only `EeroAPIException` will not see it.** |
| Premium strings (`error.premium.user_not_subscribed`, `error.partner.unavailable`), any status | `EeroAPIException` | `EeroPremiumRequiredException` (now a subclass of `EeroAPIException`) |
| Feature-unavailable strings (`error.eero.offline`, `error.network.unavailable`, …), any status | `EeroAPIException` | `EeroFeatureUnavailableException` (now a subclass of `EeroAPIException`) |
| `error.app.version.blocked`, any status | `EeroAPIException` | `EeroClientBlockedException` (new; subclass of `EeroAPIException`) |
| `error.rate.limit` on a non-429 status | `EeroAPIException` | `EeroRateLimitException` |
| Any 401 | `EeroAuthenticationException` | Unchanged — always `EeroAuthenticationException`. Stored credentials are cleared only for a session-group string (`error.session.expired` / `.invalid` / `.revoked`) or an unrecognised 401 from the refresh endpoint; verification-state and `error.session.refresh` strings never clear them |
| Everything else (including every recognised domain string) | `EeroAPIException` | Unchanged — `EeroAPIException` with `error_code` set |

`EeroNotFoundException`, `EeroPremiumRequiredException`, and `EeroFeatureUnavailableException`
were previously defined but never raised; they are now raised by the transport and importable
from the package root. Their legacy constructors (`EeroNotFoundException(resource_type,
resource_id)`, etc.) still work; each also has a `from_response(...)` classmethod. `is_auth_error()`
is `True` only for `EeroAuthenticationException`.

**Matching on the message no longer works.** If you followed the `eeroctl`-style pattern of
matching a substring of `str(exc)`, switch to `error_code`:

```python
# Before (v7.x) — the body was pasted (truncated) into the message
except EeroAPIException as err:
    if "error.session.expired" in str(err): ...
    if err.status_code == 404: ...

# After (v8.0.0+) — the class and error_code carry the meaning
except EeroNotFoundException:
    ...
except EeroAuthenticationException as err:
    if err.error_code == "error.session.expired": ...
except EeroValidationException as err:          # API 400 form errors land here now
    print(err.error_code, err.envelope)
except EeroAPIException as err:
    if err.error_code == "error.assignment.ip.unavailable": ...
    print(err.status_code, err.envelope)         # the API's own envelope, unmodified
```

`from eero import ErrorGroup, classify_error_code` gives you the catalogue group of any
`error_code` if you want to branch by meaning rather than by exact string. The full group
list is in [Error Handling](Error-Handling#the-groups).

### Retry policy and new constructor options

Writes (`POST`/`PUT`/`DELETE`/`PATCH`) are never retried by the SDK, for any reason. An
opt-in bounded retry exists for `GET`s that fail with a transport error or a `5xx`:

```python
EeroClient(
    send_legacy_cookie=True,  # default; False sends only the X-User-Token header
    accept_language="en-US",  # default; X-Accept-Language header, printable ASCII only
    get_retries=0,            # default; additional GET attempts on transport error / 5xx
)
```

All three are keyword-only and also accepted by `EeroAPI` and `AuthAPI`. `4xx` and `429` are
never retried whatever `get_retries` is set to. The 401 refresh-and-replay is not a retry and
is not affected by this option.

### `get_data_usage` and the data-usage family

The data-usage endpoints accept query parameters only and reject a request body. The old
`payload` dict and free-form `resource` argument are gone; `start`, `end`, and `cadence`
(`"daily"` or `"hourly"`) are required keyword-only arguments, `timezone` is optional:

```python
# Before (v7.x)
await client.get_data_usage(payload={"resource": "network"})

# After (v8.0.0+)
await client.get_data_usage(
    start="2026-07-01T00:00:00Z",
    end="2026-07-21T00:00:00Z",
    cadence="daily",
    timezone="UTC",  # optional IANA name
)
```

Each former `resource` value is now an explicit method, on `EeroClient` (trailing
`network_id=None`, no auto-discovery) and on `DataUsageAPI` (`network_id` first), with the same
keyword-only window arguments:

| Old `resource` intent | `EeroClient` | `DataUsageAPI` |
|---|---|---|
| breakdown | `get_data_usage_breakdown(network_id=None, *, start, end, cadence=None, timezone=None)` | `get_breakdown(network_id, *, …)` |
| per-device list | `get_devices_data_usage(network_id=None, *, start, end, cadence=None, timezone=None, profile_id=None)` | `get_devices_usage(network_id, *, …)` |
| one device | `get_device_data_usage(device_mac, network_id=None, *, start, end, cadence, timezone=None)` | `get_device_usage(network_id, device_mac, *, …)` |
| eeros summary | `get_eeros_data_usage_summary(network_id=None, *, start, end, cadence, timezone=None)` | `get_eeros_summary(network_id, *, …)` |
| one eero | `get_eero_data_usage(eero_id, network_id=None, *, start, end, cadence, timezone=None)` | `get_eero_usage(network_id, eero_id, *, …)` |
| one profile | `get_profile_data_usage(profile_id, network_id=None, *, start, end, cadence, timezone=None)` | `get_profile_usage(network_id, profile_id, *, …)` |
| unprofiled devices | `get_unprofiled_devices_data_usage(network_id=None, *, start, end, cadence=None, timezone=None)` | `get_unprofiled_devices(network_id, *, …)` |
| unprofiled summary | `get_unprofiled_data_usage_summary(network_id=None, *, start, end, cadence, timezone=None)` | `get_unprofiled_summary(network_id, *, …)` |
| report settings (read) | `get_data_usage_report_settings(network_id=None)` | `get_report_settings(network_id)` |
| report settings (write) | `set_data_usage_report_settings(*, cadence, notification_day, network_id=None)` — invalidates that network's cache entry | `set_report_settings(network_id, *, cadence, notification_day)` |

The report-settings write is **unverified**: read first, write only on a difference, never retry.

An invalid `cadence` raises `EeroValidationException` before any request.

### `get_ouicheck`

The API returns `404` for `GET /networks/{id}/ouicheck` unless both `serial` and `version`
query parameters are present, so the old one-argument call never returned data. Both are now
required keyword-only arguments, taken from an eero envelope:

```python
# Before (v7.x) — always EeroAPIException (404)
await client.get_ouicheck()

# After (v8.0.0+) — both values come from the eero's own envelope (get_eeros / get_eero)
await client.get_ouicheck(serial="<eero-serial>", version="<eero-version>")
```

### Removed constants

| Removed from `eero.const` | Use instead |
|---|---|
| `DEFAULT_HEADERS` | `DEFAULT_USER_AGENT` for the UA string; headers are built per request by `eero.api.base.build_request_headers` |
| `REFRESH_ENDPOINTS`, `ACCOUNT_REFRESH_ENDPOINT` | `LOGIN_REFRESH_ENDPOINT` — the only refresh path |
| `SESSION_TOKEN_KEY`, `REFRESH_TOKEN_KEY` | Nothing — the record shape is `{"session_id", "schema_version"}`; `CREDENTIAL_SCHEMA_VERSION` is the only storage constant |
| `MAX_ERROR_BODY_CHARS` | Nothing — error bodies are no longer embedded; read `err.envelope` |

New: `API_HOST`, `API_VERSION`, `DEFAULT_USER_AGENT`, `DEFAULT_ACCEPT_LANGUAGE`,
`GET_RETRY_DELAY_SECONDS`, `CREDENTIAL_SCHEMA_VERSION`, `LOGIN_RESEND_ENDPOINT`,
`LOGOUT_COOKIE_FIELD_NAME`, `SESSION_COOKIE_PREFIX`, `api_endpoint(version)`,
`API_VERSION_DEFAULT`, `API_VERSION_DEVICE_WRITES`, `API_VERSION_MULTISTATICIP`,
`API_VERSION_SECONDARY_WAN`. `eero.api.base` additionally exports `RequestEncoding` and
`build_request_headers`; `eero.api.links` (re-exported from `eero`) adds `resolve_link`,
`self_url`, `resource_url`, `sub_resource_url`, `join_api_path`.

Checklist (transport, auth, errors, parameters):

- [ ] Grep for `session_expiry`, `refresh_token`, `is_session_expired`, `has_valid_session`,
      and `clear_session(` — remove; there is no client-side expiry and no refresh token.
- [ ] If anything outside the SDK reads or writes the credential file, read `session_id` only
      and write `{"session_id": ..., "schema_version": 2}`.
- [ ] Grep for `str(err)` / `err.message` / `in str(exc)` parsing of API error bodies — switch
      to `err.error_code` / `err.envelope` or the new exception classes.
- [ ] Grep for `except EeroAPIException` — add `except EeroValidationException` wherever an API
      400 form error must be handled; check `status_code == 404` / `== 403` branches, which can
      become `except EeroNotFoundException` / `except EeroAccessDeniedException`.
- [ ] Grep for `from eero.exceptions import EeroNotFoundException` (etc.) — still works, but
      these classes are now raised for real and importable from `eero` directly.
- [ ] Grep for `X-User-Token`, `"Cookie"`, or `Authorization` in any `headers=` you pass to the
      transport — remove them.
- [ ] Grep for `allow_redirects` — remove; it cannot be set.
- [ ] Grep for `from eero.const import` of `DEFAULT_HEADERS`, `REFRESH_ENDPOINTS`,
      `ACCOUNT_REFRESH_ENDPOINT`, `SESSION_TOKEN_KEY`, `REFRESH_TOKEN_KEY`, or
      `MAX_ERROR_BODY_CHARS` — replace per the table above.
- [ ] Grep for `get_data_usage(` — pass `start=`, `end=`, `cadence=`; drop `payload` /
      `resource`; move per-resource reads to the explicit `DataUsageAPI` methods.
- [ ] Grep for `get_ouicheck(` — pass `serial=` and `version=`.
- [ ] Long-running processes: remove any home-grown periodic refresh; handle a terminal
      `EeroAuthenticationException` by re-seeding a token or re-running the OTP flow.

---

## Upgrading safely

- **Pin your version** (`eero-api==7.0.0` or a narrow range) rather than `eero-api>=...` — this
  is a fast-moving SDK tracking an undocumented, reverse-engineered API, and breaking changes
  ship as major versions on purpose.
- **Read `CHANGELOG.md`** for every major version between your current pin and your target —
  don't skip versions when judging blast radius.
- **Find breakage fast** by grepping your codebase for:
  - `eero.models` or `from eero.models` — removed in v2.0.0.
  - `Error)` / `except eero.*Error` — this SDK has only ever used `*Exception` suffixes; if you
    see `*Error`, it's a bug in your code, not a rename to chase.
  - Attribute access on anything returned by an `eero-api` call (`result.name`, `result.status`)
    — since v2.0.0 every result is a raw `dict`.
  - Positional `network_id` arguments passed anywhere other than first on `EeroClient` methods,
    or first on `EeroAPI`/domain-API methods — `network_id` is always a required leading
    positional on the low-level APIs and an optional trailing keyword on `EeroClient`.
  - `set_preferred_network(` / `preferred_network_id` on an `EeroAPI` instance — removed in
    v5.0.0, see above.
  - `get_insights(` calls missing `start=`/`end=`/`insight_type=` — required since v6.0.0.
  - `set_custom_dns(` / `set_dns_mode(` / `clear_custom_dns(` / `set_dns_caching(` — these were
    no-ops before v7.0.0 and now take effect. Also grep for `custom_dns`, `dns_caching` and
    `dns_servers` as *response* keys: none of them exist in the API.
  - `set_device_priority(`, `get_activity`, `set_ipv6_dns(`, `run_insights(`, `run_ouicheck(`,
    `set_thread(`, `get_settings(`, `get_password(`, and `get_burst_reporters(` — all removed
    outright in v8.0.0, see above.
  - `set_sqm_enabled(`, `configure_sqm(`, `set_sqm_bandwidth(`, `set_sqm_auto(`,
    `get_backup_network(`, `get_backup_status(`, `set_backup_network(`,
    `configure_backup_network(`, `get_profile_schedule(`, `set_profile_schedule(`,
    `update_profile_content_filter(`, `update_profile_block_list(`, `get_blocked_applications(`,
    `set_blocked_applications(` — removed in v8.0.0 with the write re-pointing, see above.
  - `set_guest_network(` with `password=`, `block_device(` with `blocked=`, `set_nightlight(`
    with `brightness=` / `schedule_enabled=` / `schedule_on=` / `schedule_off=` /
    `ambient_light_enabled=`, `set_nightlight_schedule(` with `on_time=` / `off_time=`, and
    `device_id=` by keyword on a `DevicesAPI` method — re-signatured in v8.0.0, see above.
  - `session_expiry`, `refresh_token`, `MAX_ERROR_BODY_CHARS`, `DEFAULT_HEADERS`,
    `REFRESH_ENDPOINTS` — removed in v8.0.0 with the transport/auth changes, see above.
  - `get_data_usage(` without `start=`/`end=`/`cadence=`, and `get_ouicheck(` without
    `serial=`/`version=` — signatures changed in v8.0.0, see above.
  - `set_led(` / `set_led_brightness(` — not a signature change, but the pre-v8.0.0 write was
    verified to change nothing; any behaviour built on it has never actually run.

---

## 🔗 Related Pages

- [Deprecations](Deprecations) — surface that still exists but should not be used
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
- [Network Targeting](Network-Targeting) — passing `network_id` correctly
- [API Reference](API-Reference) — every domain API and method signature
