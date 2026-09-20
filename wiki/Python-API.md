# 🐍 Python API

The `EeroClient` facade — installation, lifecycle, and every topic area of the SDK.

---

## Installation

```bash
pip install eero-api
# or
uv add eero-api
```

## Quickstart

```python
import asyncio
from eero import EeroClient

async def main():
    async with EeroClient() as client:
        if not client.is_authenticated:
            await client.login("you@example.com")
            await client.verify(input("Verification code: "))

        response = await client.get_networks()
        data = response.get("data") or {}
        networks = data if isinstance(data, list) else (data.get("networks") or data.get("data") or [])
        for network in networks:
            print(f"📶 {network.get('name')}: {network.get('status')}")

asyncio.run(main())
```

> **Note**: `is_authenticated` is a property, not a method — no `()`.

> **Note**: For a reusable shape-tolerant helper, see [Raw Response Format](Raw-Response-Format#the-networks-shape-specifically) — `get_networks()` can return the network list under more than one shape.

---

## Client Lifecycle

`EeroClient` is only usable as an async context manager. There is no `connect()` / `close()` pair.

```python
async with EeroClient() as client:
    ...  # session is opened on __aenter__ and torn down on __aexit__
```

### Constructor

| Argument | Type | Default | Purpose |
|----------|------|---------|---------|
| `session` | `Optional[aiohttp.ClientSession]` | `None` | Bring your own `aiohttp` session instead of letting the client create one. The session token is never written to its cookie jar |
| `cookie_file` | `Optional[str]` | `None` | Path used by the file-based credential storage fallback |
| `use_keyring` | `bool` | `True` | Store the session token in the OS keyring; falls back to the JSON cookie file when unavailable |
| `cache_timeout` | `int` | `60` | TTL in seconds for the client's in-memory response cache |
| `send_legacy_cookie` | `bool` | `True` | Keyword-only. Also send the session token as the per-request `s=<token>` cookie alongside the `X-User-Token` header; `False` sends the header only |
| `accept_language` | `str` | `"en-US"` | Keyword-only. Value of the `X-Accept-Language` header on every request; printable ASCII only |
| `get_retries` | `int` | `0` | Keyword-only. Additional attempts for a `GET` that fails with a transport error or `5xx`. Writes are never retried |

```python
import aiohttp
from eero import EeroClient

async with aiohttp.ClientSession() as session:
    async with EeroClient(
        session=session,
        use_keyring=False,
        cache_timeout=120,
        send_legacy_cookie=False,
        accept_language="en-GB",
        get_retries=2,
    ) as client:
        ...
```

> ⚠️ **Warning:** There is no `session_token`, `config_path`, or `timeout` constructor argument, and no environment variables are read. If you already have a session token, use `await client.set_session_token(token)` after entering the context manager.

The session token is sent as the `X-User-Token` header on every request to the API host over `https`, and to no other host; there is no client-side expiry — the server decides when a session is no longer valid, and asks the SDK to refresh it when needed. See [Authentication](Authentication) and [Configuration](Configuration#-request-headers-and-transport).

---

## Raw Response Envelope

Every method — on `EeroClient` and on the lower-level `EeroAPI` — returns the raw, unmodified JSON body from the Eero Cloud API:

```python
{"meta": {...}, "data": {...}}
```

There are no Pydantic models and `eero.models` does not exist. Always index into `resp["data"]`, never attribute-access. See [Raw Response Format](Raw-Response-Format) for the full shape and gotchas (list-vs-dict `data`, missing keys, etc.).

---

## Network Targeting

`network_id` is an **optional trailing keyword argument** on nearly every `EeroClient` method. When omitted, only 24 methods auto-discover your first network — every other method requires a preferred network already set (via `set_preferred_network()`, or as a side effect of calling `get_networks()` once) and raises `EeroException` otherwise. See [Network Targeting](Network-Targeting) for the full list and resolution order.

```python
await client.get_eeros()                              # auto-discovered network
await client.get_eeros(network_id="<network-id>")     # explicit network
```

> **Note**: Since v5.0.0, `set_preferred_network()` / `preferred_network_id` live on `EeroClient` only. The identically-named symbols were removed from `EeroAPI` — they never wired through to any domain API.

### IDs, paths, and URLs are interchangeable

Every resource argument — `network_id`, `eero_id`, `device_id`, `profile_id`, `forward_id`,
`reservation_id`, `invite_id`, a `schedule` — accepts a bare ID, the resource's API path (the
`url` value from its envelope), or that path joined onto the API host. A URL on any other host
or scheme raises `EeroValidationException` before any request. Domain methods additionally take
a keyword-only `parent=` envelope so the link the API published is used instead of a template;
`EeroClient` passes its cached envelopes as `parent=` for you. Full description:
[Network Targeting — Resource links](Network-Targeting#resource-links-ids-paths-and-urls-are-interchangeable).

```python
network = await client.get_network(network_id="<network-id>")
url = network["data"]["url"]                     # "/2.2/networks/<network-id>"
await client.get_eeros(network_id=url)           # the path form works everywhere an ID does
```

---

## Writes and safety

Read this before automating any write.

1. **The API accepts unrecognised JSON keys with a 200 and discards them.** A success status
   proves nothing about whether a write applied. After any write whose effect matters, read the
   resource back and compare.
2. **Every write in the families added in v8.0.0, and every write re-pointed in v8.0.0, is
   unverified against a live network.** The request follows the path, encoding, and field names
   the API declares, but the SDK has not confirmed on a real network that it persists or what
   else it does. Each such write logs one line at `WARNING` on its module's secure logger
   immediately before the request:

   ```
   Issuing write (<operation>): its side effects have not been fully characterised against a
   live network. Read the current state first and skip the write when it already matches --
   never retry a failed write in a loop.
   ```

   The writes that do *not* log this line are the ones whose request shape is verified or
   unchanged from earlier releases: `set_device_nickname`, `pause_device`, `set_device_type`
   (all verified 2026-09-20 or earlier), `unblock_device` (verified), the DNS writes (verified),
   `set_wpa3` / `set_band_steering` / `set_upnp` / `set_ipv6` / `configure_security`,
   `reboot_eero`, `set_led`, `set_led_brightness`, `run_speed_test`, `set_guest_network`,
   `set_guest_password`, `clear_guest_password` (verified 2026-09-20), `reboot_network`, the
   profile CRUD, `set_profile_devices`, `create_reservation` / `create_forward` and their
   update/delete, `create_burst_reporter`, `request_support`. Absence of the warning is not a
   claim that the write has been verified — the per-method status column in the
   [API Reference](API-Reference) is.
3. **Settings-class writes may reboot the whole mesh.** A DNS write is confirmed to restart
   every eero and drop every client a few minutes after the 200. The SDK treats every other
   write to the network's `settings` link, and its settings-class siblings, as capable of the
   same until proven otherwise: `set_sqm`, `set_dhcp`, `set_connection_mode`,
   `set_nat_port_randomization`, `set_mlo_mode`, `set_wpa3_per_band`, `set_fast_transition`,
   `set_power_saving`, `set_subnets_config`, `delete_subnet`, `set_multistaticip`,
   `set_secondary_wan_config`, `set_device_secondary_wan_access`, and the security toggles.
   `apply_update` reboots every node by design; `node_action` with
   `POWER_CYCLE_ALL_PORTS_AND_REBOOT` reboots that eero. Password and guest-network writes
   disconnect clients while they take effect.
4. **Therefore: read, compare, skip, never retry in a loop.** A 200 is "accepted", not
   "settled"; the effect lands minutes later. A reconciliation loop that writes unconditionally
   reboots the network every run, and a retry loop queues repeated reboots.

```python
# The pattern every settings-class write should follow
current = (await client.get_network(network_id="<network-id>", refresh_cache=True))["data"]
if current.get("sqm") is not True:
    await client.set_sqm(True, network_id="<network-id>")   # logs one WARNING, then PUTs
# Do not read back immediately expecting the new value to be settled.
```

The per-method status (verified read / unverified write / settings-class) is in the
[API Reference](API-Reference) tables; the cache side of this is in
[Caching and Rate Limits](Caching-and-Rate-Limits#writes-what-unverified-and-settings-class-mean).

---

## Account & Networks

```python
account = await client.get_account()
networks = await client.get_networks()
network = await client.get_network(network_id=None, refresh_cache=False)
premium = await client.get_premium_status(network_id=None)

await client.set_network_name("Home", network_id=None)            # form-encoded to the settings link; disconnects clients
await client.set_network_password("<new-password>", network_id=None)   # form-encoded to the password link; disconnects clients
await client.clear_network_password(network_id=None)               # DELETE on the password link
```

The three writes are unverified; `set_network_name`'s JSON shape was verified in the past, the
form shape it now sends has not been re-verified.

### Account profile

Every account write is unverified and logs the warning. Identifier values (email, phone,
verification codes) are never logged. Account deletion is deliberately not exposed.

```python
await client.set_account_name("<display-name>")
await client.set_account_email("you@example.com")          # then confirm:
await client.verify_account_email("<code>")
await client.set_account_phone("<phone>")                   # then confirm:
await client.verify_account_phone("<code>")
await client.set_account_consents(marketing_emails=False)
countries = await client.get_sms_countries()
```

---

## Eeros (Mesh Nodes)

```python
eeros = await client.get_eeros(network_id=None, refresh_cache=False)
eero = await client.get_eero(eero_id, network_id=None, refresh_cache=False)   # never cached
await client.reboot_eero(eero_id, network_id=None)                 # POST "" to the eero's reboot link; verified (2026-09-20): only the targeted node rebooted
await client.set_location(eero_id, "Living Room", network_id=None) # form-encoded; unverified
connections = await client.get_connections(eero_id, network_id=None)
support = await client.get_eero_support("<eero-serial>")          # may 404 on some nodes
```

### Node and port actions

Both are unverified writes; both power-cycle ports and drop wired clients while they
renegotiate. Invalid `action` values raise `EeroValidationException` locally.

```python
await client.node_action(eero_id, "POWER_CYCLE_ALL_PORTS", network_id=None)
await client.node_action(eero_id, "POWER_CYCLE_ALL_PORTS_AND_REBOOT", network_id=None)  # reboots the eero
await client.port_action(eero_id, "<interface-number>", "RESTART_POWER", network_id=None)
# port actions: ENABLE_DATA, DISABLE_DATA, ENABLE_POE, DISABLE_POE, ENABLE_PORT, DISABLE_PORT,
#               RESTART_POWER, ENABLE_PORT_SECURITY, DISABLE_PORT_SECURITY
```

---

## Devices

`device_id` on `EeroClient` is the device's MAC address (the domain methods name the parameter
`mac`). It also accepts the device's path or absolute URL.

```python
devices = await client.get_devices(network_id=None, refresh_cache=False)
thread_devices = await client.get_devices(network_id=None, thread=True)          # query param; bypasses the cache
proxied = await client.get_devices(network_id=None, proxied_node=True)
device = await client.get_device("<mac>", network_id=None, refresh_cache=False)

await client.set_device_nickname("<mac>", "Living Room TV", network_id=None)   # verified (2.3 endpoint)
await client.pause_device("<mac>", paused=True, network_id=None)               # verified (2.3 endpoint)
await client.block_device("<mac>", network_id=None)      # form-encoded mac to POST networks/{id}/blacklist
await client.unblock_device("<mac>", network_id=None)    # DELETE networks/{id}/blacklist/{mac}
```

```python
# The API's declared device-update form: a JSON PUT of nickname / paused / profile to the
# device's own URL on the default version. Prefer set_device_nickname / pause_device for
# those two fields — only the 2.3 write is verified to persist. Unverified; logs the warning.
await client.update_device_via_link("<mac>", nickname="TV", profile="/2.2/networks/<network-id>/profiles/<profile-id>")

await client.set_device_type("<mac>", "<device-type>", network_id=None)  # verified (2026-09-20): value persists and reads back
labels = await client.get_device_labels("<mac>", network_id=None)
# Verified NO-OP (2026-09-20): returns 200 with the labels echoed back, but the read-back
# (get_device_labels) never shows the new value. Still logs the warning.
await client.set_device_labels("<mac>", make_label="...", model_label="...", network_id=None)  # sent as query parameters
```

`get_device_priority(device_id)` still exists and returns the full device envelope — there is no
priority endpoint; use [SQM](#sqm--qos) for bandwidth control.

---

## Profiles

A profile has exactly four fields — `devices`, `name`, `paused`, `url`. Content filtering,
block lists, and blocked applications are not profile fields; they live in the
[DNS policies](#dns-policies-content-filtering) family.

```python
profiles = await client.get_profiles(network_id=None, refresh_cache=False)
profile = await client.get_profile(profile_id, network_id=None, refresh_cache=False)
await client.pause_profile(profile_id, paused=True, network_id=None)
await client.create_profile("Kids", devices=["/2.2/networks/<network-id>/devices/<mac>"], paused=False, network_id=None)
await client.rename_profile(profile_id, "Teens", network_id=None)
await client.delete_profile(profile_id, network_id=None)

devices = await client.get_profile_devices(profile_id, network_id=None)
await client.set_profile_devices(profile_id, device_urls=["/2.2/networks/<network-id>/devices/<mac>"], network_id=None)
```

---

## Schedules & Bedtime

Scheduled pauses are sub-resources at `networks/{id}/profiles/{profile}/schedules`, not a field
on the profile. Every write here is unverified and logs the warning.

```python
schedules = await client.get_schedules(profile_id, network_id=None)          # data is a list of pauses
created = await client.create_schedule(
    profile_id, name="Bedtime", days=["monday", "tuesday"], start="21:00", end="07:00", enabled=True, network_id=None
)

# update / delete address the pause by its own url (or its envelope) — no network_id needed
pause = created["data"]
await client.update_schedule(pause, enabled=False)
await client.update_schedule(pause["url"], start="22:00")
await client.delete_schedule(pause)

responses = await client.clear_profile_schedule(profile_id, network_id=None)  # one DELETE per pause; returns a list

# Convenience: one pause each, built on create_schedule
await client.enable_bedtime(profile_id, "21:00", "07:00", days=["monday"], network_id=None)
await client._api.schedule.set_weekday_bedtime("<network-id>", profile_id, "21:00", "07:00")
await client._api.schedule.set_weekend_bedtime("<network-id>", profile_id, "22:00", "08:00")
```

---

## Guest Network

```python
guest = await client.get_guest_network(network_id=None)
await client.set_guest_network(enabled=True, name="Guest WiFi", network_id=None)   # form-encoded enabled / name
await client.set_guest_password("<new-password>", network_id=None)               # form-encoded to the guest network's password link
await client.clear_guest_password(network_id=None)                               # DELETE
```

All three writes are live-verified (2026-09-20) and disconnect guest clients while they take
effect. `set_guest_network` no longer takes a password.

---

## Speed Test & Diagnostics

```python
results = await client.run_speed_test(network_id=None)                          # POST "" to the speedtest link; verified (2026-09-20): 202 with data: null, result appears in get_speed_tests about a minute later
history = await client.get_speed_tests(network_id=None, limit=10, start_time=None, end_time=None)  # GET on the same link
diagnostics = await client.get_diagnostics(network_id=None)
await client.run_diagnostics(network_id=None, device="<mac>", symptom="<symptom>")  # JSON body of the keys given; unverified
```

---

## DHCP Reservations

A reservation's body has exactly `description`, `ip`, `mac`, `public_static_ip` (plus its own
`url`); the SDK passes bodies through unchanged.

```python
reservations = await client.get_reservations(network_id=None)
await client.create_reservation({"mac": "<mac>", "ip": "192.168.4.50", "description": "NAS"}, network_id=None)
await client.update_reservation("<reservation-id>", {"ip": "192.168.4.51"}, network_id=None)
await client.delete_reservation("<reservation-id>", network_id=None, delete_forwards=True)   # query parameter
```

On `ReservationsAPI`, `update_reservation(reservation, data, *, network=None)` takes the
reservation's own path/URL or envelope, and needs `network=` only for a bare ID.

---

## Port Forwards

A forward's body has exactly `client_port`, `description`, `enabled`, `gateway_port`, `ip`,
`protocol` (plus its own `url`); the SDK passes bodies through unchanged.

```python
forwards = await client.get_forwards(network_id=None)
await client.create_forward({"ip": "192.168.4.10", "client_port": 8080, "gateway_port": 8080, "protocol": "tcp", "enabled": True, "description": "web"}, network_id=None)
await client.update_forward("<forward-id>", {"enabled": False}, network_id=None)
await client.delete_forward("<forward-id>", network_id=None)
```

---

## DNS

> **⚠️ Every DNS write reboots the whole mesh** — all eeros restart and clients lose
> connectivity. Read first and skip the write when nothing has changed; see
> [Writes and safety](#writes-and-safety) and
> [Troubleshooting](Troubleshooting#my-whole-network-went-down-after-changing-dns).

```python
dns = await client.get_dns_settings(network_id=None)
await client.set_dns_caching(enabled=True, network_id=None)

# All four slots at once — the list is split by address family.
await client.set_custom_dns(
    dns_servers=[
        "1.1.1.1", "1.0.0.1",                          # IPv4 primary / secondary
        "2606:4700:4700::1111", "2606:4700:4700::1001",  # IPv6 primary / secondary
    ],
    network_id=None,
)

# Or one family at a time; the other is left untouched.
await client.set_custom_dns_ipv4(["8.8.8.8", "8.8.4.4"], network_id=None)
await client.set_custom_dns_ipv6(["2001:4860:4860::8888"], network_id=None)

await client.set_dns_mode("custom", custom_servers=["1.1.1.1"], network_id=None)

# Back to the ISP's resolvers. Non-destructive: the API keeps your servers.
await client.clear_custom_dns(family="ipv6", network_id=None)  # one family
await client.clear_custom_dns(network_id=None)                 # both

# Re-enable the stored servers without resupplying them.
await client.set_dns_mode("custom", network_id=None)
```

Reading the result:

```python
data = (await client.get_dns_settings())["data"]

data["dns"]["mode"]                     # "custom" | "automatic"
data["dns"]["custom"]["ips"]            # IPv4 servers
data["dns"]["parent"]["ips"]            # the ISP's resolvers
data["dns"]["caching"]                  # bool
data["ipv6"]["name_servers"]["mode"]    # "custom" | "automatic"
data["ipv6"]["name_servers"]["custom"]  # IPv6 servers, fully expanded
```

At most 2 servers per family; more raises `EeroValidationException`, as does a malformed
address or one of the wrong family.

### Provider presets

The SDK deliberately has no built-in provider list. The API serves its own catalogue, which
is authoritative and stays current — build a picker from it rather than hardcoding addresses:

```python
data = (await client.get_dns_settings())["data"]

for provider in data["dns"]["default_test_servers"]:
    print(provider["name"], provider["ipv4"], provider["ipv6"])

chosen = data["dns"]["default_test_servers"][0]
await client.set_custom_dns(chosen["ipv4"] + chosen["ipv6"])
```

> **Note**: `set_ipv6_dns()` was removed in v8.0.0 — it never set IPv6 DNS servers, only
> `ipv6_upstream`, the IPv6 connectivity setting. Use `set_ipv6()` for the connectivity toggle,
> or `set_custom_dns_ipv6()` for IPv6 DNS servers.

### Dynamic DNS

Two parameterless PUTs with no request body — the API declares no fields for either. Both are
unverified. The current state is the network envelope's `ddns` field.

```python
await client.enable_ddns(network_id=None)
await client.disable_ddns(network_id=None)
```

---

## DNS policies (content filtering)

A premium (Eero Plus / Eero Secure) feature. This family owns content filtering, domain
allow/block lists, and per-profile application blocking — the former profile-level methods for
these were removed because a profile has no such fields. Two reads are verified
(`get_advanced_content_filter`, `get_dns_policy_applications`); every write is unverified and
logs the warning. Removal on the list endpoints is expressed with `is_delete=True` on the same
PUT — there is no DELETE verb.

```python
lists = await client.get_advanced_content_filter(network_id=None)   # data: allowed_list / blocked_list

# Network-wide
await client.allow_domain("example.com", add_cname=True, network_id=None)
await client.allow_domain("example.com", is_delete=True, network_id=None)          # remove
await client.allow_cnames(["cdn.example.com"], network_id=None)
await client.block_domain("ads.example", keep_profiles=["<profile-id>"], network_id=None)

# Per profile
await client.allow_domain_for_profiles("example.com", profiles=["<profile-id>"], override=True, network_id=None)
await client.allow_cnames_for_profiles(["cdn.example.com"], profiles=["<profile-id>"], network_id=None)
await client.block_domain_for_profiles("ads.example", profiles=["<profile-id>"], network_id=None)

apps = await client.get_dns_policy_applications("<profile-id>", network_id=None)   # applications / categories_list
await client.set_profile_blocked_applications("<profile-id>", ["<app-id>"], network_id=None)  # replaces the full list
```

**Not exposed:** the network- and profile-level DNS-policy *settings* (the boolean content
category toggles such as `ad_block`, `block_malware`, `safe_search_enabled`) and the ad-block
on/off switches. Neither the network envelope's `premium_dns` field nor its `resources` object,
nor a profile's own `premium_dns` / `resources`, carries a URL for those endpoints, so the SDK
has no link to follow and deliberately does not guess one.

### Subnet content filters

```python
filters = await client.get_subnet_content_filters("<subnet-id>", network_id=None)     # verified read
await client.set_subnet_content_filters({"content_filters": {...}, "subnets": [...]}, network_id=None)  # forwarded unchanged; unverified
```

---

## SQM / QoS

SQM is one boolean on the network's `settings` link, written as the `sqm` query parameter with
no body. There are no bandwidth or "auto" variants — the API declares none.

```python
sqm = await client.get_sqm_settings(network_id=None)     # the network envelope; look at data["sqm"]
await client.set_sqm(True, network_id=None)              # settings-class: may reboot the mesh; read-compare-skip
```

---

## Security

```python
security = await client.get_security_settings(network_id=None)
await client.set_wpa3(enabled=True, network_id=None)
await client.set_band_steering(enabled=True, network_id=None)
await client.set_upnp(enabled=False, network_id=None)
await client.set_ipv6(enabled=True, network_id=None)
await client.configure_security(wpa3=True, band_steering=True, upnp=False, ipv6=True, network_id=None)
```

These write the same `settings` link as DNS; treat them as settings-class.

### Per-band WPA3, MLO, fast transition, Passpoint, proxied nodes

```python
bands = await client.get_wpa3_per_band(network_id=None)                          # verified read
await client.set_wpa3_per_band(network_id=None, band_2_4_ghz="WPA2_WPA3", band_5_ghz="WPA3")  # values: WPA2 | WPA2_WPA3 | WPA3

await client.set_mlo_mode("multi", network_id=None)        # "disabled" | "single" | "multi"; settings-class

ft = await client.get_fast_transition(network_id=None)     # verified read
await client.set_fast_transition(True, network_id=None)    # JSON {"fast_transition": bool}

await client.set_passpoint_enabled(True, network_id=None)  # JSON {"enabled": bool} to passpoint/enabled
await client.set_proxied_nodes(True, network_id=None)      # JSON {"enabled": bool} to proxied_nodes
```

Every write here is unverified; `set_wpa3_per_band` may also require devices to reconnect when
their negotiated mode is no longer offered.

---

## Thread

```python
thread = await client.get_thread(network_id=None)
await client.set_thread_enabled(True, network_id=None)                  # JSON {"enabled": bool} PUT to networks/{id}/thread
await client.update_thread(thread_enable=True, enable_credential_syncing=False, network_id=None)
await client.regenerate_thread_credentials(network_id=None)            # POST ""
```

All three writes are unverified.

---

## DHCP, connection mode, NAT, PPPoE

All settings-class (may reboot the mesh) except `set_pppoe`, which is unverified.

```python
await client.set_dhcp(network_id=None, mode="manual", custom={"start_ip": "192.168.4.10", "end_ip": "192.168.4.200", "subnet_ip": "192.168.4.0", "subnet_mask": "255.255.255.0"})
await client.set_dhcp(network_id=None, custom_v2={"main": {...}, "guest": {...}})   # keys: main, guest, subnetA, subnetB, supernet
await client.set_connection_mode("BRIDGE", network_id=None)        # "BRIDGE" | "NAT"
await client.set_nat_port_randomization(True, network_id=None)

# PPPoE credentials are encrypted by the eero; the response carries the blob the API expects
# back on a later DHCP/connection write. The SDK does not interpret or forward it.
blob = await client.set_pppoe("<eero-serial>", username="<user>", password="<password>")
```

`set_dhcp` raises `EeroValidationException` for a `mode` other than `"automatic"` / `"manual"`,
when no field is supplied, or when `custom` / `custom_v2` carry a key the API does not declare.

---

## Backup Internet

```python
backup = await client.get_backup_internet(network_id=None)
await client.set_backup_internet(True, network_id=None)          # JSON {"backup_internet_enabled": bool}; unverified
usage = await client.get_cellular_backup_usage(network_id=None)
events = await client.get_cellular_backup_events(network_id=None)
```

### Backup access points (backup Wi-Fi networks)

`list` and `discover_backup_ssids` are verified reads; every write is unverified. The password
is never logged.

```python
aps = await client.list_backup_access_points(network_id=None)
await client.add_backup_access_point(network_id=None, ssid="<ssid>", password="<password>")
await client.update_backup_access_point("<backup-network-id>", network_id=None, enabled=False)
await client.delete_backup_access_point("<backup-network-id>", network_id=None)
await client.rearrange_backup_access_points(["<id-1>", "<id-2>"], network_id=None)   # {"rearranged_ids": [...]}

scan = await client.discover_backup_ssids(network_id=None)
await client.start_backup_ssid_discovery(network_id=None)   # POST ""
await client.backup_connectivity_check(network_id=None)     # POST ""
```

---

## LEDs & Nightlight

```python
led = await client.get_led_status(eero_id, network_id=None)    # led_on / led_brightness on the eero envelope
await client.set_led(eero_id, enabled=False, network_id=None)          # form-encoded led_on to the eero's led_action link
await client.set_led_brightness(eero_id, brightness=50, network_id=None)  # form-encoded led_brightness; 0-100
await client.led_cycle("<eero-serial>", colors=["red", "blue"], duration="<duration>", time_per_color="<time>")  # form-encoded colors[]
```

> ⚠️ The pre-v8.0.0 `set_led` write (a JSON body to the eero's own URL) was verified to change
> nothing — any caller who "successfully" set the LED through this SDK never did. The
> form-encoded write to the `led_action` link is the shape the API declares and was verified
> live on 2026-09-20: the node's light went off and back on, the app agreed, and no node
> rebooted. `set_led_brightness` uses the same link and was live-verified the same day: the
> node's brightness changed and the read-back matched, with no reboot. Read `get_led_status`
> first and skip when it already matches.

The nightlight (Beacon only) is its own sub-resource at `data.nightlight.url` on the eero
envelope; it accepts exactly `enabled`, `brightness_percentage`, and `schedule`. An eero without
a nightlight raises `EeroFeatureUnavailableException`.

```python
nightlight = await client.get_nightlight(eero_id, network_id=None)
await client.set_nightlight(eero_id, enabled=True, brightness_percentage=30, schedule={...}, network_id=None)  # schedule forwarded unchanged
await client.set_nightlight_brightness(eero_id, 30, network_id=None)
await client.set_nightlight_schedule(eero_id, {...}, network_id=None)
await client.nightlight_override(eero_id, brightness_percentage=80, network_id=None)   # preview; form-encoded POST
```

---

## Updates

```python
updates = await client.get_updates(network_id=None)
await client.apply_update(network_id=None)   # POST ""; reboots every node; read get_updates first and only apply when one is pending
```

---

## Power saving

```python
await client.set_power_saving(network_id=None, enable=True, power_saving_schedule_enabled=True)   # settings-class

schedules = await client.get_power_saving_schedules(network_id=None)   # verified read
await client.create_power_saving_schedule(network_id=None, name="Night", days=[...], start_time="23:00", end_time="06:00")
await client.update_power_saving_schedule("<schedule-id>", network_id=None, enabled=False)
await client.delete_power_saving_schedule("<schedule-id>", network_id=None)
```

---

## Subnets

```python
config = await client.get_subnets_config(network_id=None)          # verified read
await client.set_subnets_config({...}, network_id=None)            # SubnetConfig forwarded unchanged; settings-class
await client.delete_subnet("<subnet-type>", network_id=None)       # settings-class
```

Declared `SubnetConfig` fields: `dedicated_subnet`, `enabled`, `open_network`, `name`,
`network_id`, `password`, `rate_limit_pct`, `subnet_id`, `subnet_kind`, `subnet_type`,
`wan_access`. The SDK validates none of them.

---

## Multi-static IP and secondary WAN (API 2.3)

This family is served on API version `2.3` only.

```python
msip = await client.get_multistaticip(network_id=None)   # verified read; EeroNotFoundException (error.network.multistaticip_not_found) without the feature
await client.set_multistaticip({"enabled": True, "type": "...", "multistaticip_settings": {...}}, network_id=None)   # settings-class

await client.set_secondary_wan_config({"devices": [{"mac": "<mac>", "secondary_wan_deny_access": True}]}, network_id=None)  # settings-class
await client.set_device_secondary_wan_access("<mac>", deny=True, network_id=None)   # PUT devices/{mac} on 2.3; settings-class
```

---

## Entitlements

Verified reads. The SDK returns the envelopes as-is and makes no attempt to interpret premium
status — that belongs to the caller.

```python
features = await client.get_entitlement_features(network_id=None)   # GET entitlements/networks/{id}/features
upsell = await client.get_upsell_features(network_id=None)          # GET entitlements/networks/{id}/upsell_features
caps = await client.get_model_capabilities(network_id=None)         # GET eero_models/capabilities?networkId=<id> (bare ID only)
customer = await client.get_premium_customer()                      # GET premium/customer
```

---

## Events, scans, and channel utilisation

Verified reads; `get_channel_utilization` is verified with `start` / `end` only, the optional
parameters follow the API's declared shape. None are cached.

```python
events = await client.get_app_events(network_id=None, page_size=50, timestamp=None)   # timestamp = pagination cursor
scan = await client.get_network_scan(network_id=None)
util = await client.get_channel_utilization(
    network_id=None,
    start="2026-07-01T00:00:00Z", end="2026-07-02T00:00:00Z",
    band="band_5GHz_full",        # band_2_4GHz | band_5GHz_low | band_5GHz_high | band_5GHz_full | band_6GHz
    granularity=15,               # integer minutes per sample — the API rejects strings
    busy_threshold=None, eero_id=None, gap_data_placeholder=None,
)
```

An invalid `band`, or a non-positive `granularity` / `busy_threshold`, raises
`EeroValidationException` locally.

---

## Permissions and members

```python
perms = await client.get_permissions(network_id=None)     # verified read: permissions map + role
members = await client.get_members(network_id=None)       # verified read

invites = await client.get_invites(network_id=None)       # unverified read — access denied on some accounts
await client.create_invite(role="admin", network_id=None)              # "owner" | "admin"
await client.update_invite("<invite-id>", invite_nickname="<name>", network_id=None)
await client.delete_invite("<invite-id>", network_id=None)
await client.respond_to_invite(accept=True, invite_id="<invite-id>", network_id=None)     # or invite_code=; exactly one
await client.cancel_pending_admin(network_id=None)                     # POST ""
await client.promote_member("<member-id>", network_id=None)
await client.remove_admin("<user-id>", network_id=None)
lookup = await client.query_invite("<invite-code>")                    # not network-scoped; the code is never logged
```

Every member/invite write is unverified.

---

## Notifications

```python
settings = await client.get_notification_settings(network_id=None)   # one boolean per event key, e.g. "device.new"
await client.set_notification_settings({"device.new": True, "network.updated": False}, network_id=None)  # sent as-is; keys keep their dots
unread = await client.has_unread_notifications(network_id=None)      # data["has_unread"]
await client.mark_notifications_read(network_id=None)                # POST ""
history = await client.get_notification_history(network_id=None, timestamp=None)
await client.set_push_settings({"networkOffline": True, "nodeOffline": True})   # account-level; not network-scoped
```

The two writes are unverified; the SDK enforces no closed set of keys on either mapping.

---

## Stats & Usage

```python
transfer = await client.get_transfer_stats(network_id=None, device_id=None)

# start / end / cadence are keyword-only and required by the API; sent as query parameters.
usage = await client.get_data_usage(
    network_id=None,
    start="2026-07-01T00:00:00Z",
    end="2026-07-21T00:00:00Z",
    cadence="daily",          # or "hourly"
    timezone="UTC",           # optional IANA name
)
```

The rest of the data-usage family is on `EeroClient` too — `network_id` is the usual trailing
optional keyword (no auto-discovery), and the window arguments are keyword-only. None of these
reads are cached:

```python
window = {"start": "2026-07-01T00:00:00Z", "end": "2026-07-21T00:00:00Z"}

await client.get_data_usage_breakdown(**window)
await client.get_devices_data_usage(**window, profile_id="<profile-id>")
await client.get_device_data_usage("<mac>", **window, cadence="hourly")
await client.get_eeros_data_usage_summary(**window, cadence="daily")
await client.get_eero_data_usage("<eero-id>", **window, cadence="daily")
await client.get_profile_data_usage("<profile-id>", **window, cadence="daily")
await client.get_unprofiled_devices_data_usage(**window)
await client.get_unprofiled_data_usage_summary(**window, cadence="daily")

settings = await client.get_data_usage_report_settings()
```

`cadence` is required by the API on `get_data_usage`, `get_device_data_usage`,
`get_eeros_data_usage_summary`, `get_eero_data_usage`, `get_profile_data_usage`, and
`get_unprofiled_data_usage_summary`; it is optional on the others and omitted from the request
when not given. A value other than `"daily"` / `"hourly"` raises `EeroValidationException`
before any request.

> ⚠️ **Warning:** `set_data_usage_report_settings(*, cadence, notification_day, network_id=None)`
> is an **unverified write** — read `get_data_usage_report_settings` first, write only when the
> stored values differ, and never retry it. It invalidates that network's cache entry.

> **Note**: `get_burst_reporters()` was removed in v8.0.0 — the endpoint returns 404; the
> resource is POST-only. `client._api.burst_reporters.create_burst_reporter(...)` remains
> available.

### Insights

`get_insights` takes `start`, `end`, `insight_type` (required, keyword-only) and `cadence`
(default `"daily"`). The per-device and per-profile series — all verified reads — take the
same window plus a required `cadence` (`"daily"` / `"hourly"`):

```python
window = {"start": "2026-07-01T00:00:00Z", "end": "2026-07-21T00:00:00Z", "insight_type": "blocked"}

await client.get_insights(network_id=None, **window, cadence="daily")
await client.get_devices_insights(network_id=None, **window, cadence="daily")
await client.get_device_insights("<mac>", network_id=None, **window, cadence="daily")
await client.get_profiles_insights(network_id=None, **window, cadence="daily")
await client.get_profile_insights("<profile-id>", network_id=None, **window, cadence="daily")
await client.get_profile_devices_insights("<profile-id>", network_id=None, **window, cadence="daily")
```

Unlike most `EeroClient` methods, none of these auto-discover `network_id` — pass it explicitly
or set a preferred network first (see [Network Targeting](Network-Targeting)).

---

## Blacklist

```python
blacklist = await client.get_blacklist(network_id=None)
```

`block_device` / `unblock_device` (above) are the facade's add/remove; the domain
`BlacklistAPI.add_to_blacklist` / `remove_from_blacklist` are what they delegate to.

---

## OUI Check

The API requires `serial` and `version` query parameters identifying the eero being checked and
returns `404` without them; both are keyword-only and required. Take them from an eero envelope:

```python
result = await client.get_ouicheck(
    network_id=None,
    serial="<eero-serial>",    # the eero's serial number, as returned in its envelope
    version="<eero-version>",  # the eero's version string, as returned in its envelope
)
```

Empty or non-string values raise `EeroValidationException` before any request.

---

## Removed Surface

> ⚠️ **Warning:** v8.0.0 removed `set_device_priority`, the `ActivityAPI` passthroughs,
> `set_ipv6_dns`, the SQM bandwidth/auto variants, the four `*backup_network` methods, the
> profile schedule array methods, and the profile content-filter / block-list /
> blocked-applications methods. See [Deprecations](Deprecations) for the full list with
> replacements and [Migration](Migration#v7x--v800) for before/after code.

---

## Error Handling

All exceptions derive from `EeroException`, end in `...Exception` (not `...Error`), and are importable from the package root: `EeroAuthenticationException` (every 401), `EeroRateLimitException`, `EeroNetworkException`, `EeroTimeoutException`, `EeroValidationException` (client-side validation **and** API 400 form errors — not an `EeroAPIException`), and `EeroAPIException` with its subclasses `EeroNotFoundException` (every 404), `EeroAccessDeniedException` (403 + `error.access.denied`), `EeroPremiumRequiredException`, `EeroFeatureUnavailableException`, and `EeroClientBlockedException`.

The class is chosen from the HTTP status first and the API's `meta.error` catalogue string second. Every exception carries `envelope` (the raw response envelope, or `None`) and `error_code` (`meta.error`, or `None`); the message is only the status plus the recognised catalogue string (or `unrecognised error string`) — never the body. Branch on the class or on `error_code`, not on `str(err)`.

```python
from eero import (
    EeroAPIException,
    EeroAuthenticationException,
    EeroException,
    EeroNotFoundException,
)

try:
    await client.get_network(network_id="<network-id>")
except EeroAuthenticationException as err:
    print(f"Session rejected ({err.error_code}) — log in again")
except EeroNotFoundException:
    print("No such network")
except EeroAPIException as err:
    print(f"API error {err.status_code}: {err.error_code}")
except EeroException as err:
    print(f"Request failed: {err.error_code or err}")
```

Full hierarchy and per-exception guidance: [Error Handling](Error-Handling).

---

## Caching

`EeroClient` keeps a `cache_timeout`-second in-memory cache (default 60s) for read methods that accept `refresh_cache`. Pass `refresh_cache=True` to bypass it for a single call, or call `client.clear_cache()` to drop everything. The cached network, eero, and device envelopes are also what the facade passes as `parent=` to the domain methods.

```python
await client.get_networks(refresh_cache=True)
client.clear_cache()
```

Details on which methods are cached, which writes invalidate what, and rate-limit behaviour: [Caching and Rate Limits](Caching-and-Rate-Limits).

---

## Utilities

`id_from_url` is exported from the top-level `eero` package and extracts the trailing ID segment from an API URL fragment or bare ID:

```python
from eero import id_from_url

id_from_url("/2.2/networks/<network-id>/profiles/<profile-id>")  # -> "<profile-id>"
id_from_url("<network-id>")                                      # -> "<network-id>"
```

The link-resolution helpers `resolve_link`, `self_url`, `resource_url`, `sub_resource_url`, and
`join_api_path` are exported alongside it — see
[Network Targeting](Network-Targeting#the-link-helpers).

---

## The Lower-Level `EeroAPI`

`EeroClient` is a facade over `EeroAPI`, a composition-based aggregator exposing the same domain APIs directly (`api.devices`, `api.profiles`, `api.security`, `api.dns_policies`, `api.wan`, etc.) without caching or auto-discovery. Use it when you need domain-level control; pass `network_id` explicitly to every call, and pass `parent=` yourself when you hold the envelope. Full method inventory: [API Reference](API-Reference).

---

## 🔗 Related Pages

- [Home](Home) — Wiki overview and quick links
- [Configuration](Configuration) — Auth storage & settings
- [Authentication](Authentication) — Login/verify flow and session persistence
- [Raw Response Format](Raw-Response-Format) — Envelope shape, extraction patterns, and the `resources` links
- [Error Handling](Error-Handling) — Full exception hierarchy and handling patterns
- [Caching and Rate Limits](Caching-and-Rate-Limits) — Cache TTLs, invalidation, and which writes may reboot the mesh
- [Network Targeting](Network-Targeting) — How `network_id` resolution works; IDs, paths, URLs and `parent=`
- [API Reference](API-Reference) — Full per-domain method inventory with verified/unverified status
- [Examples](Examples) — End-to-end runnable scripts
- [Troubleshooting](Troubleshooting) — Common issues & fixes
