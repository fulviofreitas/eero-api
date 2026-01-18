"""Diagnostics models for Eero."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class DiagnosticsStatus(str, Enum):
    """Diagnostics status enumeration."""

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class DiagnosticsResult(BaseModel):
    """Diagnostics result model."""

    status: DiagnosticsStatus = Field(..., description="Current status of diagnostics")
    timestamp: Optional[datetime] = Field(None, description="Timestamp of the diagnostics")
    results: Optional[Dict[str, Any]] = Field(None, description="Diagnostics results")
    error: Optional[str] = Field(None, description="Error message if diagnostics failed")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class NetworkDiagnostics(BaseModel):
    """Network diagnostics model."""

    network_id: str = Field(..., description="Network ID")
    diagnostics: DiagnosticsResult = Field(..., description="Diagnostics result")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class DiagnosticsRequest(BaseModel):
    """Diagnostics request model."""

    network_id: str = Field(..., description="Network ID to run diagnostics on")
    force: bool = Field(False, description="Force new diagnostics run")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
