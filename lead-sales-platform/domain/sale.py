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
from decimal import Decimal
from typing import Optional
from uuid import UUID

from .age_bucket import AgeBucket
from .time import require_utc_timestamp


@dataclass(frozen=True, slots=True)
class SaleRecord:
    """
    Immutable record of a sale event for a given (lead_id, age_bucket).

    Captures the complete sale transaction including:
    - Who bought it (client_id)
    - What was purchased (lead_id + age_bucket)
    - When it was sold (sold_at)
    - How much was paid (purchase_price)
    - Payment status and transaction tracking

    All timestamps must be passed explicitly.
    """

    sale_id: UUID
    lead_id: UUID
    client_id: UUID
    age_bucket: AgeBucket
    sold_at: datetime
    purchase_price: Decimal
    currency: str
    payment_status: Optional[str] = None  # pending, completed, failed, refunded
    payment_transaction_id: Optional[str] = None  # External payment processor ID (e.g., Stripe)
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        require_utc_timestamp("sold_at", self.sold_at)
        if self.created_at is not None:
            require_utc_timestamp("created_at", self.created_at)

