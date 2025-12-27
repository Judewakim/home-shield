"""
Domain: Age buckets and lead age calculation.

This module is governed by:
- docs/behavior/lead_classification_and_inventory.md
- docs/ANCHOR.md

Contract excerpts implemented here:
- Lead age is calculated in whole 24-hour days:
  age_days = floor((as_of_utc - created_at_utc) / 24 hours)
- Months are fixed 30-day intervals:
  age_months = floor(age_days / 30)
- Buckets are defined strictly as:
  - MONTH_3_TO_5: age_days ∈ [  90, 179 ]
  - MONTH_6_TO_8: age_days ∈ [ 180, 269 ]
  - MONTH_9_TO_11: age_days ∈ [ 270, 359 ]
  - MONTH_12_TO_23: age_days ∈ [ 360, 719 ]
  - MONTH_24_PLUS: age_days ≥ 720

Leads with age_days < 90 do not fall into any bucket and are not sellable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from .time import require_utc_timestamp  # type: ignore[import-untyped]


class AgeBucket(str, Enum):
    MONTH_3_TO_5 = "MONTH_3_TO_5"
    MONTH_6_TO_8 = "MONTH_6_TO_8"
    MONTH_9_TO_11 = "MONTH_9_TO_11"
    MONTH_12_TO_23 = "MONTH_12_TO_23"
    MONTH_24_PLUS = "MONTH_24_PLUS"

    @staticmethod
    def for_age_days(age_days: int) -> Optional["AgeBucket"]:
        """
        Resolve an AgeBucket from an integer age in days.

        Returns None if the lead does not fall into any bucket (age_days < 90).
        Behavior is defined by the contract. No additional bucketing rules exist.
        """

        if age_days < 0:
            # The contract defines age_days from (as_of_utc - created_at_utc).
            # A negative value indicates inconsistent inputs.
            raise ValueError("age_days must be >= 0")

        if age_days < 90:
            return None
        if 90 <= age_days <= 179:
            return AgeBucket.MONTH_3_TO_5
        if 180 <= age_days <= 269:
            return AgeBucket.MONTH_6_TO_8
        if 270 <= age_days <= 359:
            return AgeBucket.MONTH_9_TO_11
        if 360 <= age_days <= 719:
            return AgeBucket.MONTH_12_TO_23
        return AgeBucket.MONTH_24_PLUS

    @staticmethod
    def from_age_days(age_days: int) -> "AgeBucket":
        """
        Resolve an AgeBucket from an integer age in days.

        Raises if no bucket exists for the age (age_days < 90).
        """

        bucket = AgeBucket.for_age_days(age_days)
        if bucket is None:
            raise ValueError("age_days is not eligible for any AgeBucket")
        return bucket


@dataclass(frozen=True, slots=True)
class LeadAge:
    """
    Value object for lead age evaluation.

    All timestamps must be passed explicitly; no implicit 'now' is used.
    """

    created_at_utc: datetime
    as_of_utc: datetime

    def age_days(self) -> int:
        """
        Compute lead age in whole days per contract:

        age_days = floor((as_of_utc - created_at_utc) / 24 hours)
        """

        require_utc_timestamp("created_at_utc", self.created_at_utc)
        require_utc_timestamp("as_of_utc", self.as_of_utc)

        if self.as_of_utc < self.created_at_utc:
            raise ValueError("as_of_utc must be >= created_at_utc")

        delta = self.as_of_utc - self.created_at_utc
        return int(delta // timedelta(days=1))

    def age_months(self) -> int:
        """
        Months are fixed 30-day intervals per contract:

        age_months = floor(age_days / 30)
        """

        return self.age_days() // 30

    def bucket(self) -> Optional[AgeBucket]:
        """Resolve the AgeBucket for this lead age per contract (or None if no bucket applies)."""

        return AgeBucket.for_age_days(self.age_days())

