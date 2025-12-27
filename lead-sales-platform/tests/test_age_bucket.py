"""
Tests for `domain/age_bucket.py`.

Covers contract rules:
- Age bucket boundaries are defined strictly by day ranges.
- Leads with age_days < 90 are not in any bucket (None).
- Negative ages and inconsistent timestamps raise errors.
- All timestamps passed to LeadAge must be UTC timezone-aware.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from domain.age_bucket import AgeBucket, LeadAge


@pytest.mark.parametrize(
    "age_days, expected",
    [
        (0, None),
        (89, None),
        (90, AgeBucket.MONTH_3_TO_5),
        (179, AgeBucket.MONTH_3_TO_5),
        (180, AgeBucket.MONTH_6_TO_8),
        (269, AgeBucket.MONTH_6_TO_8),
        (270, AgeBucket.MONTH_9_TO_11),
        (359, AgeBucket.MONTH_9_TO_11),
        (360, AgeBucket.MONTH_12_TO_23),
        (719, AgeBucket.MONTH_12_TO_23),
        (720, AgeBucket.MONTH_24_PLUS),
        (1000, AgeBucket.MONTH_24_PLUS),
    ],
)
def test_age_bucket_for_age_days_boundaries(age_days: int, expected: AgeBucket | None) -> None:
    """Verify age_days → bucket mapping for boundary days and out-of-bucket ages."""

    assert AgeBucket.for_age_days(age_days) == expected


def test_age_bucket_for_age_days_negative_raises() -> None:
    """Verify invalid input (negative age_days) raises error."""

    with pytest.raises(ValueError):
        AgeBucket.for_age_days(-1)


def test_age_bucket_from_age_days_under_90_raises() -> None:
    """Verify from_age_days raises when the lead does not fall into any bucket (age_days < 90)."""

    with pytest.raises(ValueError):
        AgeBucket.from_age_days(0)


def test_lead_age_age_days_floors_partial_days() -> None:
    """Verify age_days uses floor of whole 24-hour days (partial days not rounded up)."""

    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    as_of_just_under_24h = created + timedelta(hours=23, minutes=59, seconds=59)
    as_of_exact_24h = created + timedelta(days=1)

    assert LeadAge(created_at_utc=created, as_of_utc=as_of_just_under_24h).age_days() == 0
    assert LeadAge(created_at_utc=created, as_of_utc=as_of_exact_24h).age_days() == 1


@pytest.mark.parametrize(
    "age_days, expected_months",
    [
        (0, 0),
        (29, 0),
        (30, 1),
        (59, 1),
        (60, 2),
        (89, 2),
        (90, 3),
    ],
)
def test_lead_age_age_months_uses_fixed_30_day_intervals(age_days: int, expected_months: int) -> None:
    """Verify age_months = floor(age_days / 30) using fixed 30-day intervals (no calendar months)."""

    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    as_of = created + timedelta(days=age_days)
    assert LeadAge(created_at_utc=created, as_of_utc=as_of).age_months() == expected_months


def test_lead_age_bucket_none_when_under_90_days() -> None:
    """Verify LeadAge.bucket() returns None for age_days < 90."""

    created = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    as_of = created + timedelta(days=89)
    assert LeadAge(created_at_utc=created, as_of_utc=as_of).bucket() is None


def test_lead_age_inconsistent_timestamps_raise() -> None:
    """Verify as_of_utc < created_at_utc raises error (negative age)."""

    created = datetime(2025, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    as_of = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        LeadAge(created_at_utc=created, as_of_utc=as_of).age_days()


def test_lead_age_requires_utc_timestamps() -> None:
    """Verify UTC timestamp enforcement for created_at_utc and as_of_utc."""

    naive = datetime(2025, 1, 1, 0, 0, 0)
    utc = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    non_utc = datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone(timedelta(hours=-5)))

    with pytest.raises(ValueError):
        LeadAge(created_at_utc=naive, as_of_utc=utc).age_days()
    with pytest.raises(ValueError):
        LeadAge(created_at_utc=utc, as_of_utc=naive).age_days()
    with pytest.raises(ValueError):
        LeadAge(created_at_utc=non_utc, as_of_utc=utc).age_days()
    with pytest.raises(ValueError):
        LeadAge(created_at_utc=utc, as_of_utc=non_utc).age_days()


