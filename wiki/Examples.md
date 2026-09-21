# 💡 Examples

Complete, runnable scripts covering the workflows people actually build against this SDK.

---

## First-Time Login

Interactive OTP login that persists the session to the OS keyring (or file fallback) for next time.

```python
"""First-time login: request an OTP, verify it, and persist the session."""

import asyncio

from eero import EeroClient, EeroAuthenticationException, EeroValidationException


async def main() -> None:
    async with EeroClient(use_keyring=True) as client:
        if client.is_authenticated:
            print("Already authenticated — nothing to do.")
            return

        identifier = input("Email or phone number: ").strip()
        try:
            await client.login(identifier)
        except EeroAuthenticationException as err:
            print(f"Login request failed: {err}")
            return

        code = input("Verification code sent by Eero: ").strip()
        try:
            await client.verify(code)
        except (EeroAuthenticationException, EeroValidationException) as err:
            print(f"Verification failed: {err}")
            return

        print("Logged in — session token stored via keyring/file fallback.")


asyncio.run(main())
```

> **Note**: `client.is_authenticated` is a property — never `await` it. See [Authentication](Authentication).

---

## Network Inventory Dump

The canonical "does it work" script: account → networks → eeros → devices, printed as a tree.

```python
"""Print account -> networks -> eeros -> devices as a readable tree."""

import asyncio

from eero import EeroClient, EeroException, id_from_url


def as_list(response: dict, key: str | None = None) -> list:
    """Pull a list of resources out of an Eero response envelope.

    See the wiki's Raw Response Format page — get_networks() can return the
    network list as a bare list, under "networks", or nested one level deeper.
    """
    data = response.get("data") or {}
    if isinstance(data, list):
        return data
    items = data.get(key) if key else None
    if items is None:
        items = data.get("data") or []
    if isinstance(items, dict):
        items = items.get("data") or []
    return items if isinstance(items, list) else []


async def main() -> None:
    async with EeroClient() as client:
        if not client.is_authenticated:
            print("Not authenticated — run the login example first.")
            return

        account = await client.get_account()
        email = account.get("data", {}).get("email", {}).get("address", "unknown")
        print(f"Account: {email}")

        networks = as_list(await client.get_networks(), "networks")

        for network in networks:
            network_id = id_from_url(network["url"])
            print(f"\n📶 {network.get('name', network_id)} ({network.get('status', 'unknown')})")

            try:
                eeros = (await client.get_eeros(network_id=network_id)).get("data", [])
            except EeroException as err:
                print(f"  ⚠️ Could not fetch eeros: {err}")
                continue

            for eero in eeros:
                tag = "gateway" if eero.get("gateway") else "eero"
                print(
                    f"  📡 [{tag}] {eero.get('location', '?')} — "
                    f"{eero.get('model', '?')} ({eero.get('status', '?')})"
                )

            devices = (await client.get_devices(network_id=network_id)).get("data", [])
            for device in devices:
                name = device.get("nickname") or device.get("hostname") or device.get("mac", "?")
                state = "connected" if device.get("connected") else "offline"
                print(f"      - {name} [{state}]")


asyncio.run(main())
```

> **Note**: See [Raw Response Format](Raw-Response-Format) for why `get_networks()` needs this normalization.

---

## Find a Device by Name or MAC

Iterate devices and match on nickname, hostname, or MAC — every field is read with `.get()` since presence varies per device type.

```python
"""Search connected devices by nickname, hostname, or MAC address."""

import asyncio
import sys
from typing import Any, Optional

from eero import EeroClient


async def find_device(client: EeroClient, query: str) -> Optional[dict[str, Any]]:
    response = await client.get_devices()
    query_lower = query.lower()

    for device in response.get("data", []):
        nickname = (device.get("nickname") or "").lower()
        hostname = (device.get("hostname") or "").lower()
        mac = (device.get("mac") or "").lower()

        if query_lower in (nickname, hostname, mac):
            return device

    return None


async def main() -> None:
    query = sys.argv[1] if len(sys.argv) > 1 else input("Nickname, hostname, or MAC: ")

    async with EeroClient() as client:
        device = await find_device(client, query)

        if device is None:
            print(f"No device matched {query!r}")
            return

        print(f"Nickname:     {device.get('nickname', '(none)')}")
        print(f"Hostname:     {device.get('hostname', '(unknown)')}")
        print(f"MAC:          {device.get('mac', '(unknown)')}")
        print(f"IP:           {device.get('ip', '(unknown)')}")
        print(f"Connected:    {device.get('connected', False)}")
        print(f"Wireless:     {device.get('wireless', False)}")
        print(f"Manufacturer: {device.get('manufacturer', '(unknown)')}")


asyncio.run(main())
```

