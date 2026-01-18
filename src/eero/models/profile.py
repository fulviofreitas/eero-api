"""Profile-related models for the Eero API."""

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ProfileScheduleBlock(BaseModel):
    """Model representing a time block in a profile schedule."""

    days: List[str] = Field(..., description="Days of the week")
    start_time: str = Field(..., description="Start time (HH:MM)")
    end_time: str = Field(..., description="End time (HH:MM)")


class ContentFilter(BaseModel):
    """Model representing content filtering settings."""

    adblock: bool = Field(False, description="Ad blocking enabled")
    adblock_plus: bool = Field(False, description="Enhanced ad blocking enabled")
    safe_search: bool = Field(False, description="Safe search enabled")
    block_malware: bool = Field(False, description="Malware blocking enabled")
    block_illegal: bool = Field(False, description="Illegal content blocking enabled")
    block_violent: bool = Field(False, description="Violent content blocking enabled")
    block_adult: bool = Field(False, description="Adult content blocking enabled")
    youtube_restricted: bool = Field(False, description="YouTube restricted mode enabled")


class ProfileState(BaseModel):
    """Model representing profile state."""

    value: str = Field(..., description="Profile state value")
    schedule: Optional[str] = Field(None, description="Schedule information")


class ProfileResources(BaseModel):
    """Model representing profile resources."""

    schedules: str = Field(..., description="Schedules resource URL")


