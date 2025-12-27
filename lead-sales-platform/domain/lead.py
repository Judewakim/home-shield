"""
Domain: Lead entity.

Governed by:
- docs/behavior/lead_classification_and_inventory.md
- docs/ANCHOR.md

Contract excerpts implemented here:
- A Lead represents a single consumer inquiry and is uniquely identified by lead_id (UUID).
- Classification occurs exactly once at ingestion time and must not change thereafter.
- Every Lead must be classified as exactly one of: Gold or Silver.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping
from uuid import UUID

from .time import require_utc_timestamp


class LeadClassification(str, Enum):
    GOLD = "Gold"
    SILVER = "Silver"


@dataclass(frozen=True, slots=True)
class Lead:
    """
    Pure domain entity for a Lead.

    Immutability:
    - This entity is frozen to prevent classification changes after ingestion.

    Notes:
    - This model does not evaluate Gold criteria; the contract states that criteria
      are defined externally and injected at runtime. This entity only stores the
      resulting classification.
    - All fields except lead_id, state, classification, and created_at_utc are optional
    - Empty strings from CSV are preserved as empty strings (not converted to None)
    """

    # Core identifiers (required)
    lead_id: UUID
    state: str
    classification: LeadClassification
    created_at_utc: datetime

    # Classification fields (optional - empty = Silver)
    source: str | None = None

    # Mortgage identification
    mortgage_id: str | None = None
    campaign_id: str | None = None
    type: str | None = None
    status: str | None = None

    # Contact information
    full_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    co_borrower_name: str | None = None

    # Address fields
    address: str | None = None
    city: str | None = None
    county: str | None = None
    zip: str | None = None

    # Financial information
    mortgage_amount: str | None = None
    lender: str | None = None
    sale_date: str | None = None

    # Agent and contact details
    agent_id: str | None = None
    call_in_phone_number: str | None = None
    borrower_phone: str | None = None

    # Qualification fields (for Gold/Silver classification)
    borrower_age: str | None = None
    borrower_medical_issues: str | None = None
    borrower_tobacco_use: str | None = None
    co_borrower: str | None = None  # Maps to "Co-Borrower ?" column

    # Original timestamp string
    call_in_date: str | None = None

    def __post_init__(self) -> None:
        require_utc_timestamp("created_at_utc", self.created_at_utc)

