"""Eero device-specific models for the Eero API."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from ..const import EeroDeviceType


class Location(BaseModel):
    """Model representing the location of an Eero device."""

    lat: Optional[float] = Field(None, description="Latitude")
    lon: Optional[float] = Field(None, description="Longitude")
    address: Optional[str] = Field(None, description="Address")
    city: Optional[str] = Field(None, description="City")
    state: Optional[str] = Field(None, description="State/Province")
    country: Optional[str] = Field(None, description="Country")
    zip_code: Optional[str] = Field(None, description="Postal/ZIP code")


class EeroHealth(BaseModel):
    """Model representing the health status of an Eero device."""

    status: str = Field(..., description="Health status")
    issues: List[Dict[str, Any]] = Field(default_factory=list, description="Health issues")


class NeighborMetadata(BaseModel):
    """Model representing neighbor metadata."""

    port: Optional[int] = Field(None, description="Port number")
    port_name: Optional[str] = Field(None, description="Port name")
    location: Optional[str] = Field(None, description="Location")
    url: Optional[str] = Field(None, description="URL")


class Neighbor(BaseModel):
    """Model representing a neighbor device."""

    type: Optional[str] = Field(None, description="Device type")
    metadata: Optional[NeighborMetadata] = Field(None, description="Metadata")


class LldpInfo(BaseModel):
    """Model representing LLDP information."""

    systemDescription: Optional[str] = Field(None, description="System description")
    managementIpv4Address: Optional[str] = Field(None, description="Management IPv4 address")
    managementIpv6Address: Optional[str] = Field(None, description="Management IPv6 address")
    chassisIdType: Optional[str] = Field(None, description="Chassis ID type")
    chassisId: Optional[str] = Field(None, description="Chassis ID")
    portIdType: Optional[str] = Field(None, description="Port ID type")
    portId: Optional[str] = Field(None, description="Port ID")
    portDescription: Optional[str] = Field(None, description="Port description")
    macAddress: Optional[str] = Field(None, description="MAC address")
    systemName: Optional[str] = Field(None, description="System name")


class EthernetStatus(BaseModel):
    """Model representing ethernet status."""

    interfaceNumber: Optional[int] = Field(None, description="Interface number")
    hasCarrier: Optional[bool] = Field(None, description="Has carrier")
    speed: Optional[str] = Field(None, description="Speed")
    isWanPort: Optional[bool] = Field(None, description="Is WAN port")
    isLte: Optional[bool] = Field(None, description="Is LTE")
    isLeafWiredToUpstream: Optional[bool] = Field(None, description="Is leaf wired to upstream")
    neighbor: Optional[Neighbor] = Field(None, description="Neighbor")
    power_saving: Optional[bool] = Field(None, description="Power saving")
    original_speed: Optional[str] = Field(None, description="Original speed")
    derated_reason: Optional[str] = Field(None, description="Derated reason")
    lldpInfo: Optional[List[LldpInfo]] = Field(None, description="LLDP info")
    port_name: Optional[str] = Field(None, description="Port name")


class EthernetStatuses(BaseModel):
    """Model representing ethernet statuses."""

    statuses: Optional[List[EthernetStatus]] = Field(None, description="Statuses")
    wiredInternet: Optional[bool] = Field(None, description="Wired internet")
    segmentId: Optional[str] = Field(None, description="Segment ID")


class Ipv6Address(BaseModel):
    """Model representing IPv6 address."""

    address: Optional[str] = Field(None, description="Address")
    scope: Optional[str] = Field(None, description="Scope")
    interface: Optional[str] = Field(None, description="Interface")


class PowerInfo(BaseModel):
    """Model representing power information."""

    power_source: Optional[str] = Field(None, description="Power source")
    power_source_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Power source metadata"
    )


class UpdateStatus(BaseModel):
    """Model representing update status."""

    support_expired: Optional[bool] = Field(None, description="Support expired")
    support_expiration_string: Optional[str] = Field(None, description="Support expiration string")
    support_expiration_date: Optional[str] = Field(None, description="Support expiration date")


class Organization(BaseModel):
    """Model representing organization."""

    id: Optional[int] = Field(None, description="Organization ID")
    name: Optional[str] = Field(None, description="Organization name")


class BssidWithBand(BaseModel):
    """Model representing BSSID with band."""

    band: Optional[str] = Field(None, description="Band")
    ethernet_address: Optional[str] = Field(None, description="Ethernet address")


class PortDetail(BaseModel):
    """Model representing port detail."""

    ethernet_address: Optional[str] = Field(None, description="Ethernet address")
    port_name: Optional[str] = Field(None, description="Port name")
    position: Optional[int] = Field(None, description="Position")


class Eero(BaseModel):
    """Model representing an Eero device."""

    # Required fields from API response
    url: str = Field(..., description="API URL for the Eero")
    serial: str = Field(..., description="Serial number")
    mac_address: str = Field(..., description="MAC address")
    model: str = Field(..., description="Model name")
    status: str = Field(..., description="Current status")

    # Optional fields from API response
    name: Optional[str] = Field(None, description="Eero name")
    network_id: Optional[str] = Field(None, description="Network ID this Eero belongs to")
    device_type: EeroDeviceType = Field(EeroDeviceType.UNKNOWN, description="Eero device type")
    created_at: Optional[datetime] = Field(None, description="When the Eero was created")
    updated_at: Optional[datetime] = Field(None, description="When the Eero was last updated")
    firmware_version: Optional[str] = Field(None, description="Firmware version")
    ip_address: Optional[str] = Field(None, description="IP address")
    connected: bool = Field(False, description="Whether the Eero is connected")
    is_gateway: bool = Field(False, description="Whether the Eero is a gateway")
    gateway: bool = Field(False, description="Whether the Eero is a gateway (API field)")
    is_primary: bool = Field(False, description="Whether the Eero is primary")
    is_primary_node: bool = Field(False, description="Whether the Eero is primary node (API field)")
    backup_connection: bool = Field(False, description="Whether using backup connection")
    wired: bool = Field(False, description="Whether the Eero is wired")
    connected_clients_count: int = Field(0, description="Number of connected clients")
    health: Optional[EeroHealth] = Field(None, description="Health status")
    location: Optional[Union[str, Location]] = Field(None, description="Physical location")
    parent: Optional[str] = Field(None, description="Parent Eero ID")
    last_heartbeat: Optional[Union[str, datetime]] = Field(
        None, description="Last heartbeat timestamp"
    )
    uptime: Optional[int] = Field(None, description="Uptime in seconds")
    memory_usage: Optional[float] = Field(None, description="Memory usage percentage")
    cpu_usage: Optional[float] = Field(None, description="CPU usage percentage")
    temperature: Optional[float] = Field(None, description="Temperature in Celsius")

    # Additional fields from API response
    joined: Optional[str] = Field(None, description="When the Eero joined the network")
    model_number: Optional[str] = Field(None, description="Model number")
    model_variant: Optional[str] = Field(None, description="Model variant")
    os: Optional[str] = Field(None, description="Operating system version")
    os_version: Optional[str] = Field(None, description="OS version")
    mesh_quality_bars: Optional[int] = Field(None, description="Mesh quality bars")
    led_on: Optional[bool] = Field(None, description="LED status")
    led_brightness: Optional[int] = Field(None, description="LED brightness")
    using_wan: Optional[bool] = Field(None, description="Using WAN connection")
    connection_type: Optional[str] = Field(None, description="Connection type")
    state: Optional[str] = Field(None, description="Device state")
    update_available: Optional[bool] = Field(None, description="Update available")
    heartbeat_ok: Optional[bool] = Field(None, description="Heartbeat status")
    provides_wifi: Optional[bool] = Field(None, description="Provides WiFi")
    auto_provisioned: Optional[bool] = Field(None, description="Auto provisioned")

    # Network-related fields
    network: Optional[Dict[str, Any]] = Field(None, description="Network information")
    resources: Optional[Dict[str, Any]] = Field(None, description="Available resources")
    ethernet_addresses: Optional[List[str]] = Field(None, description="Ethernet addresses")
    ethernet_status: Optional[EthernetStatuses] = Field(None, description="Ethernet status")
    wifi_bssids: Optional[List[str]] = Field(None, description="WiFi BSSIDs")
    bands: Optional[List[str]] = Field(None, description="Supported bands")
    bssids_with_bands: Optional[List[BssidWithBand]] = Field(None, description="BSSIDs with bands")
    port_details: Optional[List[PortDetail]] = Field(None, description="Port details")

    # Additional optional fields
    messages: Optional[List[Dict[str, Any]]] = Field(None, description="Messages")
    update_status: Optional[UpdateStatus] = Field(None, description="Update status")
    ipv6_addresses: Optional[List[Ipv6Address]] = Field(None, description="IPv6 addresses")
    organization: Optional[Organization] = Field(None, description="Organization info")
    power_info: Optional[PowerInfo] = Field(None, description="Power information")
    backup_wan: Optional[Dict[str, Any]] = Field(None, description="Backup WAN info")
    extended_border_agent_address: Optional[str] = Field(
        None, description="Extended border agent address"
    )
    provide_device_power: Optional[bool] = Field(None, description="Provide device power")
    wireless_upstream_node: Optional[Dict[str, Any]] = Field(
        None, description="Wireless upstream node"
    )
    cellular_backup: Optional[Dict[str, Any]] = Field(None, description="Cellular backup info")
    channel_selection: Optional[Dict[str, Any]] = Field(None, description="Channel selection")
    nightlight: Optional[Dict[str, Any]] = Field(None, description="Nightlight settings")
    last_reboot: Optional[str] = Field(None, description="Last reboot timestamp")
    requires_amazon_pre_authorized_code: Optional[bool] = Field(
        None, description="Requires Amazon pre-authorized code"
    )
    connected_wired_clients_count: Optional[int] = Field(
        None, description="Connected wired clients count"
    )
    connected_wireless_clients_count: Optional[int] = Field(
        None, description="Connected wireless clients count"
    )

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        extra = "allow"  # Allow extra fields from API response

    @property
    def eero_id(self) -> str:
        """Extract Eero ID from URL."""
        if self.url:
            # Extract ID from URL like "/2.2/eeros/26172144"
            parts = self.url.split("/")
            if len(parts) > 0:
                return parts[-1]
        return ""
