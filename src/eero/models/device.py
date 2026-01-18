"""Device-related models for the Eero API."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..const import EeroDeviceStatus


class DeviceTag(BaseModel):
    """Model representing a device tag."""

    id: Optional[str] = Field(None, description="Tag ID")
    name: Optional[str] = Field(None, description="Tag name")
    color: Optional[str] = Field(None, description="Tag color")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"


class DeviceConnection(BaseModel):
    """Model representing a device connection."""

    type: Optional[str] = Field(None, description="Connection type (wired/wireless)")
    connected_to: Optional[str] = Field(None, description="Connected to device ID")
    connected_via: Optional[str] = Field(
        None, description="Connected via (e.g., 'wifi', 'ethernet')"
    )
    frequency: Optional[str] = Field(None, description="Frequency (2.4GHz/5GHz)")
    signal_strength: Optional[int] = Field(None, description="Signal strength")
    tx_rate: Optional[int] = Field(None, description="TX rate")
    rx_rate: Optional[int] = Field(None, description="RX rate")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"


class DeviceSource(BaseModel):
    """Model representing device source information."""

    location: Optional[str] = Field(None, description="Location of the source eero")
    is_gateway: bool = Field(False, description="Whether this is a gateway")
    model: Optional[str] = Field(None, description="Eero model")
    display_name: Optional[str] = Field(None, description="Display name")
    serial_number: Optional[str] = Field(None, description="Serial number")
    is_proxied_node: bool = Field(False, description="Whether this is a proxied node")
    url: Optional[str] = Field(None, description="URL to the eero")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"


class DeviceConnectivity(BaseModel):
    """Model representing device connectivity information."""

    rx_bitrate: Optional[str] = Field(None, description="RX bitrate")
    tx_bitrate: Optional[str] = Field(None, description="TX bitrate")
    signal: Optional[str] = Field(None, description="Signal strength")
    signal_avg: Optional[str] = Field(None, description="Average signal strength")
    score: Optional[float] = Field(None, description="Connection score")
    score_bars: Optional[int] = Field(None, description="Score bars")
    frequency: Optional[int] = Field(None, description="Frequency in MHz")
    rx_rate_info: Optional[Dict[str, Any]] = Field(None, description="RX rate information")
    tx_rate_info: Optional[Dict[str, Any]] = Field(None, description="TX rate information")
    ethernet_status: Optional[Union[str, Dict[str, Any]]] = Field(
        None, description="Ethernet status"
    )

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"


class DeviceInterface(BaseModel):
    """Model representing device interface information."""

    frequency: Optional[str] = Field(None, description="Frequency")
    frequency_unit: Optional[str] = Field(None, description="Frequency unit")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"


class DeviceProfile(BaseModel):
    """Model representing device profile information."""

    url: Optional[str] = Field(None, description="Profile URL")
    name: Optional[str] = Field(None, description="Profile name")
    paused: bool = Field(False, description="Whether profile is paused")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"


class DeviceHomekit(BaseModel):
    """Model representing device HomeKit information."""

    registered: bool = Field(False, description="Whether device is registered with HomeKit")
    protection_mode: Optional[str] = Field(None, description="Protection mode")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"


class DeviceRingLTE(BaseModel):
    """Model representing device Ring LTE information."""

    is_not_pausable: bool = Field(False, description="Whether device is not pausable")
    ring_managed: bool = Field(False, description="Whether device is Ring managed")
    lte_enabled: bool = Field(False, description="Whether LTE is enabled")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"


class DeviceIPv6Address(BaseModel):
    """Model representing device IPv6 address information."""

    address: Optional[str] = Field(None, description="IPv6 address")
    scope: Optional[str] = Field(None, description="Address scope")
    interface: Optional[str] = Field(None, description="Interface name")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"


class Device(BaseModel):
    """Model representing a device connected to an Eero network."""

    # Core device information
    url: Optional[str] = Field(None, description="Device URL")
    mac: Optional[str] = Field(None, alias="mac_address", description="MAC address")
    eui64: Optional[str] = Field(None, description="EUI64 identifier")
    manufacturer: Optional[str] = Field(None, description="Manufacturer name")
    ip: Optional[str] = Field(None, alias="ip_address", description="Primary IP address")
    ips: List[str] = Field(default_factory=list, description="All IP addresses")
    ipv6_addresses: List[DeviceIPv6Address] = Field(
        default_factory=list, description="IPv6 addresses"
    )
    ipv4: Optional[str] = Field(None, description="IPv4 address")

    # Device identification
    nickname: Optional[str] = Field(None, description="User-defined device nickname")
    hostname: Optional[str] = Field(None, description="Device hostname")
    display_name: Optional[str] = Field(None, alias="name", description="Display name")
    model_name: Optional[str] = Field(None, alias="model", description="Model name")

    # Connection status
    connected: Optional[bool] = Field(False, description="Whether the device is connected")
    wireless: Optional[bool] = Field(False, description="Whether the device is wireless")
    connection_type: Optional[str] = Field(None, description="Connection type")

    # Source information
    source: Optional[DeviceSource] = Field(None, description="Source eero information")

    # Timestamps
    last_active: Optional[datetime] = Field(None, alias="last_seen", description="When last active")
    first_active: Optional[datetime] = Field(
        None, alias="first_seen", description="When first active"
    )

    # Connectivity details
    connectivity: Optional[DeviceConnectivity] = Field(None, description="Connectivity information")
    interface: Optional[DeviceInterface] = Field(None, description="Interface information")

    # Usage and profile
    usage: Optional[Dict[str, Any]] = Field(None, description="Usage statistics")
    profile: Optional[DeviceProfile] = Field(None, description="Profile information")

    # Device classification
    device_type: Optional[str] = Field(None, description="Device type")
    manufacturer_device_type_id: Optional[str] = Field(
        None, description="Manufacturer device type ID"
    )
    amazon_devices_detail: Optional[Dict[str, Any]] = Field(
        None, description="Amazon devices detail"
    )

    # Network information
    ssid: Optional[str] = Field(None, description="SSID")
    subnet_kind: Optional[str] = Field(None, description="Subnet kind")
    channel: Optional[int] = Field(None, description="WiFi channel")
    auth: Optional[str] = Field(None, description="Authentication method")

    # Status flags
    blacklisted: Optional[bool] = Field(
        False, alias="blocked", description="Whether device is blacklisted"
    )
    dropped: Optional[bool] = Field(False, description="Whether device is dropped")
    is_guest: Optional[bool] = Field(
        False, alias="guest", description="Whether device is on guest network"
    )
    paused: Optional[bool] = Field(False, description="Whether device is paused")
    is_private: Optional[bool] = Field(False, description="Whether device is private")
    secondary_wan_deny_access: Optional[bool] = Field(
        False, description="Whether secondary WAN access is denied"
    )
    is_proxied_node: Optional[bool] = Field(False, description="Whether device is a proxied node")

    # HomeKit and Ring integration
    homekit: Optional[DeviceHomekit] = Field(None, description="HomeKit information")
    ring_lte: Optional[DeviceRingLTE] = Field(None, description="Ring LTE information")

    # Legacy fields for compatibility
    id: Optional[str] = Field(None, description="Device ID (extracted from URL)")
    network_id: Optional[str] = Field(None, description="Network ID")
    status: EeroDeviceStatus = Field(EeroDeviceStatus.UNKNOWN, description="Device status")
    connection: Optional[DeviceConnection] = Field(None, description="Connection details")
    tags: List[DeviceTag] = Field(default_factory=list, description="Device tags")
    profile_id: Optional[str] = Field(None, description="Profile ID")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"  # Allow extra fields from API response

    def __init__(self, **data):
        """Initialize the Device model with computed fields."""
        super().__init__(**data)

        # Extract device ID from URL if not provided
        if not self.id and self.url:
            # Extract device ID from URL like "/2.2/networks/3401709/devices/44070b35c7b2"
            parts = self.url.split("/")
            if len(parts) >= 2:
                self.id = parts[-1]

        # Extract network ID from URL if not provided
        if not self.network_id and self.url:
            parts = self.url.split("/")
            if len(parts) >= 4:
                self.network_id = parts[-3]

        # Extract profile ID from profile URL if not provided
        if not self.profile_id and self.profile and self.profile.url:
            parts = self.profile.url.split("/")
            if len(parts) >= 2:
                self.profile_id = parts[-1]

        # Determine status based on connection state
        if self.connected:
            if self.blacklisted:
                self.status = EeroDeviceStatus.BLOCKED
            else:
                self.status = EeroDeviceStatus.CONNECTED
        else:
            self.status = EeroDeviceStatus.DISCONNECTED
