"""Pydantic models for the Eero API responses."""

from .account import Account, User
from .activity import (
    ActivityCategory,
    ActivityHistory,
    ActivityHistoryPoint,
    ActivityUsage,
    ClientActivity,
    NetworkActivity,
)
from .device import Device
from .diagnostics import (
    DiagnosticsRequest,
    DiagnosticsResult,
    DiagnosticsStatus,
    NetworkDiagnostics,
)
from .eero import Eero
from .network import Network
from .profile import Profile

__all__ = [
    "Account",
    "ActivityCategory",
    "ActivityHistory",
    "ActivityHistoryPoint",
    "ActivityUsage",
    "ClientActivity",
    "Device",
    "DiagnosticsRequest",
    "DiagnosticsResult",
    "DiagnosticsStatus",
    "Eero",
    "Network",
    "NetworkActivity",
    "NetworkDiagnostics",
    "Profile",
    "User",
]
