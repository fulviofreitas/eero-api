# 💡 Examples

Ten complete, runnable scripts covering the workflows people actually build against this SDK.

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

Run a speed test and read the download/upload result directly from the response.

```python
"""Run a speed test and print the download/upload results."""

import asyncio

from eero import EeroClient, EeroException


async def main() -> None:
    async with EeroClient() as client:
        try:
            result = await client.run_speed_test()
        except EeroException as err:
            print(f"Speed test failed: {err}")
            return

        data = result.get("data", {})
        down = data.get("down", {})
        up = data.get("up", {})
        print(f"Download: {down.get('value')} {down.get('units', 'Mbps')}")
        print(f"Upload:   {up.get('value')} {up.get('units', 'Mbps')}")


asyncio.run(main())
```

---

## Reserve a DHCP Address and Open a Port Forward

The v6.1.0/v6.2.0 features — created, then listed, then cleaned up. Reservations and forwards never auto-discover a network, so `network_id` must be explicit.

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

        reservation_data = {"device_id": "device_042", "ip_address": "192.168.4.200"}
        forward_data = {"device_id": "device_042", "port": 8080, "protocol": "tcp"}

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
        for reservation in reservations:
            if reservation.get("ip_address") == reservation_data["ip_address"]:
                await client.delete_reservation(
                    id_from_url(reservation["url"]), network_id=network_id
                )
                break

        for forward in forwards:
            if forward.get("port") == forward_data["port"]:
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

Read the guest network config, set a new password, and confirm the change took.

```python
"""Read the guest network config, rotate its password, and confirm the change."""

import asyncio
import secrets

from eero import EeroClient, EeroException


async def main() -> None:
    async with EeroClient() as client:
        network = await client.get_network(refresh_cache=True)
        guest = network.get("data", {}).get("guest_network", {})
        print(f"Guest network {guest.get('name', '(unnamed)')} enabled={guest.get('enabled', False)}")

        new_password = secrets.token_urlsafe(12)
        try:
            await client.set_guest_network(enabled=True, password=new_password)
        except EeroException as err:
            print(f"Failed to rotate guest password: {err}")
            return

        updated = await client.get_network(refresh_cache=True)
        updated_guest = updated.get("data", {}).get("guest_network", {})
        print(f"Rotated. Guest network now enabled={updated_guest.get('enabled', False)}")


asyncio.run(main())
```

---

## Dual-Stack Custom DNS

Configure all four slots the eero app exposes — IPv4 primary/secondary and IPv6
primary/secondary — then verify the write actually landed.

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

Clearing is non-destructive on the **server** side — the API keeps the stored servers rather
than erasing them, so they still appear in `dns.custom.ips` while the mode is `automatic`.

Switching back through this SDK still requires supplying the addresses, though. The API
appears to accept a mode-only write that would re-enable the retained servers, but that has
not been live-verified, so no method exposes it.

```python
async with EeroClient() as client:
    # ...resolve network_id as above...
    await client.clear_custom_dns(family="ipv6", network_id=network_id)  # IPv4 untouched
    await client.set_custom_dns_ipv6(
        ["2001:4860:4860::8888"], network_id=network_id
    )  # re-enabling means passing addresses again
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
- [Caching and Rate Limits](Caching-and-Rate-Limits) — TTL cache & the ~100 req/min ceiling
- [Authentication](Authentication) — the OTP login flow in detail
