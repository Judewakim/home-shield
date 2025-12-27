"""
Domain: Sale events.

Governed by:
- docs/behavior/lead_classification_and_inventory.md
- docs/ANCHOR.md

Contract excerpts relevant here:
- A Lead may be sold at most once per Age Bucket.
- Selling a Lead in one Age Bucket has no effect on eligibility in future buckets.

This module captures sale events. Eligibility decisions and enforcement live with
inventory tracking logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from .age_bucket import AgeBucket
from .time import require_utc_timestamp


@dataclass(frozen=True, slots=True)
class SaleRecord:
    """
    Immutable record of a sale event for a given (lead_id, age_bucket).

    All timestamps must be passed explicitly.
    """

    lead_id: UUID
    age_bucket: AgeBucket
    sold_at: datetime

    def __post_init__(self) -> None:
        require_utc_timestamp("sold_at", self.sold_at)

