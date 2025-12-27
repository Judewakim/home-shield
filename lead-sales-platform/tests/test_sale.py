"""
Tests for `domain/sale.py`.

Covers contract rules:
- SaleRecord.sold_at is required and must be a UTC timestamp.
- SaleRecord is immutable (frozen).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from domain.age_bucket import AgeBucket
from domain.sale import SaleRecord


def test_sale_record_sold_at_must_be_utc() -> None:
    """Verify sold_at enforces UTC timezone-aware timestamp."""

    lead_id = UUID("00000000-0000-0000-0000-000000000020")

    with pytest.raises(ValueError):
        SaleRecord(lead_id=lead_id, age_bucket=AgeBucket.MONTH_3_TO_5, sold_at=datetime(2025, 1, 1, 0, 0, 0))

    with pytest.raises(ValueError):
        SaleRecord(
            lead_id=lead_id,
            age_bucket=AgeBucket.MONTH_3_TO_5,
            sold_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=2))),
        )


def test_sale_record_is_immutable() -> None:
    """Verify SaleRecord cannot be mutated after creation (frozen entity)."""

    sale = SaleRecord(
        lead_id=UUID("00000000-0000-0000-0000-000000000020"),
        age_bucket=AgeBucket.MONTH_3_TO_5,
        sold_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(FrozenInstanceError):
        sale.age_bucket = AgeBucket.MONTH_6_TO_8  # type: ignore[misc]


