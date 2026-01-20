# 🐍 Python API

Programmatic access to your Eero network using the async Python client.

---

## Quick Start

```python
import asyncio
from eero import EeroClient

async def main():
    async with EeroClient() as client:
        # Check authentication
        if not client.is_authenticated:
            await client.login("your-email@example.com")
            code = input("Enter verification code: ")
            await client.verify(code)
        
        # List networks
        networks = await client.get_networks()
        for network in networks:
            print(f"📶 {network.name}: {network.status}")
        
        # List connected devices
        devices = await client.get_devices()
        for device in devices:
            print(f"💻 {device.display_name}: {device.ip}")

asyncio.run(main())
```

---

## Client Initialization

### Basic Usage

```python
from eero import EeroClient

# Using context manager (recommended)
async with EeroClient() as client:
    # Client is automatically cleaned up
    pass

# Manual lifecycle management
client = EeroClient()
await client.connect()
# ... do work ...
await client.close()
```

### Configuration Options

```python
client = EeroClient(
    session_token="optional-token",  # Pre-existing session token
    use_keyring=True,                # Use system keyring for credentials
    config_path="~/.config/eero",    # Custom config directory
    timeout=30,                      # Request timeout in seconds
)
```

---

## Authentication

### Login Flow

```python
async with EeroClient() as client:
    # Step 1: Initiate login
    await client.login("your-email@example.com")
    # or
    await client.login("+1234567890")  # Phone number
    
    # Step 2: Verify with code sent to email/phone
    code = input("Enter verification code: ")
    await client.verify(code)
    
    # Now authenticated - token is stored automatically
```

### Check Authentication Status

```python
if client.is_authenticated:
    print("Ready to make API calls")
else:
    print("Need to login")
```

### Logout

```python
await client.logout()
```

---

## Networks

### List Networks

```python
networks = await client.get_networks()
for network in networks:
    print(f"Name: {network.name}")
    print(f"Status: {network.status}")
    print(f"ID: {network.id}")
```

### Get Network Details

```python
network = await client.get_network(network_id)
print(f"SSID: {network.ssid}")
print(f"Password: {network.password}")
print(f"Guest enabled: {network.guest_network_enabled}")
```

### Update Network Settings

```python
# Rename network
await client.rename_network(network_id, "New Network Name")

# Update DNS
await client.set_dns_mode(network_id, "cloudflare")

# Enable/disable features
await client.set_upnp(network_id, enabled=False)
await client.set_wpa3(network_id, enabled=True)
await client.set_ipv6(network_id, enabled=True)
```

---

## Guest Network

```python
# Enable guest network
await client.set_guest_network(
    network_id,
    enabled=True,
    name="Guest WiFi",
    password="welcome123"
)

# Disable guest network
await client.set_guest_network(network_id, enabled=False)

# Get guest network status
guest = await client.get_guest_network(network_id)
print(f"Enabled: {guest.enabled}")
print(f"Name: {guest.name}")
```

---

## Eero Devices (Mesh Nodes)

### List Eeros

```python
eeros = await client.get_eeros(network_id)
for eero in eeros:
    print(f"Name: {eero.location}")
    print(f"Model: {eero.model}")
    print(f"Status: {eero.status}")
    print(f"Connected clients: {eero.connected_clients_count}")
```

### Reboot an Eero

```python
await client.reboot_eero(network_id, eero_id)
```

### LED Settings

```python
# Turn LED on/off
await client.set_eero_led(network_id, eero_id, enabled=True)

# Set brightness (0-100)
await client.set_eero_led_brightness(network_id, eero_id, brightness=50)
```

### Nightlight (Beacon only)

```python
await client.set_nightlight(
    network_id,
    eero_id,
    enabled=True,
    brightness=30,
    schedule={
        "on": "22:00",
        "off": "06:00"
    }
)
```

---

## Connected Clients (Devices)

### List All Clients

```python
devices = await client.get_devices(network_id)
for device in devices:
    print(f"Name: {device.display_name}")
    print(f"IP: {device.ip}")
    print(f"MAC: {device.mac}")
    print(f"Connected: {device.connected}")
    print(f"Connection type: {device.connection_type}")
```

### Get Client Details

