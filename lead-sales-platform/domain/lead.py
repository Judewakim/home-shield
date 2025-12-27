"""
Domain: Lead entity.

Governed by:
- docs/behavior/lead_classification_and_inventory.md
- docs/ANCHOR.md

Contract excerpts implemented here:
- A Lead represents a single consumer inquiry and is uniquely identified by lead_id (UUID).
- received_at is a UTC timestamp and is authoritative.
- Classification occurs exactly once at ingestion time and must not change thereafter.
- Every Lead must be classified as exactly one of: Gold or Silver.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Mapping
from uuid import UUID


def _require_utc_timestamp(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware (UTC)")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be a UTC timestamp (offset 0)")


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
    received_at: datetime
    source: str
    state: str
    raw_payload: Mapping[str, Any]
    classification: LeadClassification
    created_at: datetime

    def __post_init__(self) -> None:
        _require_utc_timestamp("received_at", self.received_at)
        _require_utc_timestamp("created_at", self.created_at)

