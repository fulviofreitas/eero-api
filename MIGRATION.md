# Migration Guide: Raw Response Architecture

This guide covers the migration from Pydantic models to raw JSON responses in eero-api v2.0.

## Overview

Starting with v2.0, `eero-api` returns raw, unmodified JSON responses from the Eero Cloud API. This is a **major breaking change** with no backward compatibility.

### Why This Change?

1. **Reduced Coupling**: The Eero Cloud API evolves independently. Maintaining Pydantic models within the library was fragile.
2. **Client Flexibility**: Downstream clients (eero-cli, eero-ui, etc.) can now handle response transformation according to their specific needs.
3. **Transparent Behavior**: What you get from `eero-api` is exactly what Eero returns—no hidden transformations.

## What Changed

### Before (v1.x)

```python
# All methods returned Pydantic models or extracted data
networks = await client.get_networks()  # List[Network]
for network in networks:
    print(network.name)  # Direct attribute access
    print(network.status)  # Validated enum
```

### After (v2.0)

```python
# All methods return raw Dict[str, Any]
response = await client.get_networks()  # {"meta": {...}, "data": {...}}
networks = response.get("data", {}).get("networks", [])
for network in networks:
    print(network["name"])  # Dict key access
    print(network.get("status"))  # Optional field handling
```

## API Response Format

All API methods now return the raw JSON structure from Eero:

```python
{
    "meta": {
        "code": 200,
        "server_time": "2024-01-15T12:00:00Z"
    },
    "data": {
        # Actual payload varies by endpoint
    }
}
```

## Removed Components

### Pydantic Models (Deleted)

The following models have been removed:

- `Network` → Use `response["data"]`
- `Device` → Use `response["data"]`
- `Eero` → Use `response["data"]`
- `Profile` → Use `response["data"]`
- `Account` → Use `response["data"]`
- `Activity` → Use `response["data"]`
- `Diagnostics` → Use `response["data"]`

### Transformations (Removed)

The following transformations are no longer performed:

| Old Behavior | New Behavior |
|-------------|--------------|
| Extract `data` from envelope | Return full envelope |
| Rename `wan_ip` → `public_ip` | Keep `wan_ip` |
| Rename `geo_ip.isp` → `isp_name` | Keep `geo_ip.isp` |
| Normalize `dhcp` structure | Keep original structure |
| Filter devices by status | Return all devices |
| Convert speed test results | Keep original format |

## Migration Steps

### Step 1: Update Return Type Expectations

```python
# Before
network: Network = await client.get_network()
name = network.name

# After
response: Dict[str, Any] = await client.get_network()
network = response.get("data", {})
name = network.get("name", "Unknown")
```

### Step 2: Handle Data Extraction

```python
# Before - automatic list extraction
devices: List[Device] = await client.get_devices()

# After - manual extraction
response = await client.get_devices()
devices = response.get("data", [])
# Or depending on API format:
# devices = response.get("data", {}).get("devices", [])
```

### Step 3: Add Null Checks

```python
# Before - Pydantic provided defaults
speed = network.speed_test.download_mbps

# After - handle missing data
speed_test = network.get("speed") or network.get("speed_test", {})
speed = speed_test.get("down", {}).get("value", 0)
```

### Step 4: Update Field Names

```python
# Before - normalized names
public_ip = network.public_ip
isp = network.isp_name

# After - original API names
public_ip = network.get("wan_ip")
isp = network.get("geo_ip", {}).get("isp")
```

## Helper Utilities (Optional)

If you need the old behavior, consider creating helper functions:

```python
def extract_data(response: Dict[str, Any]) -> Any:
    """Extract data from API response envelope."""
    return response.get("data", {})

def get_networks_list(response: Dict[str, Any]) -> List[Dict]:
    """Extract networks list from response."""
    data = response.get("data", {})
    if isinstance(data, list):
        return data
    return data.get("networks", data.get("data", []))
```

## Type Checking

For type safety without Pydantic:

```python
from typing import TypedDict, List

class NetworkDict(TypedDict, total=False):
    url: str
    name: str
    status: str
    wan_ip: str
    # Add fields as needed

# Use in type hints
networks: List[NetworkDict] = response.get("data", [])
```

## Error Handling

Error responses also come as raw JSON:

```python
try:
    response = await client.get_network("invalid-id")
except EeroAPIException as e:
    # e.response contains the raw error response
    error_code = e.response.get("meta", {}).get("code")
    error_message = e.response.get("meta", {}).get("error")
```

## Questions?

- Check the [Wiki](../../wiki) for updated documentation
- Open an issue for migration problems
- Review downstream client implementations (eero-cli, eero-ui) for patterns
