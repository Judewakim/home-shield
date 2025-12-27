"""
Inventory repository (persistence).

This module provides *only* persistence operations for the InventoryRecord domain
entity. It contains no business rules about eligibility or bucketing; it only
enforces simple persistence constraints (e.g., uniqueness and conditional updates).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Mapping
from uuid import UUID, uuid4

from domain.age_bucket import AgeBucket
from domain.inventory import InventoryRecord
from domain.time import require_utc_timestamp
from repositories.client import supabase

# Supabase table name for Inventory records.
# Keep this aligned with your database schema.
_INVENTORY_TABLE: str = "inventory"


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


def _row_to_inventory(row: Mapping[str, Any]) -> InventoryRecord:
    """Convert a Supabase row into an InventoryRecord."""

    sold_at_val = row.get("sold_at_utc")
    return InventoryRecord(
        inventory_id=str(row["inventory_id"]),
        lead_id=UUID(str(row["lead_id"])),
        age_bucket=AgeBucket(str(row["age_bucket"])),
        created_at=_parse_utc_datetime(row["created_at_utc"]),
        sold_at=_parse_utc_datetime(sold_at_val) if sold_at_val is not None else None,
    )


def create_inventory_record(lead_id: UUID, bucket: AgeBucket, created_at: datetime) -> None:
    """
    Insert a new InventoryRecord into Supabase.

    Enforces:
    - Uniqueness constraint on (lead_id, age_bucket)

    Args:
    - lead_id: Lead identifier
    - bucket: AgeBucket for the inventory record
    - created_at: UTC timestamp when the inventory record is created
    """

    # Generate a new inventory_id
    inventory_id = str(uuid4())

    payload: dict[str, Any] = {
        "inventory_id": inventory_id,
        "lead_id": str(lead_id),
        "age_bucket": bucket.value,
        "created_at_utc": _to_iso_utc(created_at, name="created_at"),
        "sold_at_utc": None,
    }

    # Enforce uniqueness proactively to provide a clean, domain-friendly error.
    existing = (
        supabase.table(_INVENTORY_TABLE)
        .select("inventory_id")
        .eq("lead_id", str(lead_id))
        .eq("age_bucket", bucket.value)
        .limit(1)
        .execute()
    )
    existing_error = getattr(existing, "error", None)
    if existing_error:
        raise RuntimeError(f"Failed to check inventory uniqueness: {existing_error}")
    if getattr(existing, "data", None):
        raise ValueError("InventoryRecord already exists for (lead_id, age_bucket)")

    response = supabase.table(_INVENTORY_TABLE).insert(payload).execute()
    error = getattr(response, "error", None)
    if error:
        # If the DB also enforces uniqueness, surface it as a ValueError.
        code = getattr(error, "code", None)
        if str(code) == "23505":
            raise ValueError("InventoryRecord already exists for (lead_id, age_bucket)") from None
        raise RuntimeError(f"Failed to create inventory record: {error}")


def mark_inventory_sold(lead_id: UUID, bucket: AgeBucket, sold_at: datetime) -> None:
    """
    Mark an inventory record as sold by setting sold_at_utc.

    Requirements:
    - Must only update if sold_at_utc is currently NULL.
    """

    update_payload: dict[str, Any] = {"sold_at_utc": _to_iso_utc(sold_at, name="sold_at")}

    query = (
        supabase.table(_INVENTORY_TABLE)
        .update(update_payload)
        .eq("lead_id", str(lead_id))
        .eq("age_bucket", bucket.value)
    )

    # Apply a "sold_at_utc IS NULL" condition to ensure we only mark unsold inventory.
    if hasattr(query, "is_"):
        # postgrest-py style
        query = query.is_("sold_at_utc", "null")
    elif hasattr(query, "filter"):
        # fallback for older/different builders
        query = query.filter("sold_at_utc", "is", "null")

    response = query.execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to mark inventory sold: {error}")

    updated_rows = getattr(response, "data", None) or []
    if not updated_rows:
        # Either no record exists, or it was already sold (sold_at_utc not NULL).
        raise ValueError("InventoryRecord not found or already sold for (lead_id, age_bucket)")


def get_inventory_by_lead(lead_id: UUID) -> List[InventoryRecord]:
    """
    Fetch all inventory records for a given lead.

    Returns:
    - List[InventoryRecord] (possibly empty)
    """

    response = (
        supabase.table(_INVENTORY_TABLE).select("*").eq("lead_id", str(lead_id)).execute()
    )
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to fetch inventory records: {error}")

    rows = getattr(response, "data", None) or []
    return [_row_to_inventory(row) for row in rows]


__all__ = [
    "create_inventory_record",
    "mark_inventory_sold",
    "get_inventory_by_lead",
]


