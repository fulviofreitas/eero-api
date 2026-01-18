from datetime import datetime
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, model_validator

from ..const import EeroNetworkStatus


class NetworkSettings(BaseModel):
    """Model representing network settings."""

    ipv6_upstream: bool = Field(False, description="IPv6 upstream enabled")
    band_steering: bool = Field(False, description="Band steering enabled")
    thread_enabled: bool = Field(False, description="Thread enabled")
    upnp_enabled: bool = Field(False, description="UPnP enabled")
    wpa3_transition: bool = Field(False, description="WPA3 transition mode enabled")
    dns_caching: bool = Field(True, description="DNS caching enabled")
    ipv6_downstream: bool = Field(False, description="IPv6 downstream enabled")
    target_firmware: Optional[str] = Field(None, description="Target firmware version")
    gateway_mac_address: Optional[str] = Field(None, description="Gateway MAC address")


class DHCP(BaseModel):
    """Model representing DHCP configuration."""

    # Make all fields optional with defaults
    lease_time_seconds: int = Field(86400, description="DHCP lease time in seconds")
    dns_server: Optional[str] = Field(None, description="DNS server")
    subnet_mask: str = Field("255.255.255.0", description="Subnet mask")
    starting_address: str = Field("192.168.4.2", description="Starting IP address")
    ending_address: str = Field("192.168.4.254", description="Ending IP address")


class Network(BaseModel):
    """Model representing an Eero network."""

    id: str = Field(..., description="Unique identifier for the network")
    name: str = Field(..., description="Network name")
    # Accept either string or EeroNetworkStatus enum for status
    status: Union[str, EeroNetworkStatus] = Field(
        EeroNetworkStatus.UNKNOWN, description="Network status"
    )
    created_at: Optional[datetime] = Field(None, description="When the network was created")
    updated_at: Optional[datetime] = Field(None, description="When the network was last updated")
    speed_test: Optional[Dict[str, Any]] = Field(None, description="Latest speed test results")
    bandwidth_limits: Optional[Dict[str, Any]] = Field(
        None, description="Bandwidth limits configuration"
    )
    health: Optional[Dict[str, Any]] = Field(None, description="Network health status")
    dhcp: Optional[DHCP] = Field(None, description="DHCP configuration")
    settings: NetworkSettings = Field(
        default_factory=lambda: NetworkSettings(
            ipv6_upstream=False,
            band_steering=False,
            thread_enabled=False,
            upnp_enabled=False,
            wpa3_transition=False,
            dns_caching=True,
            ipv6_downstream=False,
            target_firmware=None,
            gateway_mac_address=None,
        ),
        description="Network settings",
    )
    guest_network_enabled: bool = Field(False, description="Guest network enabled status")
    guest_network_name: Optional[str] = Field(None, description="Guest network name")
    guest_network_password: Optional[str] = Field(None, description="Guest network password")
    isp_name: Optional[str] = Field(None, description="ISP name")
    public_ip: Optional[str] = Field(None, description="Public IP address")
    url: Optional[str] = Field(None, description="Network URL")

    # Additional fields from API response
    display_name: Optional[str] = Field(None, description="Display name")
    owner: Optional[str] = Field(None, description="Network owner")
    network_customer_type: Optional[str] = Field(None, description="Network customer type")
    premium_status: Optional[str] = Field(None, description="Premium subscription status")
    gateway: Optional[str] = Field(None, description="Gateway type")
    wan_type: Optional[str] = Field(None, description="WAN connection type")
    gateway_ip: Optional[str] = Field(None, description="Gateway IP address")
    connection_mode: Optional[str] = Field(None, description="Connection mode")
    auto_setup_mode: Optional[str] = Field(None, description="Auto setup mode")
    backup_internet_enabled: bool = Field(False, description="Backup internet enabled")
    power_saving: bool = Field(False, description="Power saving enabled")
    wireless_mode: Optional[str] = Field(None, description="Wireless mode")
    mlo_mode: Optional[str] = Field(None, description="MLO mode")
    sqm: bool = Field(False, description="Smart Queue Management enabled")
    upnp: bool = Field(False, description="UPnP enabled")
    thread: bool = Field(False, description="Thread enabled")
    band_steering: bool = Field(False, description="Band steering enabled")
    wpa3: bool = Field(False, description="WPA3 enabled")
    ipv6_upstream: bool = Field(False, description="IPv6 upstream enabled")
    geo_ip: Optional[Dict[str, Any]] = Field(None, description="Geographic IP information")
    dns: Optional[Dict[str, Any]] = Field(None, description="DNS configuration")
    organization: Optional[Dict[str, Any]] = Field(None, description="Organization information")
    premium_details: Optional[Dict[str, Any]] = Field(
        None, description="Premium subscription details"
    )
    updates: Optional[Dict[str, Any]] = Field(None, description="Update information")
    ddns: Optional[Dict[str, Any]] = Field(None, description="DDNS configuration")
    homekit: Optional[Dict[str, Any]] = Field(None, description="HomeKit configuration")
    amazon_account_linked: bool = Field(False, description="Amazon account linked")
    ffs: bool = Field(False, description="FFS enabled")
    alexa_skill: bool = Field(False, description="Alexa skill enabled")
    amazon_device_nickname: bool = Field(False, description="Amazon device nickname enabled")
    ip_settings: Optional[Dict[str, Any]] = Field(None, description="IP settings")
    premium_dns: Optional[Dict[str, Any]] = Field(None, description="Premium DNS configuration")
    last_reboot: Optional[str] = Field(None, description="Last reboot timestamp")

    # Normalize status field
    @model_validator(mode="after")
    def ensure_basic_fields(self):
        """Ensure all required fields have at least default values and normalize status."""
        # Normalize status to a string representation
        if self.status is None:
            self.status = "unknown"
        elif isinstance(self.status, EeroNetworkStatus):
            # Keep as enum, will be displayed properly in CLI
            pass
        elif isinstance(self.status, str):
            # Convert string status to enum if it matches
            try:
                # Try to match with enum values
                self.status = EeroNetworkStatus(self.status.lower())
            except ValueError:
                # If the status string doesn't match any enum, handle special cases
                if self.status.lower() == "connected":
                    # API returns "connected" for online networks
                    self.status = EeroNetworkStatus.ONLINE
                # Otherwise keep the string as is

        # If settings is None, create default
        if not hasattr(self, "settings") or self.settings is None:
            self.settings = NetworkSettings(
                ipv6_upstream=False,
                band_steering=False,
                thread_enabled=False,
                upnp_enabled=False,
                wpa3_transition=False,
                dns_caching=True,
                ipv6_downstream=False,
                target_firmware=None,
                gateway_mac_address=None,
            )

        # If DHCP is problematic, set to None
        if hasattr(self, "dhcp") and isinstance(self.dhcp, dict):
            # Check if we have all required fields
            required_dhcp_fields = [
                "subnet_mask",
                "starting_address",
                "ending_address",
                "lease_time_seconds",
            ]
            if not all(field in self.dhcp for field in required_dhcp_fields):
                # Set to None to avoid validation errors
                self.dhcp = None

        return self

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
        # Allow extra fields in the response
        extra = "ignore"