class Profile(BaseModel):
    """Model representing a profile for grouped devices."""

    url: str = Field(..., description="Profile URL")
    resources: Optional[ProfileResources] = Field(None, description="Profile resources")
    name: str = Field(..., description="Profile name")
    paused: bool = Field(False, description="Whether internet access is paused")
    devices: List[Dict[str, Any]] = Field(
        default_factory=list, description="Devices in this profile"
    )
    schedule: List[Any] = Field(default_factory=list, description="Schedule information")
    state: ProfileState = Field(..., description="Profile state")
    premium_dns: Optional[Dict[str, Any]] = Field(None, description="Premium DNS settings")
    unified_content_filters: Optional[Dict[str, Any]] = Field(
        None, description="Unified content filters"
    )
    proxied_nodes: List[Any] = Field(default_factory=list, description="Proxied nodes")
    default: bool = Field(False, description="Whether this is the default profile")

    # Computed fields
    id: Optional[str] = Field(None, description="Extracted profile ID from URL")
    network_id: Optional[str] = Field(None, description="Extracted network ID from URL")
    device_count: Optional[int] = Field(None, description="Number of devices in this profile")
    connected_device_count: Optional[int] = Field(None, description="Number of connected devices")
    wired_device_count: Optional[int] = Field(None, description="Number of wired devices")
    wireless_device_count: Optional[int] = Field(None, description="Number of wireless devices")
    schedule_enabled: Optional[bool] = Field(None, description="Whether schedule is enabled")
    schedule_blocks: Optional[List[ProfileScheduleBlock]] = Field(
        None, description="Schedule blocks"
    )
    content_filter: Optional[ContentFilter] = Field(None, description="Content filtering settings")
    device_ids: Optional[List[str]] = Field(None, description="Device IDs")
    custom_block_list: List[str] = Field(default_factory=list, description="Custom blocked domains")
    custom_allow_list: List[str] = Field(default_factory=list, description="Custom allowed domains")
    usage: Optional[Dict[str, Any]] = Field(None, description="Usage statistics")
    premium_enabled: Optional[bool] = Field(
        None, description="Whether premium features are enabled"
    )

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization hook to compute derived fields."""
        # Extract profile ID from URL if not provided
        if not self.id and self.url:
            parts = self.url.split("/")
            if len(parts) >= 2:
                self.id = parts[-1]

        # Extract network ID from URL if not provided
        if not self.network_id and self.url:
            parts = self.url.split("/")
            if len(parts) >= 4:
                self.network_id = parts[-3]

    @field_validator("device_count", mode="before")
    @classmethod
    def compute_device_count(cls, v: Optional[int], info: Any) -> int:
        """Compute device count from devices list."""
        if v is not None:
            return v

        devices = info.data.get("devices", [])
        return len(devices) if devices else 0

    @field_validator("connected_device_count", mode="before")
    @classmethod
    def compute_connected_device_count(cls, v: Optional[int], info: Any) -> int:
        """Compute connected device count from devices list."""
        if v is not None:
            return v

        devices = info.data.get("devices", [])
        if not devices:
            return 0

        connected_count = 0
        for device in devices:
            if device.get("connected", False):
                connected_count += 1
        return connected_count

    @field_validator("wired_device_count", mode="before")
    @classmethod
    def compute_wired_device_count(cls, v: Optional[int], info: Any) -> int:
        """Compute wired device count from devices list."""
        if v is not None:
            return v

        devices = info.data.get("devices", [])
        if not devices:
            return 0

        wired_count = 0
        for device in devices:
            if device.get("connected", False) and device.get("wireless") is False:
                wired_count += 1
        return wired_count

    @field_validator("wireless_device_count", mode="before")
    @classmethod
    def compute_wireless_device_count(cls, v: Optional[int], info: Any) -> int:
        """Compute wireless device count from devices list."""
        if v is not None:
            return v

        devices = info.data.get("devices", [])
        if not devices:
            return 0

        wireless_count = 0
        for device in devices:
            if device.get("connected", False) and device.get("wireless") is True:
                wireless_count += 1
        return wireless_count

    @field_validator("device_ids", mode="before")
    @classmethod
    def extract_device_ids(cls, v: Optional[List[str]], info: Any) -> List[str]:
        """Extract device IDs from devices list."""
        if v is not None:
            return v

        devices = info.data.get("devices", [])
        if not devices:
            return []

        device_ids = []
        for device in devices:
            device_url = device.get("url", "")
            if device_url:
                # Extract device ID from URL like /2.2/networks/3401709/devices/8609b71bd8df
                match = re.search(r"/devices/([^/]+)", device_url)
                if match:
                    device_ids.append(match.group(1))
        return device_ids

    @field_validator("schedule_enabled", mode="before")
    @classmethod
    def compute_schedule_enabled(cls, v: Optional[bool], info: Any) -> bool:
        """Compute schedule enabled from schedule data."""
        if v is not None:
            return v

        schedule = info.data.get("schedule", [])
        return len(schedule) > 0 if schedule else False

    @field_validator("content_filter", mode="before")
    @classmethod
    def extract_content_filter(
        cls, v: Optional[ContentFilter], info: Any
    ) -> Optional[ContentFilter]:
        """Extract content filter from unified_content_filters."""
        if v is not None:
            return v

        unified_filters = info.data.get("unified_content_filters", {})
        if not unified_filters:
            return None

        dns_policies = unified_filters.get("dns_policies", {})
        if not dns_policies:
            return None

        return ContentFilter(
            safe_search=dns_policies.get("safe_search_enabled", False),
            youtube_restricted=dns_policies.get("youtube_restricted", False),
            block_adult=dns_policies.get("block_pornographic_content", False),
            block_illegal=dns_policies.get("block_illegal_content", False),
            block_violent=dns_policies.get("block_violent_content", False),
            # Note: Some fields might not be available in the API response
            adblock=False,
            adblock_plus=False,
            block_malware=False,
        )

    @field_validator("custom_block_list", mode="before")
    @classmethod
    def extract_custom_block_list(cls, v: Optional[List[str]], info: Any) -> List[str]:
        """Extract custom block list from premium_dns."""
        if v is not None:
            return v

        premium_dns = info.data.get("premium_dns", {})
        if not premium_dns:
            return []

        advanced_filters = premium_dns.get("advanced_content_filters", {})
        blocked_list = advanced_filters.get("blocked_list", [])
        return blocked_list if isinstance(blocked_list, list) else []

    @field_validator("custom_allow_list", mode="before")
    @classmethod
    def extract_custom_allow_list(cls, v: Optional[List[str]], info: Any) -> List[str]:
        """Extract custom allow list from premium_dns."""
        if v is not None:
            return v

        premium_dns = info.data.get("premium_dns", {})
        if not premium_dns:
            return []

        advanced_filters = premium_dns.get("advanced_content_filters", {})
        allowed_list = advanced_filters.get("allowed_list", [])
        return allowed_list if isinstance(allowed_list, list) else []

    @field_validator("premium_enabled", mode="before")
    @classmethod
    def compute_premium_enabled(cls, v: Optional[bool], info: Any) -> bool:
        """Compute premium enabled from premium_dns data."""
        if v is not None:
            return v

        premium_dns = info.data.get("premium_dns", {})
        if not premium_dns:
            return False

        # Check if any premium features are enabled
        ad_block_settings = premium_dns.get("ad_block_settings", {})
        if ad_block_settings.get("enabled", False):
            return True

        # Check if any DNS policies are enabled
        dns_policies = premium_dns.get("dns_policies", {})
        if any(dns_policies.values()):
            return True

        # Check if any advanced content filters are set
        advanced_filters = premium_dns.get("advanced_content_filters", {})
        if advanced_filters.get("blocked_list") or advanced_filters.get("allowed_list"):
            return True

        return False

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
