"""
Domain: Inventory tracking for resale eligibility.

Governed by:
- docs/behavior/lead_classification_and_inventory.md
- docs/ANCHOR.md

Contract excerpts implemented here:
- Inventory records are defined per (lead_id, age_bucket).
- Uniqueness constraint: never more than one Inventory record for the same (lead_id, age_bucket).
- Availability: is_available is TRUE iff sold_at is NULL.
- Single-sale-per-bucket: a Lead may be sold at most once per Age Bucket; once sold in a bucket,
  that (lead_id, age_bucket) is permanently closed while future buckets remain eligible.

This module contains only pure domain entities/value objects: no I/O, no database, no frameworks.
All timestamps must be passed explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Mapping, Optional
from uuid import UUID

from age_bucket import AgeBucket
from sale import SaleRecord


def _require_utc_timestamp(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware (UTC)")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be a UTC timestamp (offset 0)")


@dataclass(frozen=True, slots=True)
class InventoryRecord:
    """
    Immutable record of sellable eligibility for a Lead within an AgeBucket.

    Notes from contract:
    - Inventory is derived, not manually created.
    - Historical Inventory records are immutable; this type models immutability by returning
      a new instance when sold_at is set.
    """

    inventory_id: str
    lead_id: UUID
    age_bucket: AgeBucket
    created_at: datetime
    sold_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        _require_utc_timestamp("created_at", self.created_at)
        if self.sold_at is not None:
            _require_utc_timestamp("sold_at", self.sold_at)

    @property
    def is_available(self) -> bool:
        """Availability is TRUE iff sold_at is NULL (contract)."""

        return self.sold_at is None

    def sold(self, sold_at: datetime) -> "InventoryRecord":
        """
        Return a new InventoryRecord marked as sold.

        Enforces the single-sale-per-bucket rule for this (lead_id, age_bucket).
        """

        _require_utc_timestamp("sold_at", sold_at)
        if self.sold_at is not None:
            raise ValueError("InventoryRecord is already sold for this age_bucket")
        return InventoryRecord(
            inventory_id=self.inventory_id,
            lead_id=self.lead_id,
            age_bucket=self.age_bucket,
            created_at=self.created_at,
            sold_at=sold_at,
        )


@dataclass(frozen=True, slots=True)
class InventoryLedger:
    """
    In-memory domain representation of inventory history for a single lead.

    Enforces:
    - Uniqueness constraint on (lead_id, age_bucket) within this ledger.
    - Single-sale-per-bucket by preventing selling an already-sold record.

    This is not a persistence model; it is a pure domain structure.
    """

    lead_id: UUID
    _by_bucket: Mapping[AgeBucket, InventoryRecord]

    @staticmethod
    def empty(lead_id: UUID) -> "InventoryLedger":
        return InventoryLedger(lead_id=lead_id, _by_bucket={})

    def get(self, bucket: AgeBucket) -> Optional[InventoryRecord]:
        return self._by_bucket.get(bucket)

    def has_record(self, bucket: AgeBucket) -> bool:
        return bucket in self._by_bucket

    def ensure_record(self, *, inventory_id: str, bucket: AgeBucket, created_at: datetime) -> "InventoryLedger":
        """
        Ensure an InventoryRecord exists for (lead_id, bucket).

        Contract requirement:
        - Inventory MUST be created when the Lead enters a new AgeBucket AND no record exists
          for (lead_id, age_bucket).
        """

        _require_utc_timestamp("created_at", created_at)

        existing = self._by_bucket.get(bucket)
        if existing is not None:
            return self

        record = InventoryRecord(
            inventory_id=inventory_id,
            lead_id=self.lead_id,
            age_bucket=bucket,
            created_at=created_at,
            sold_at=None,
        )
        updated: Dict[AgeBucket, InventoryRecord] = dict(self._by_bucket)
        updated[bucket] = record
        return InventoryLedger(lead_id=self.lead_id, _by_bucket=updated)

    def record_sale(self, *, bucket: AgeBucket, sold_at: datetime) -> tuple["InventoryLedger", SaleRecord]:
        """
        Record a sale for (lead_id, bucket).

        Enforces:
        - Single-sale-per-bucket (cannot sell twice in the same bucket).
        - Uniqueness: sale is recorded against the unique InventoryRecord for this bucket.
        """

        _require_utc_timestamp("sold_at", sold_at)

        record = self._by_bucket.get(bucket)
        if record is None:
            raise ValueError("No InventoryRecord exists for (lead_id, age_bucket)")

        updated_record = record.sold(sold_at)
        updated: Dict[AgeBucket, InventoryRecord] = dict(self._by_bucket)
        updated[bucket] = updated_record

        return (
            InventoryLedger(lead_id=self.lead_id, _by_bucket=updated),
            SaleRecord(lead_id=self.lead_id, age_bucket=bucket, sold_at=sold_at),
        )

