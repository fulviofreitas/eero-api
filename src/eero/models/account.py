"""Account-related models for the Eero API."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """Model representing an Eero user."""

    id: str = Field(..., description="Unique identifier for the user")
    name: Optional[str] = Field(None, description="User's name")
    email: str = Field(..., description="User's email address")
    phone: Optional[str] = Field(None, description="User's phone number")
    created_at: datetime = Field(..., description="When the user was created")
    role: str = Field(..., description="User's role (e.g., 'owner', 'member')")


class Account(BaseModel):
    """Model representing an Eero account."""

    id: Optional[str] = Field(None, description="Unique identifier for the account")
    name: Optional[str] = Field(None, description="Account name")
    users: List[User] = Field(default_factory=list, description="Users on this account")
    premium_status: Optional[str] = Field(None, description="Premium subscription status")
    premium_expiry: Optional[datetime] = Field(
        None, description="When premium subscription expires"
    )
    created_at: Optional[datetime] = Field(None, description="When account was created")

    class Config:
        """Pydantic model configuration."""

        populate_by_name = True
