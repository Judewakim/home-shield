"""
Sale repository (persistence).

This module provides *only* persistence operations for the SaleRecord domain
entity. It does not enforce business rules (e.g., single-sale-per-bucket); it
only inserts and fetches sale records.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Mapping, Optional
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
        sale_id=UUID(str(row["sale_id"])),
        lead_id=UUID(str(row["lead_id"])),
        client_id=UUID(str(row["client_id"])),
        age_bucket=AgeBucket(str(row["age_bucket"])),
        sold_at=_parse_utc_datetime(row["sold_at_utc"]),
        purchase_price=Decimal(str(row["purchase_price"])),
        currency=str(row.get("currency", "USD")),
        payment_status=row.get("payment_status"),
        payment_transaction_id=row.get("payment_transaction_id"),
        created_at=_parse_utc_datetime(row["created_at_utc"]) if row.get("created_at_utc") else None,
    )


def record_sale(
    lead_id: UUID,
    client_id: UUID,
    bucket: AgeBucket,
    sold_at: datetime,
    purchase_price: Decimal,
    currency: str = "USD",
    payment_status: Optional[str] = None,
    payment_transaction_id: Optional[str] = None,
) -> SaleRecord:
    """
    Insert a new sale event into Supabase.

    Args:
        lead_id: Lead identifier
        client_id: Client (buyer) who purchased the lead
        bucket: AgeBucket associated with this sale
        sold_at: UTC timestamp for when the sale occurred
        purchase_price: Price paid for this lead
        currency: Currency code (default: USD)
        payment_status: Payment status (pending, completed, failed, refunded)
        payment_transaction_id: External payment processor transaction ID

    Returns:
        SaleRecord domain model with the recorded sale
    """

    # Generate a new sale_id
    sale_id = uuid4()
    now = datetime.now(timezone.utc)

    payload: dict[str, Any] = {
        "sale_id": str(sale_id),
        "lead_id": str(lead_id),
        "client_id": str(client_id),
        "age_bucket": bucket.value,
        "sold_at_utc": _to_iso_utc(sold_at, name="sold_at"),
        "purchase_price": str(purchase_price),
        "currency": currency,
        "payment_status": payment_status,
        "payment_transaction_id": payment_transaction_id,
        "created_at_utc": now.isoformat(),
    }

    response = supabase.table(_SALES_TABLE).insert(payload).execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to record sale: {error}")

    return SaleRecord(
        sale_id=sale_id,
        lead_id=lead_id,
        client_id=client_id,
        age_bucket=bucket,
        sold_at=sold_at,
        purchase_price=purchase_price,
        currency=currency,
        payment_status=payment_status,
        payment_transaction_id=payment_transaction_id,
        created_at=now,
    )


def list_sales_by_lead(lead_id: UUID) -> List[SaleRecord]:
    """
    Retrieve all sale records for a given lead.

    Returns:
        List[SaleRecord] (possibly empty)
    """

    response = supabase.table(_SALES_TABLE).select("*").eq("lead_id", str(lead_id)).execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to list sales: {error}")

    rows = getattr(response, "data", None) or []
    return [_row_to_sale(row) for row in rows]


def list_sales_by_client(client_id: UUID) -> List[SaleRecord]:
    """
    Retrieve all sale records for a given client (buyer purchase history).

    Args:
        client_id: Client (buyer) identifier

    Returns:
        List[SaleRecord] (possibly empty)
    """

    response = supabase.table(_SALES_TABLE).select("*").eq("client_id", str(client_id)).execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to list sales: {error}")

    rows = getattr(response, "data", None) or []
    return [_row_to_sale(row) for row in rows]


def get_sale_by_id(sale_id: UUID) -> Optional[SaleRecord]:
    """
    Retrieve a single sale record by its ID.

    Args:
        sale_id: Sale identifier

    Returns:
        SaleRecord or None if not found
    """

    response = (
        supabase.table(_SALES_TABLE)
        .select("*")
        .eq("sale_id", str(sale_id))
        .limit(1)
        .execute()
    )
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to get sale: {error}")

    rows = getattr(response, "data", None) or []

    if not rows:
        return None

    return _row_to_sale(rows[0])


def update_payment_status(
    sale_id: UUID,
    payment_status: str,
    payment_transaction_id: Optional[str] = None
) -> None:
    """
    Update the payment status and transaction ID for a sale.

    Args:
        sale_id: Sale identifier
        payment_status: New payment status (pending, completed, failed, refunded)
        payment_transaction_id: Optional external payment transaction ID
    """

    payload: dict[str, Any] = {
        "payment_status": payment_status,
    }

    if payment_transaction_id is not None:
        payload["payment_transaction_id"] = payment_transaction_id

    response = (
        supabase.table(_SALES_TABLE)
        .update(payload)
        .eq("sale_id", str(sale_id))
        .execute()
    )

    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to update payment status: {error}")


__all__ = [
    "record_sale",
    "list_sales_by_lead",
    "list_sales_by_client",
    "get_sale_by_id",
    "update_payment_status",
]