---

## Pause and Resume a Profile

Look up a profile by name, pause it, wait, then resume it — with the resume guaranteed via `finally`.

```python
"""Pause a profile by name, wait, then resume it."""

import asyncio
from typing import Optional

from eero import EeroClient, id_from_url


async def find_profile_id(client: EeroClient, name: str) -> Optional[str]:
    response = await client.get_profiles()
    for profile in response.get("data", []):
        if profile.get("name") == name:
            return id_from_url(profile["url"])
    return None


async def main() -> None:
    async with EeroClient() as client:
        profile_id = await find_profile_id(client, "Kids")
        if profile_id is None:
            print("Profile 'Kids' not found")
            return

        try:
            await client.pause_profile(profile_id, True)
            print("Paused. Waiting 30 seconds...")
            await asyncio.sleep(30)
        finally:
            await client.pause_profile(profile_id, False)
            print("Resumed.")


asyncio.run(main())
```

> ⚠️ **Warning:** `pause_profile(profile_id, paused, network_id=None)` — `network_id` is a trailing kwarg. Never call `pause_profile(network_id, True)`; see [Network Targeting](Network-Targeting).

---

## Speed Test and Report

Trigger a speed test, wait for the result to land, and read it from the history.

```python
"""Run a speed test and print the download/upload results."""

import asyncio

from eero import EeroClient, EeroException


async def main() -> None:
    async with EeroClient() as client:
        try:
            await client.run_speed_test()   # 202 with data: null; the result is not in this response
        except EeroException as err:
            print(f"Speed test failed: {err}")
            return

        await asyncio.sleep(90)              # the result lands in the history about a minute later
        history = await client.get_speed_tests(limit=1)
        data = history.get("data") or []
        latest = data[0] if isinstance(data, list) and data else {}
        down = latest.get("down") or {}
        up = latest.get("up") or {}
        print(f"Download: {down.get('value')} {down.get('units', 'Mbps')}")
        print(f"Upload:   {up.get('value')} {up.get('units', 'Mbps')}")


asyncio.run(main())
```

---

## Reserve a DHCP Address and Open a Port Forward

Created, then listed, then cleaned up. Reservations and forwards never auto-discover a network, so `network_id` must be explicit. A reservation body has exactly `description`, `ip`, `mac`, `public_static_ip`; a forward body has exactly `client_port`, `description`, `enabled`, `gateway_port`, `ip`, `protocol` — the SDK passes both through unchanged.

```python
"""Reserve a DHCP address and open a port forward, then list and clean both up."""

import asyncio

from eero import EeroClient, EeroException, id_from_url


def as_list(response: dict, key: str | None = None) -> list:
    """See Raw Response Format — the networks list has several shapes."""
    data = response.get("data") or {}
    if isinstance(data, list):
        return data
    items = data.get(key) if key else None
    if items is None:
        items = data.get("data") or []
    if isinstance(items, dict):
        items = items.get("data") or []
    return items if isinstance(items, list) else []


async def main() -> None:
    async with EeroClient() as client:
        networks = as_list(await client.get_networks(), "networks")
        if not networks:
            print("No networks on this account.")
            return
        network_id = id_from_url(networks[0]["url"])

        reservation_data = {"mac": "<mac>", "ip": "192.168.4.200", "description": "NAS"}
        forward_data = {
            "ip": "192.168.4.200",
            "client_port": 8080,
            "gateway_port": 8080,
            "protocol": "tcp",
            "enabled": True,
            "description": "web",
        }

        try:
            await client.create_reservation(reservation_data, network_id=network_id)
            await client.create_forward(forward_data, network_id=network_id)
        except EeroException as err:
            print(f"Failed to create rule: {err}")
            return

        reservations = (await client.get_reservations(network_id=network_id)).get("data", [])
        forwards = (await client.get_forwards(network_id=network_id)).get("data", [])
        print(f"Reservations: {len(reservations)}  Forwards: {len(forwards)}")

        # Clean up: find what we just created by the fields we set, then delete it.
        # delete_forwards=True asks the API to drop forwards that reference the
        # reservation's IP as well, so the forward below may already be gone.
        for reservation in reservations:
            if reservation.get("ip") == reservation_data["ip"]:
                await client.delete_reservation(
                    id_from_url(reservation["url"]), network_id=network_id, delete_forwards=True
                )
                break

        for forward in (await client.get_forwards(network_id=network_id)).get("data", []):
            if forward.get("gateway_port") == forward_data["gateway_port"]:
                await client.delete_forward(id_from_url(forward["url"]), network_id=network_id)
                break


asyncio.run(main())
```

