"""
Domain: Age buckets and lead age calculation.

This module is governed by:
- docs/behavior/lead_classification_and_inventory.md
- docs/ANCHOR.md

Contract excerpts implemented here:
- Lead age is calculated in whole 24-hour days:
  age_days = floor((current_utc_time - received_at) / 24 hours)
- Buckets are defined strictly as:
  - DAY_0: age_days == 0
  - DAY_1: age_days == 1
  - DAY_2: age_days == 2
  - DAY_3_PLUS: age_days >= 3
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


def _require_utc_timestamp(name: str, value: datetime) -> None:
    """
    Enforces the contract requirement that timestamps are UTC.

    Invariants:
    - Timestamps must be timezone-aware.
    - Timestamps must have UTC offset 0.
    """

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware (UTC)")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"{name} must be a UTC timestamp (offset 0)")


class AgeBucket(str, Enum):
    DAY_0 = "DAY_0"
    DAY_1 = "DAY_1"
    DAY_2 = "DAY_2"
    DAY_3_PLUS = "DAY_3_PLUS"

    @staticmethod
    def from_age_days(age_days: int) -> "AgeBucket":
        """
        Resolve an AgeBucket from an integer age in days.

        Behavior is defined by the contract. No additional bucketing rules exist.
        """

        if age_days < 0:
            # The contract defines age_days from (current_utc_time - received_at).
            # A negative value indicates inconsistent inputs.
            raise ValueError("age_days must be >= 0")

        if age_days == 0:
            return AgeBucket.DAY_0
        if age_days == 1:
            return AgeBucket.DAY_1
        if age_days == 2:
            return AgeBucket.DAY_2
        return AgeBucket.DAY_3_PLUS


@dataclass(frozen=True, slots=True)
class LeadAge:
    """
    Value object for lead age evaluation.

    All timestamps must be passed explicitly; no implicit 'now' is used.
    """

    received_at: datetime
    current_utc_time: datetime

    def age_days(self) -> int:
        """
        Compute lead age in whole days per contract:

        age_days = floor((current_utc_time - received_at) / 24 hours)
        """

        _require_utc_timestamp("received_at", self.received_at)
        _require_utc_timestamp("current_utc_time", self.current_utc_time)

        if self.current_utc_time < self.received_at:
            raise ValueError("current_utc_time must be >= received_at")

        delta = self.current_utc_time - self.received_at
        return int(delta // timedelta(days=1))

    def bucket(self) -> AgeBucket:
        """Resolve the AgeBucket for this lead age per contract."""

        return AgeBucket.from_age_days(self.age_days())