```python
device = await client.get_device(network_id, device_id)
```

### Rename a Client

```python
await client.set_device_nickname(network_id, device_id, "Living Room TV")
```

### Block/Unblock a Client

```python
# Block device (removes from network completely)
await client.block_device(device_id, blocked=True)

# Unblock device
await client.block_device(device_id, blocked=False)
```

### Pause/Unpause a Client

Pausing a device temporarily suspends internet access while keeping it connected to the network.

```python
# Pause internet access for a device
await client.pause_device(device_id, paused=True)

# Resume internet access
await client.pause_device(device_id, paused=False)

# Get all paused devices
paused_devices = await client.get_paused_devices()
for device in paused_devices:
    print(f"Paused: {device['nickname'] or device['hostname']}")
```

> **Note**: Pausing is different from blocking:
> - **Paused**: Device stays connected to WiFi but has no internet access
> - **Blocked**: Device is completely removed from the network

### Bandwidth Priority

```python
# Enable priority for 30 minutes
await client.set_device_priority(
    network_id,
    device_id,
    enabled=True,
    duration_minutes=30
)

# Disable priority
await client.set_device_priority(network_id, device_id, enabled=False)
```

---

## Profiles

### List Profiles

```python
profiles = await client.get_profiles(network_id)
for profile in profiles:
    print(f"Name: {profile.name}")
    print(f"Paused: {profile.paused}")
    print(f"Devices: {len(profile.devices)}")
```

### Pause/Unpause Profile

```python
# Pause internet access for all devices in profile
await client.pause_profile(profile_id, paused=True)

# Resume internet access
await client.pause_profile(profile_id, paused=False)
```

### Manage Profile Devices

Assign or remove devices from a profile for easier management.

```python
# Get devices currently assigned to a profile
devices = await client.get_profile_devices(profile_id)
for device in devices:
    print(f"Device URL: {device['url']}")

# Add a device to a profile
await client.add_device_to_profile(profile_id, device_id)

# Remove a device from a profile
await client.remove_device_from_profile(profile_id, device_id)

# Set all devices for a profile (replaces existing assignments)
device_urls = [
    "/2.2/networks/{network_id}/devices/device1",
    "/2.2/networks/{network_id}/devices/device2",
]
await client.set_profile_devices(profile_id, device_urls)
```

### Block Applications (Eero Plus)

```python
# Block apps
await client.block_apps(network_id, profile_id, ["TikTok", "YouTube"])

# Unblock apps
await client.unblock_apps(network_id, profile_id, ["YouTube"])
```

---

## Speed Tests

```python
# Run a new speed test
results = await client.run_speed_test(network_id)
print(f"Download: {results['down']} Mbps")
print(f"Upload: {results['up']} Mbps")

# Get last speed test results
last_test = await client.get_speed_test(network_id)
```

---

## Diagnostics

```python
# Run diagnostics
diagnostics = await client.run_diagnostics(network_id)

# Get network health status
health = await client.get_network_health(network_id)
```

---

## Error Handling

```python
from eero.exceptions import (
    EeroAuthenticationError,
    EeroNotFoundError,
    EeroForbiddenError,
    EeroTimeoutError,
    EeroAPIError,
)

try:
    await client.get_network("invalid-id")
except EeroNotFoundError:
    print("Network not found")
except EeroAuthenticationError:
    print("Need to re-authenticate")
except EeroForbiddenError:
    print("Insufficient permissions")
except EeroTimeoutError:
    print("Request timed out")
except EeroAPIError as e:
    print(f"API error: {e.message}")
```

---

## Advanced: Custom Session

```python
import aiohttp

# Use a custom aiohttp session
async with aiohttp.ClientSession() as session:
    client = EeroClient(session=session)
    await client.connect()
    # ...
```

---

## Type Hints

The client uses Pydantic models for full type safety:

```python
from eero.models import Network, Device, Profile, Eero

async def process_network(network: Network) -> None:
    print(network.name)  # IDE autocomplete works!
```

---

## 🔗 Related Pages

- [CLI Reference](CLI-Reference) — Command-line interface
- [Usage Examples](Usage-Examples) — CLI examples
- [Configuration](Configuration) — Authentication storage