---

## Nightly Monitoring Scrape

A loop suited to a cron job or exporter: a high `cache_timeout`, exponential backoff on `EeroRateLimitException`/`EeroTimeoutException`, one metrics line per node.

```python
"""Cron/exporter-friendly scrape loop with backoff on rate limits and timeouts."""

import asyncio

from eero import EeroClient, EeroRateLimitException, EeroTimeoutException, id_from_url


def as_list(response: dict, key: str | None = None) -> list:
    """See Raw Response Format — the networks list has several shapes."""
    data = response.get("data") or {}
    if isinstance(data, list):
        return data
    items = data.get(key) if key else None
    if items is None:
        items = data.get("data") or []
    if isinstance(items, dict):
        items = items.get("data") or []
    return items if isinstance(items, list) else []


async def scrape_once(client: EeroClient) -> None:
    for network in as_list(await client.get_networks(), "networks"):
        network_id = id_from_url(network["url"])
        eeros = (await client.get_eeros(network_id=network_id)).get("data", [])

        for eero in eeros:
            print(
                f'eero_status{{network="{network_id}",location="{eero.get("location", "?")}"}} '
                f'clients={eero.get("connected_clients_count", 0)} '
                f'status="{eero.get("status", "unknown")}"'
            )


async def main() -> None:
    # A 300s cache lets a 60s scrape loop stay well under the ~100 req/min ceiling.
    async with EeroClient(cache_timeout=300) as client:
        backoff = 1
        while True:
            try:
                await scrape_once(client)
                backoff = 1
            except (EeroRateLimitException, EeroTimeoutException) as err:
                print(f"Backing off {backoff}s after {type(err).__name__}: {err}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue

            await asyncio.sleep(60)


asyncio.run(main())
```

> 💡 **Tip:** See [Caching and Rate Limits](Caching-and-Rate-Limits) for why a long `cache_timeout` is the first line of defense against `EeroRateLimitException`.

---

## Headless / CI Session Reuse

Seed a session token from the caller's own environment variable — no interactive OTP flow required.

```python
"""Headless / CI: seed a session token from an environment variable, use it, clear it."""

import asyncio
import os

from eero import EeroClient, EeroAuthenticationException, EeroValidationException


async def main() -> None:
    token = os.environ.get("EERO_SESSION_TOKEN")
    if not token:
        raise SystemExit("EERO_SESSION_TOKEN is not set")

    # No cookie_file: deliberately ephemeral (MemoryStorage) — the token is re-seeded from
    # EERO_SESSION_TOKEN on every run and explicitly cleared in `finally` below, so there is
    # nothing to persist across invocations. If you need the session to survive between runs,
    # pass cookie_file=<path> instead (see Credential-Storage wiki page).
    async with EeroClient(use_keyring=False) as client:
        try:
            await client.set_session_token(token)
        except EeroValidationException as err:
            raise SystemExit(f"Invalid session token: {err}")

        try:
            account = await client.get_account()
            print(account.get("data", {}).get("email", {}).get("address"))
        except EeroAuthenticationException:
            print("Session token is expired or invalid.")
        finally:
            await client.clear_session_token()


asyncio.run(main())
```

> **Note**: The SDK itself reads no environment variables — `EERO_SESSION_TOKEN` here is read by this script, then handed to the SDK via `set_session_token()`.

---

## Guest Network Rotation

Read the guest network config, enable it if needed, set a new password, and read it back.
The password is its own resource (`set_guest_password`), separate from the enable/name write.
Both writes are live-verified (2026-09-20) and log no warning, but they still disconnect guest clients while they take effect — read first and skip when the state already matches.

