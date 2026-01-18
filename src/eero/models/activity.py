"""Activity-related models for the Eero API (Eero Plus feature)."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class ActivityUsage(BaseModel):
    """Model representing data usage statistics."""

    download_bytes: int = Field(0, description="Total bytes downloaded")
    upload_bytes: int = Field(0, description="Total bytes uploaded")
    total_bytes: int = Field(0, description="Total bytes transferred")
    download_mbps: Optional[float] = Field(None, description="Download speed in Mbps")
    upload_mbps: Optional[float] = Field(None, description="Upload speed in Mbps")

    @property
    def download_mb(self) -> float:
        """Get download in megabytes."""
        return self.download_bytes / (1024 * 1024)

    @property
    def upload_mb(self) -> float:
        """Get upload in megabytes."""
        return self.upload_bytes / (1024 * 1024)

    @property
    def total_mb(self) -> float:
        """Get total in megabytes."""
        return self.total_bytes / (1024 * 1024)

    @property
    def download_gb(self) -> float:
        """Get download in gigabytes."""
        return self.download_bytes / (1024 * 1024 * 1024)

    @property
    def upload_gb(self) -> float:
        """Get upload in gigabytes."""
        return self.upload_bytes / (1024 * 1024 * 1024)

    @property
    def total_gb(self) -> float:
        """Get total in gigabytes."""
        return self.total_bytes / (1024 * 1024 * 1024)


class ClientActivity(BaseModel):
    """Model representing activity data for a single client/device."""

    url: Optional[str] = Field(None, description="Device URL")
    mac: Optional[str] = Field(None, description="Device MAC address")
    nickname: Optional[str] = Field(None, description="Device nickname")
    hostname: Optional[str] = Field(None, description="Device hostname")
    display_name: Optional[str] = Field(None, description="Display name")
    usage: Optional[ActivityUsage] = Field(None, description="Usage statistics")
    last_active: Optional[datetime] = Field(None, description="Last active time")
    connected: bool = Field(False, description="Whether device is currently connected")

    # Computed fields
    device_id: Optional[str] = Field(None, description="Extracted device ID from URL")

    def model_post_init(self, __context: Any) -> None:
        """Post-initialization hook to compute derived fields."""
        # Extract device ID from URL if not provided
        if not self.device_id and self.url:
            parts = self.url.split("/")
            if len(parts) >= 2:
                self.device_id = parts[-1]

    @property
    def name(self) -> str:
        """Get the best available name for the device."""
        return self.nickname or self.display_name or self.hostname or self.mac or "Unknown"


class ActivityCategory(BaseModel):
    """Model representing activity grouped by category."""

    name: str = Field(..., description="Category name")
    category_id: Optional[str] = Field(None, description="Category identifier")
    usage: Optional[ActivityUsage] = Field(None, description="Usage for this category")
    percentage: Optional[float] = Field(None, description="Percentage of total usage")
    icon: Optional[str] = Field(None, description="Category icon name")


class ActivityHistoryPoint(BaseModel):
    """Model representing a single point in activity history."""

    timestamp: datetime = Field(..., description="Timestamp for this data point")
    download_bytes: int = Field(0, description="Bytes downloaded")
    upload_bytes: int = Field(0, description="Bytes uploaded")


class ActivityHistory(BaseModel):
    """Model representing historical activity data."""

    period: str = Field(..., description="Time period (hour, day, week, month)")
    start_time: Optional[datetime] = Field(None, description="Start of period")
    end_time: Optional[datetime] = Field(None, description="End of period")
    data_points: List[ActivityHistoryPoint] = Field(
        default_factory=list, description="Historical data points"
    )
    total_usage: Optional[ActivityUsage] = Field(None, description="Total usage for period")


class NetworkActivity(BaseModel):
    """Model representing network-wide activity summary."""

    network_id: Optional[str] = Field(None, description="Network ID")
    total_usage: Optional[ActivityUsage] = Field(None, description="Total network usage")
    top_clients: List[ClientActivity] = Field(
        default_factory=list, description="Top clients by usage"
    )
    categories: List[ActivityCategory] = Field(
        default_factory=list, description="Usage by category"
    )
    active_client_count: int = Field(0, description="Number of active clients")
    premium_enabled: bool = Field(False, description="Whether Eero Plus is enabled")

    @field_validator("total_usage", mode="before")
    @classmethod
    def parse_total_usage(cls, v: Any) -> Optional[ActivityUsage]:
        """Parse total usage from various formats."""
        if v is None:
            return None
        if isinstance(v, ActivityUsage):
            return v
        if isinstance(v, dict):
            return ActivityUsage(
                download_bytes=v.get("download", v.get("download_bytes", 0)) or 0,
                upload_bytes=v.get("upload", v.get("upload_bytes", 0)) or 0,
                total_bytes=v.get("total", v.get("total_bytes", 0)) or 0,
                download_mbps=v.get("download_mbps"),
                upload_mbps=v.get("upload_mbps"),
            )
        return None

    @field_validator("top_clients", mode="before")
    @classmethod
    def parse_top_clients(cls, v: Any) -> List[ClientActivity]:
        """Parse top clients from various formats."""
        if v is None:
            return []
        if isinstance(v, list):
            return [ClientActivity.model_validate(c) if isinstance(c, dict) else c for c in v]
        return []

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
