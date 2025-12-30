"""
Domain: Client (buyer) accounts.

Represents authenticated buyers who can purchase leads through the platform.
Supports multiple authentication methods (local password, OAuth2 providers).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from .time import require_utc_timestamp


@dataclass(frozen=True, slots=True)
class Client:
    """
    Client (buyer) account with authentication and status tracking.

    Supports:
    - Local authentication (email/password)
    - OAuth2 providers (Google, Microsoft, GitHub)
    - Account status management (active, suspended, closed)
    - Email verification
    """

    client_id: UUID
    email: str
    status: str  # active, suspended, closed

    # Optional profile information
    company_name: Optional[str] = None
    contact_name: Optional[str] = None
    phone: Optional[str] = None

    # Authentication
    auth_provider: Optional[str] = None  # local, google, microsoft, github
    auth_provider_user_id: Optional[str] = None  # OAuth provider's user ID
    email_verified: bool = False

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate timestamps are UTC-aware."""
        if self.created_at is not None:
            require_utc_timestamp("created_at", self.created_at)
        if self.updated_at is not None:
            require_utc_timestamp("updated_at", self.updated_at)
        if self.last_login_at is not None:
            require_utc_timestamp("last_login_at", self.last_login_at)

    def is_active(self) -> bool:
        """Check if client can make purchases."""
        return self.status == "active"

    def can_purchase(self) -> bool:
        """Check if client is eligible to purchase leads."""
        return self.is_active() and self.email_verified