```python
"""Read the guest network config, rotate its password, and read the result back."""

import asyncio
import secrets

from eero import EeroClient, EeroException, id_from_url


async def main() -> None:
    async with EeroClient() as client:
        network = await client.get_network(refresh_cache=True)   # cached; becomes parent= below
        network_id = id_from_url(network["data"]["url"])

        guest = (await client.get_guest_network(network_id=network_id)).get("data", {})
        print(f"Guest network {guest.get('name', '(unnamed)')} enabled={guest.get('enabled', False)}")

        try:
            if not guest.get("enabled"):
                # Read-compare-skip: only write when the state differs.
                await client.set_guest_network(enabled=True, network_id=network_id)

            await client.set_guest_password(secrets.token_urlsafe(12), network_id=network_id)
        except EeroException as err:
            print(f"Failed to rotate guest password: {err}")
            return

        # A 200 proves the request was accepted, not that the change settled — read back.
        updated = (await client.get_guest_network(network_id=network_id)).get("data", {})
        print(f"Rotated. Guest network now enabled={updated.get('enabled', False)}")


asyncio.run(main())
```

---

## Dual-Stack Custom DNS

Configure all four slots the eero app exposes — IPv4 primary/secondary and IPv6
primary/secondary — then verify the write actually landed.

> **⚠️ A DNS write reboots every eero on the network.** This example compares before writing
> and skips the write when the configuration already matches, which is what you want in
> anything scheduled — otherwise each run reboots the network.

```python
import asyncio
import ipaddress

from eero import EeroClient, id_from_url
from eero.exceptions import EeroValidationException


def as_list(response: dict, key: str | None = None) -> list:
    """See Raw Response Format — the networks list has several shapes."""
    data = response.get("data") or {}
    if isinstance(data, list):
        return data
    items = data.get(key) if key else None
    if items is None:
        items = data.get("data") or []
    if isinstance(items, dict):
        items = items.get("data") or []
    return items if isinstance(items, list) else []


def same_address(a: str, b: str) -> bool:
    """Compare IP literals by value.

    The API stores IPv6 fully expanded, so "2606:4700:4700::1111" reads back as
    "2606:4700:4700:0:0:0:0:1111". String comparison would report a false mismatch.
    """
    return ipaddress.ip_address(a) == ipaddress.ip_address(b)


async def main() -> None:
    wanted = [
        "1.1.1.1", "1.0.0.1",
        "2606:4700:4700::1111", "2606:4700:4700::1001",
    ]

    async with EeroClient() as client:
        # DNS methods use auto_discover=False, so resolve the network first and
        # pass network_id= explicitly — a bare call raises EeroException.
        networks = as_list(await client.get_networks(), "networks")
        network_id = id_from_url(networks[0]["url"])

        # Compare before writing — a DNS write reboots the whole mesh, so an
        # unconditional write in a scheduled job means a reboot every run.
        data = (await client.get_dns_settings(network_id=network_id))["data"]
        current = data["dns"]["custom"]["ips"] + data["ipv6"]["name_servers"]["custom"]

        already_set = len(current) == len(wanted) and all(
            any(same_address(a, b) for b in current) for a in wanted
        )
        if already_set:
            print("Already configured — skipping the write.")
            return

        try:
            await client.set_custom_dns(wanted, network_id=network_id)
        except EeroValidationException as exc:
            print(f"Rejected before sending: {exc}")
            return

        # get_dns_settings is never cached, so this read is always fresh.
        data = (await client.get_dns_settings(network_id=network_id))["data"]
        live = data["dns"]["custom"]["ips"] + data["ipv6"]["name_servers"]["custom"]

        for address in wanted:
            ok = any(same_address(address, seen) for seen in live)
            print(f"{'OK ' if ok else 'MISSING'}  {address}")

        print(f"IPv4 mode: {data['dns']['mode']}")
        print(f"IPv6 mode: {data['ipv6']['name_servers']['mode']}")


asyncio.run(main())
```

Reading back and comparing is worth the few extra lines: the eero API accepts unrecognised
fields with `200 OK` and silently discards them, so a success response on its own does not
prove a write took effect.

### Switch one family back to the ISP resolvers

