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
- [ ] Replace any `ActivityAPI` / `client.get_activity*` usage with
      [`InsightsAPI.get_insights`](Deprecations#activityapi--clientget_activity) (category /
      adblock / inspected breakdowns) or `DataUsageAPI.get_data_usage` (bandwidth per client or
      node) — see [Deprecations](Deprecations) for full detail.

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

---

## 🔗 Related Pages

- [Deprecations](Deprecations) — surface that still exists but should not be used
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
- [Network Targeting](Network-Targeting) — passing `network_id` correctly
- [API Reference](API-Reference) — every domain API and method signature
