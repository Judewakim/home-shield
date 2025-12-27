"""
Lead repository (persistence).

This module provides *only* persistence operations for the Lead domain entity.
No business rules (classification, age buckets, inventory eligibility) belong here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Mapping
from uuid import UUID

from domain.lead import Lead, LeadClassification
from repositories.client import supabase

# Supabase table name for Lead records.
# Keep this aligned with your database schema.
_LEADS_TABLE: str = "leads"


def _to_iso_utc(dt: datetime) -> str:
    """
    Convert a timezone-aware datetime to an ISO-8601 string in UTC.

    Notes:
    - Domain objects require UTC timestamps (offset 0). We still normalize via
      `astimezone(timezone.utc)` for safety.
    """

    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("created_at_utc must be timezone-aware (UTC)")
    return dt.astimezone(timezone.utc).isoformat()


def _parse_utc_datetime(value: Any) -> datetime:
    """
    Parse a Supabase timestamp into a timezone-aware UTC datetime.

    Supabase commonly returns ISO-8601 strings, sometimes with a trailing 'Z'.
    """

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        # Python's fromisoformat doesn't consistently accept 'Z' across versions.
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    else:
        raise TypeError(f"Unsupported timestamp type: {type(value)!r}")

    # If the backend returns a naive timestamp, interpret it as UTC so that the
    # domain model's UTC invariant is satisfied.
    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def _lead_to_row(lead: Lead) -> dict[str, Any]:
    """Convert a domain Lead to a Supabase row payload."""

    return {
        "lead_id": str(lead.lead_id),
        "created_at_utc": _to_iso_utc(lead.created_at_utc),
        "classification": lead.classification.value,
        "source": lead.source,
        "state": lead.state,
        "raw_payload": dict(lead.raw_payload),
    }


def _row_to_lead(row: Mapping[str, Any]) -> Lead:
    """Convert a Supabase row into a domain Lead."""

    return Lead(
        lead_id=UUID(str(row["lead_id"])),
        source=str(row["source"]),
        state=str(row["state"]),
        raw_payload=row.get("raw_payload") or {},
        classification=LeadClassification(str(row["classification"])),
        created_at_utc=_parse_utc_datetime(row["created_at_utc"]),
    )


def insert_lead(lead: Lead) -> None:
    """
    Insert a Lead into Supabase.

    Raises:
    - RuntimeError if Supabase returns an error response.
    - ValueError/TypeError for invalid domain values (e.g., timestamps).
    """

    payload = _lead_to_row(lead)
    response = supabase.table(_LEADS_TABLE).insert(payload).execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to insert lead: {error}")


def get_lead_by_id(lead_id: UUID) -> Lead | None:
    """
    Fetch a Lead by ID.

    Returns:
    - Lead if found
    - None if no record exists for the given ID
    """

    response = (
        supabase.table(_LEADS_TABLE)
        .select("*")
        .eq("lead_id", str(lead_id))
        .limit(1)
        .execute()
    )
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to fetch lead: {error}")

    rows = getattr(response, "data", None) or []
    if not rows:
        return None
    return _row_to_lead(rows[0])


def list_leads_by_filter(
    state: str | None = None,
    classification: str | None = None,
) -> List[Lead]:
    """
    List Leads with optional filtering by state and/or classification.

    Args:
    - state: filter by Lead.state (exact match)
    - classification: filter by classification string (e.g., "Gold" or "Silver")
    """

    query = supabase.table(_LEADS_TABLE).select("*")
    if state is not None:
        query = query.eq("state", state)
    if classification is not None:
        query = query.eq("classification", classification)

    response = query.execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to list leads: {error}")

    rows = getattr(response, "data", None) or []
    return [_row_to_lead(row) for row in rows]


__all__ = [
    "insert_lead",
    "get_lead_by_id",
    "list_leads_by_filter",
]


