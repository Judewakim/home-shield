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
    """

    lead_id: UUID
    source: str
    state: str
    raw_payload: Mapping[str, Any]
    classification: LeadClassification
    created_at_utc: datetime

    def __post_init__(self) -> None:
        require_utc_timestamp("created_at_utc", self.created_at_utc)