Clearing is non-destructive — the API keeps the stored servers rather than erasing them, so
they still appear in `dns.custom.ips` while the mode is `automatic`. Switching back is a mode
flip; you do not need to resupply the addresses.

```python
async with EeroClient() as client:
    # ...resolve network_id as above...

    # Off — falls back to the ISP resolvers. IPv4 untouched.
    await client.clear_custom_dns(family="ipv6", network_id=network_id)

    # On again, reusing whatever the network already stores.
    await client.set_dns_mode("custom", network_id=network_id)

    # Pass addresses only when you want to change them.
    await client.set_custom_dns_ipv6(["2001:4860:4860::8888"], network_id=network_id)
```

This makes a "pause custom DNS" toggle straightforward — clear to fall back, `set_dns_mode`
to restore, with no need to stash the addresses client-side.

---

## Read-Compare-Skip for a Settings-Class Write

Every settings-class write (SQM, DHCP, connection mode, MLO, per-band WPA3, and the rest listed
in [Python API — Writes and safety](Python-API#writes-and-safety)) may reboot the entire mesh,
and every one of them is unverified against a live network. The only safe shape for automation
is: read, compare, write only on a difference, never retry, and don't expect the read-back to
reflect the change immediately.

```python
"""Enable SQM only if it is not already enabled — the pattern for every settings-class write."""

import asyncio

from eero import EeroClient, EeroException


async def main() -> None:
    async with EeroClient() as client:
        network = await client.get_network(network_id="<network-id>", refresh_cache=True)
        current = network.get("data", {}).get("sqm")

        if current is True:
            print("SQM already enabled — skipping the write (no reboot).")
            return

        try:
            # Logs one WARNING (unverified, settings-class), then PUTs ?sqm=true to the
            # network's settings link. Never wrap this in a retry loop: a burst of writes
            # queues a burst of reboots.
            await client.set_sqm(True, network_id="<network-id>")
        except EeroException as err:
            print(f"Write rejected: {err.error_code or err}")
            return

        print("Accepted. The change — and any reboot — lands minutes later; check back then.")


asyncio.run(main())
```

---

## Data Usage Breakdown

Per-category usage for the last seven days. The data-usage reads take query parameters only,
are never cached, and never auto-discover a network.

```python
"""Print the network's data-usage breakdown for the last seven days."""

import asyncio
from datetime import datetime, timedelta, timezone

from eero import EeroClient, EeroException, id_from_url


def as_list(response: dict, key: str | None = None) -> list:
    """See Raw Response Format — the networks list has several shapes."""
    data = response.get("data") or {}
    if isinstance(data, list):
        return data
    items = data.get(key) if key else None
    if items is None:
        items = data.get("data") or []
    if isinstance(items, dict):
        items = items.get("data") or []
    return items if isinstance(items, list) else []


async def main() -> None:
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=7)

    async with EeroClient() as client:
        networks = as_list(await client.get_networks(), "networks")
        network_id = id_from_url(networks[0]["url"])

        try:
            breakdown = await client.get_data_usage_breakdown(
                network_id=network_id,
                start=start.isoformat().replace("+00:00", "Z"),
                end=end.isoformat().replace("+00:00", "Z"),
                cadence="daily",       # optional here; omitted from the request when None
                timezone="UTC",
            )
        except EeroException as err:
            print(f"Breakdown failed: {err.error_code or err}")
            return

        # The envelope is returned unmodified; walk whatever the API put under data.
        data = breakdown.get("data", {})
        for key, value in (data.items() if isinstance(data, dict) else enumerate(data)):
            print(f"{key}: {value}")


asyncio.run(main())
```

---

## Insights Per Device

Which devices had the most blocked requests this week — the per-device insights series, then
the single-device series for the top one.

```python
"""Rank devices by blocked-request insights, then drill into the top device."""

import asyncio

from eero import EeroClient, EeroPremiumRequiredException, id_from_url


def as_list(response: dict, key: str | None = None) -> list:
    data = response.get("data") or {}
    if isinstance(data, list):
        return data
    items = data.get(key) if key else None
    if items is None:
        items = data.get("data") or []
    if isinstance(items, dict):
        items = items.get("data") or []
    return items if isinstance(items, list) else []


async def main() -> None:
    window = {"start": "2026-07-01T00:00:00Z", "end": "2026-07-08T00:00:00Z", "cadence": "daily", "insight_type": "blocked"}

    async with EeroClient() as client:
        networks = as_list(await client.get_networks(), "networks")
        network_id = id_from_url(networks[0]["url"])

        try:
            per_device = await client.get_devices_insights(network_id=network_id, **window)
        except EeroPremiumRequiredException:
            print("Insights need an active subscription on this network.")
            return

        # The envelope is returned unmodified — print whatever the API put under data.
        print("all devices:", per_device.get("data"))

        # Drill into one device by MAC, taken from the device list rather than guessed.
        devices = (await client.get_devices(network_id=network_id)).get("data", [])
        for device in devices[:3]:
            mac = device.get("mac")
            if not mac:
                continue
            detail = await client.get_device_insights(mac, network_id=network_id, **window)
            print(device.get("nickname") or mac, "->", detail.get("data"))


asyncio.run(main())
```

---

## Speed-Test History

Run a speed test, then list the recent history the API keeps for the network.

```python
"""Trigger a speed test and print the recent history."""

import asyncio

from eero import EeroClient, EeroException, id_from_url


async def main() -> None:
    async with EeroClient() as client:
        network = await client.get_network(network_id="<network-id>", refresh_cache=True)
        network_id = id_from_url(network["data"]["url"])

        try:
            await client.run_speed_test(network_id=network_id)   # POST "" to the speedtest link
        except EeroException as err:
            print(f"Could not start a speed test: {err.error_code or err}")

        # GET on the same speedtest link; limit / startTime / endTime are optional query params.
        history = await client.get_speed_tests(network_id=network_id, limit=10)
        data = history.get("data", [])
        for result in data if isinstance(data, list) else [data]:
            down = result.get("down", {})
            up = result.get("up", {})
            print(f"down {down.get('value')} up {up.get('value')} {down.get('units', 'Mbps')}  ({result})")


asyncio.run(main())
```

---

## Channel Utilisation Panel

One day of 5 GHz channel utilisation at 15-minute granularity — the raw series for a dashboard
panel. `band` must be one of the API's declared values and `granularity` an integer.

```python
"""Fetch a day of channel-utilisation samples per band."""

import asyncio

from eero import EeroClient, EeroValidationException
from eero.api.events import CHANNEL_UTILIZATION_BANDS


async def main() -> None:
    async with EeroClient() as client:
        for band in CHANNEL_UTILIZATION_BANDS:
            try:
                util = await client.get_channel_utilization(
                    "<network-id>",                       # network_id is the only positional here
                    start="2026-07-01T00:00:00Z",
                    end="2026-07-02T00:00:00Z",
                    band=band,
                    granularity=15,                       # minutes per sample; strings are rejected
                )
            except EeroValidationException as err:
                print(f"{band}: rejected locally — {err}")
                continue

            print(band, util.get("data"))


asyncio.run(main())
```

---

## Entitlements

What the network is entitled to, what it would be upsold, and what its eero models can do.
The SDK returns these envelopes as-is — deciding whether a feature is "on" is your job.

```python
"""Dump the network's entitlement, upsell, and model-capability envelopes."""

import asyncio
import json

from eero import EeroClient


async def main() -> None:
    async with EeroClient() as client:
        features = await client.get_entitlement_features(network_id="<network-id>")
        upsell = await client.get_upsell_features(network_id="<network-id>")
        capabilities = await client.get_model_capabilities(network_id="<network-id>")   # bare ID only: sent as ?networkId=
        customer = await client.get_premium_customer()                                  # account-level

        for label, envelope in (("features", features), ("upsell", upsell), ("capabilities", capabilities), ("customer", customer)):
            print(f"== {label}")
            print(json.dumps(envelope.get("data"), indent=2)[:2000])


asyncio.run(main())
```

---

## Events

Fetch a page of the network's app events, then print the latest network scan. `page_size` and
`timestamp` are the two optional query parameters the API accepts on this endpoint —
`timestamp` is the pagination cursor, whose value you take from the previous page's data.

```python
"""Fetch a page of app events and print the network scan."""

import asyncio
import json

from eero import EeroClient


async def main() -> None:
    async with EeroClient() as client:
        page = await client.get_app_events(network_id="<network-id>", page_size=25)
        print(json.dumps(page.get("data"), indent=2)[:4000])

        # To fetch the next page, pass the cursor value from this page's data as timestamp=:
        # await client.get_app_events(network_id="<network-id>", page_size=25, timestamp="<cursor>")

        scan = await client.get_network_scan(network_id="<network-id>")
        print("network scan:", scan.get("data"))


asyncio.run(main())
```

---

## Permissions and Members

Check what the current session is allowed to do before attempting writes, and list who else is
on the network.

```python
"""Print the caller's permissions and the network's members."""

import asyncio

from eero import EeroAccessDeniedException, EeroClient


async def main() -> None:
    async with EeroClient() as client:
        perms = (await client.get_permissions(network_id="<network-id>")).get("data", {})
        print("role:", perms.get("role"))
        for capability, allowed in (perms.get("permissions") or {}).items():
            print(f"  {capability}: {allowed}")

        members = (await client.get_members(network_id="<network-id>")).get("data", {})
        for member in members.get("members", []):
            print("member:", member)

        try:
            invites = await client.get_invites(network_id="<network-id>")   # unverified read; 403 on some accounts
            print("invites:", invites.get("data"))
        except EeroAccessDeniedException:
            print("This account may not read invites.")


asyncio.run(main())
```

---

## Notifications

Read the per-event notification toggles, turn one off only if it is on, and drain the unread
flag.

```python
"""Read notification settings, conditionally change one, and mark everything read."""

import asyncio

from eero import EeroClient


async def main() -> None:
    async with EeroClient() as client:
        settings = (await client.get_notification_settings(network_id="<network-id>")).get("data", {})
        print(settings)

        # Unverified write — read-compare-skip. Keys keep their dots; the body is sent as-is.
        if settings.get("device.new") is True:
            await client.set_notification_settings({"device.new": False}, network_id="<network-id>")

        unread = (await client.has_unread_notifications(network_id="<network-id>")).get("data", {})
        if unread.get("has_unread"):
            history = await client.get_notification_history(network_id="<network-id>")
            print("history:", history.get("data"))
            await client.mark_notifications_read(network_id="<network-id>")   # POST ""; unverified


asyncio.run(main())
```

---

## Working With Multiple Networks

Iterate every network on the account, passing `network_id=` explicitly rather than relying on auto-discovery or the preferred-network default.

```python
"""Iterate every network on the account, passing network_id explicitly."""

import asyncio

from eero import EeroClient, id_from_url


def as_list(response: dict, key: str | None = None) -> list:
    """See Raw Response Format — the networks list has several shapes."""
    data = response.get("data") or {}
    if isinstance(data, list):
        return data
    items = data.get(key) if key else None
    if items is None:
        items = data.get("data") or []
    if isinstance(items, dict):
        items = items.get("data") or []
    return items if isinstance(items, list) else []


async def main() -> None:
    async with EeroClient() as client:
        networks = as_list(await client.get_networks(), "networks")

        for network in networks:
            network_id = id_from_url(network["url"])
            devices = (await client.get_devices(network_id=network_id)).get("data", [])
            connected = sum(1 for d in devices if d.get("connected"))
            print(f"{network.get('name', network_id)}: {connected}/{len(devices)} devices connected")


asyncio.run(main())
```

> ⚠️ **Warning:** Never call `set_preferred_network()` in code that fans out across multiple networks — it's global, in-memory, mutable state. See [Network Targeting](Network-Targeting).

---

Want a finished tool instead of a script? The [eeroctl](https://github.com/fulviofreitas/eeroctl) CLI already implements most of these workflows (`eero auth login`, `eero network list`, `eero profile pause`, and more) on top of this SDK.

---

## 🔗 Related Pages

- [Python API](Python-API) — full API reference & examples
- [Raw Response Format](Raw-Response-Format) — the `{"meta": ..., "data": ...}` envelope
- [Network Targeting](Network-Targeting) — passing `network_id` correctly
- [Error Handling](Error-Handling) — the `EeroException` hierarchy
- [Caching and Rate Limits](Caching-and-Rate-Limits) — TTL cache, the ~100 req/min ceiling, and which writes may reboot the mesh
- [API Reference](API-Reference) — every method with its verb, path, and verified/unverified status
- [Authentication](Authentication) — the OTP login flow in detail
