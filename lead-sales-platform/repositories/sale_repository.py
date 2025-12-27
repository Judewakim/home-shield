"""
Sale repository (persistence).

This module provides *only* persistence operations for the SaleRecord domain
entity. It does not enforce business rules (e.g., single-sale-per-bucket); it
only inserts and fetches sale records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Mapping
from uuid import UUID, uuid4

from domain.age_bucket import AgeBucket
from domain.sale import SaleRecord
from domain.time import require_utc_timestamp
from repositories.client import supabase

# Supabase table name for sale records.
# Keep this aligned with your database schema.
_SALES_TABLE: str = "sales"


def _to_iso_utc(dt: datetime, *, name: str) -> str:
    """Serialize a UTC datetime to ISO-8601 (timezone-aware, offset 0)."""

    require_utc_timestamp(name, dt)
    return dt.astimezone(timezone.utc).isoformat()


def _parse_utc_datetime(value: Any) -> datetime:
    """
    Parse a Supabase timestamp into a timezone-aware UTC datetime.

    Supabase commonly returns ISO-8601 strings, sometimes with a trailing 'Z'.
    """

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError(f"Unsupported timestamp type: {type(value)!r}")

    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _row_to_sale(row: Mapping[str, Any]) -> SaleRecord:
    """Convert a Supabase row into a SaleRecord."""

    return SaleRecord(
        lead_id=UUID(str(row["lead_id"])),
        age_bucket=AgeBucket(str(row["age_bucket"])),
        sold_at=_parse_utc_datetime(row["sold_at_utc"]),
    )


def record_sale(lead_id: UUID, bucket: AgeBucket, sold_at: datetime) -> None:
    """
    Insert a new sale event into Supabase.

    Args:
    - lead_id: Lead identifier
    - bucket: AgeBucket associated with this sale
    - sold_at: UTC timestamp for when the sale occurred
    """

    # Generate a new sale_id
    sale_id = str(uuid4())

    payload: dict[str, Any] = {
        "sale_id": sale_id,
        "lead_id": str(lead_id),
        "age_bucket": bucket.value,
        "sold_at_utc": _to_iso_utc(sold_at, name="sold_at"),
    }

    response = supabase.table(_SALES_TABLE).insert(payload).execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to record sale: {error}")


def list_sales_by_lead(lead_id: UUID) -> List[SaleRecord]:
    """
    Retrieve all sale records for a given lead.

    Returns:
    - List[SaleRecord] (possibly empty)
    """

    response = supabase.table(_SALES_TABLE).select("*").eq("lead_id", str(lead_id)).execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to list sales: {error}")

    rows = getattr(response, "data", None) or []
    return [_row_to_sale(row) for row in rows]


__all__ = [
    "record_sale",
    "list_sales_by_lead",
]


