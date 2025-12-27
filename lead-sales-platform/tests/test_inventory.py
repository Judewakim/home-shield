"""
Tests for `domain/inventory.py`.

Covers contract rules:
- InventoryRecord availability is TRUE iff sold_at is NULL.
- Single-sale-per-bucket is enforced (cannot sell same (lead_id, age_bucket) twice).
- Ledger creates new bucket records when missing (ensure_record).
- Attempting to sell without an inventory record raises error.
- Attempting to sell an already sold record raises error.
- No side effects: ledger transitions return new instances; prior ledgers are unchanged.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from domain.age_bucket import AgeBucket
from domain.inventory import InventoryLedger, InventoryRecord


def test_inventory_record_is_available_true_iff_sold_at_is_none() -> None:
    """Verify `is_available` behaves correctly based on sold_at being NULL vs set."""

    lead_id = UUID("00000000-0000-0000-0000-000000000010")
    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sold_at = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

    r1 = InventoryRecord(
        inventory_id="inv-1",
        lead_id=lead_id,
        age_bucket=AgeBucket.MONTH_3_TO_5,
        created_at=created,
        sold_at=None,
    )
    assert r1.is_available is True

    r2 = InventoryRecord(
        inventory_id="inv-1",
        lead_id=lead_id,
        age_bucket=AgeBucket.MONTH_3_TO_5,
        created_at=created,
        sold_at=sold_at,
    )
    assert r2.is_available is False


def test_inventory_record_requires_utc_timestamps() -> None:
    """Verify created_at and sold_at enforce UTC timezone-aware timestamps."""

    lead_id = UUID("00000000-0000-0000-0000-000000000010")
    created_naive = datetime(2025, 1, 1, 0, 0, 0)
    created_utc = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sold_non_utc = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone(timedelta(hours=1)))

    with pytest.raises(ValueError):
        InventoryRecord(
            inventory_id="inv-1",
            lead_id=lead_id,
            age_bucket=AgeBucket.MONTH_3_TO_5,
            created_at=created_naive,
        )

    with pytest.raises(ValueError):
        InventoryRecord(
            inventory_id="inv-1",
            lead_id=lead_id,
            age_bucket=AgeBucket.MONTH_3_TO_5,
            created_at=created_utc,
            sold_at=sold_non_utc,
        )


def test_inventory_record_sold_returns_new_instance_and_keeps_original_unchanged() -> None:
    """Verify selling returns a new instance and does not mutate the original."""

    lead_id = UUID("00000000-0000-0000-0000-000000000010")
    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sold_at = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

    record = InventoryRecord(
        inventory_id="inv-1",
        lead_id=lead_id,
        age_bucket=AgeBucket.MONTH_3_TO_5,
        created_at=created,
        sold_at=None,
    )
    sold = record.sold(sold_at)

    assert record is not sold
    assert record.sold_at is None
    assert record.is_available is True

    assert sold.sold_at == sold_at
    assert sold.is_available is False
    assert sold.inventory_id == record.inventory_id
    assert sold.lead_id == record.lead_id
    assert sold.age_bucket == record.age_bucket
    assert sold.created_at == record.created_at


def test_inventory_record_cannot_be_sold_twice() -> None:
    """Verify attempting to sell an already sold record raises error."""

    lead_id = UUID("00000000-0000-0000-0000-000000000010")
    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sold_at = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

    record = InventoryRecord(
        inventory_id="inv-1",
        lead_id=lead_id,
        age_bucket=AgeBucket.MONTH_3_TO_5,
        created_at=created,
        sold_at=sold_at,
    )

    with pytest.raises(ValueError):
        record.sold(sold_at=datetime(2025, 1, 3, 0, 0, 0, tzinfo=timezone.utc))


def test_inventory_ledger_ensure_record_creates_bucket_record_when_missing_and_is_side_effect_free() -> None:
    """Verify ledger creates new buckets correctly and does not mutate prior ledger instance."""

    lead_id = UUID("00000000-0000-0000-0000-000000000010")
    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    ledger0 = InventoryLedger.empty(lead_id)
    assert ledger0.get(AgeBucket.MONTH_3_TO_5) is None

    ledger1 = ledger0.ensure_record(inventory_id="inv-1", bucket=AgeBucket.MONTH_3_TO_5, created_at=created)
    assert ledger1 is not ledger0
    assert ledger0.get(AgeBucket.MONTH_3_TO_5) is None

    rec = ledger1.get(AgeBucket.MONTH_3_TO_5)
    assert rec is not None
    assert rec.inventory_id == "inv-1"
    assert rec.lead_id == lead_id
    assert rec.age_bucket == AgeBucket.MONTH_3_TO_5
    assert rec.created_at == created
    assert rec.sold_at is None
    assert rec.is_available is True


def test_inventory_ledger_ensure_record_is_idempotent_for_existing_bucket() -> None:
    """Verify ensuring an existing record returns the same ledger and does not create duplicates."""

    lead_id = UUID("00000000-0000-0000-0000-000000000010")
    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

    ledger1 = InventoryLedger.empty(lead_id).ensure_record(
        inventory_id="inv-1", bucket=AgeBucket.MONTH_3_TO_5, created_at=created
    )
    ledger2 = ledger1.ensure_record(
        inventory_id="inv-2",
        bucket=AgeBucket.MONTH_3_TO_5,
        created_at=datetime(2025, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
    )

    assert ledger2 is ledger1
    rec = ledger2.get(AgeBucket.MONTH_3_TO_5)
    assert rec is not None
    assert rec.inventory_id == "inv-1"
    assert rec.created_at == created


def test_inventory_ledger_record_sale_requires_existing_record() -> None:
    """Verify attempting to sell when no InventoryRecord exists raises error."""

    lead_id = UUID("00000000-0000-0000-0000-000000000010")
    ledger = InventoryLedger.empty(lead_id)
    sold_at = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError):
        ledger.record_sale(bucket=AgeBucket.MONTH_3_TO_5, sold_at=sold_at)


def test_inventory_ledger_record_sale_marks_bucket_sold_and_returns_sale_record_without_affecting_other_buckets() -> None:
    """Verify a sale closes only the sold bucket and has no effect on other buckets."""

    lead_id = UUID("00000000-0000-0000-0000-000000000010")
    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sold_at = datetime(2025, 1, 3, 0, 0, 0, tzinfo=timezone.utc)

    ledger0 = InventoryLedger.empty(lead_id)
    ledger1 = ledger0.ensure_record(inventory_id="inv-3to5", bucket=AgeBucket.MONTH_3_TO_5, created_at=created)
    ledger2 = ledger1.ensure_record(inventory_id="inv-6to8", bucket=AgeBucket.MONTH_6_TO_8, created_at=created)

    # Sell MONTH_3_TO_5; MONTH_6_TO_8 must remain unaffected.
    ledger3, sale = ledger2.record_sale(bucket=AgeBucket.MONTH_3_TO_5, sold_at=sold_at)

    assert sale.lead_id == lead_id
    assert sale.age_bucket == AgeBucket.MONTH_3_TO_5
    assert sale.sold_at == sold_at

    rec_3to5_before = ledger2.get(AgeBucket.MONTH_3_TO_5)
    rec_6to8_before = ledger2.get(AgeBucket.MONTH_6_TO_8)
    assert rec_3to5_before is not None
    assert rec_6to8_before is not None
    assert rec_3to5_before.sold_at is None
    assert rec_6to8_before.sold_at is None

    rec_3to5_after = ledger3.get(AgeBucket.MONTH_3_TO_5)
    rec_6to8_after = ledger3.get(AgeBucket.MONTH_6_TO_8)
    assert rec_3to5_after is not None
    assert rec_6to8_after is not None
    assert rec_3to5_after.sold_at == sold_at
    assert rec_3to5_after.is_available is False
    assert rec_6to8_after.sold_at is None
    assert rec_6to8_after.is_available is True


def test_inventory_ledger_single_sale_per_bucket_enforced() -> None:
    """Verify attempting to sell a bucket twice raises error (single-sale-per-bucket)."""

    lead_id = UUID("00000000-0000-0000-0000-000000000010")
    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    sold1 = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    sold2 = datetime(2025, 1, 3, 0, 0, 0, tzinfo=timezone.utc)

    ledger0 = InventoryLedger.empty(lead_id).ensure_record(
        inventory_id="inv-1", bucket=AgeBucket.MONTH_3_TO_5, created_at=created
    )
    ledger1, _sale = ledger0.record_sale(bucket=AgeBucket.MONTH_3_TO_5, sold_at=sold1)

    with pytest.raises(ValueError):
        ledger1.record_sale(bucket=AgeBucket.MONTH_3_TO_5, sold_at=sold2)


def test_inventory_ledger_is_immutable_frozen_dataclass() -> None:
    """Verify ledger cannot be mutated directly (frozen entity)."""

    ledger = InventoryLedger.empty(UUID("00000000-0000-0000-0000-000000000010"))

    with pytest.raises(FrozenInstanceError):
        ledger.lead_id = UUID("00000000-0000-0000-0000-000000000011")  # type: ignore[misc]


