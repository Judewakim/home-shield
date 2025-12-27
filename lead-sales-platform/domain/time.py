"""
Domain time utilities (pure).

Centralized timestamp validation helper.

Behavior and error messages must remain consistent across the domain model.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def require_utc_timestamp(name: str, value: datetime) -> None:
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


