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
        # Core identifiers
        "lead_id": str(lead.lead_id),
        "created_at_utc": _to_iso_utc(lead.created_at_utc),
        "classification": lead.classification.value,
        "state": lead.state,
        "source": lead.source or "",

        # Mortgage identification
        "mortgage_id": lead.mortgage_id or "",
        "campaign_id": lead.campaign_id or "",
        "type": lead.type or "",
        "status": lead.status or "",

        # Contact information
        "full_name": lead.full_name or "",
        "first_name": lead.first_name or "",
        "last_name": lead.last_name or "",
        "co_borrower_name": lead.co_borrower_name or "",

        # Address fields
        "address": lead.address or "",
        "city": lead.city or "",
        "county": lead.county or "",
        "zip": lead.zip or "",

        # Financial information
        "mortgage_amount": lead.mortgage_amount or "",
        "lender": lead.lender or "",
        "sale_date": lead.sale_date or "",

        # Agent and contact details
        "agent_id": lead.agent_id or "",
        "call_in_phone_number": lead.call_in_phone_number or "",
        "borrower_phone": lead.borrower_phone or "",

        # Qualification fields
        "borrower_age": lead.borrower_age or "",
        "borrower_medical_issues": lead.borrower_medical_issues or "",
        "borrower_tobacco_use": lead.borrower_tobacco_use or "",
        "co_borrower": lead.co_borrower or "",

        # Original timestamp string
        "call_in_date": lead.call_in_date or "",
    }


def _row_to_lead(row: Mapping[str, Any]) -> Lead:
    """Convert a Supabase row into a domain Lead."""

    # Helper to convert empty strings to None
    def get_optional(key: str) -> str | None:
        value = row.get(key, "")
        return value if value else None

    return Lead(
        # Core identifiers (required)
        lead_id=UUID(str(row["lead_id"])),
        state=str(row["state"]),
        classification=LeadClassification(str(row["classification"])),
        created_at_utc=_parse_utc_datetime(row["created_at_utc"]),

        # Optional fields
        source=get_optional("source"),

        # Mortgage identification
        mortgage_id=get_optional("mortgage_id"),
        campaign_id=get_optional("campaign_id"),
        type=get_optional("type"),
        status=get_optional("status"),

        # Contact information
        full_name=get_optional("full_name"),
        first_name=get_optional("first_name"),
        last_name=get_optional("last_name"),
        co_borrower_name=get_optional("co_borrower_name"),

        # Address fields
        address=get_optional("address"),
        city=get_optional("city"),
        county=get_optional("county"),
        zip=get_optional("zip"),

        # Financial information
        mortgage_amount=get_optional("mortgage_amount"),
        lender=get_optional("lender"),
        sale_date=get_optional("sale_date"),

        # Agent and contact details
        agent_id=get_optional("agent_id"),
        call_in_phone_number=get_optional("call_in_phone_number"),
        borrower_phone=get_optional("borrower_phone"),

        # Qualification fields
        borrower_age=get_optional("borrower_age"),
        borrower_medical_issues=get_optional("borrower_medical_issues"),
        borrower_tobacco_use=get_optional("borrower_tobacco_use"),
        co_borrower=get_optional("co_borrower"),

        # Original timestamp string
        call_in_date=get_optional("call_in_date"),
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


def insert_leads_bulk(leads: List[Lead]) -> None:
    """
    Bulk insert multiple Leads into Supabase in a single request.

    This is more efficient than calling insert_lead() repeatedly for large batches.
    All leads are inserted in a single transaction - if any lead fails validation,
    the entire batch will fail.

    Args:
        leads: List of Lead domain objects to insert

    Raises:
        RuntimeError: If Supabase returns an error response
        ValueError/TypeError: For invalid domain values (e.g., timestamps)

    Notes:
        - Empty list is a no-op
        - Supabase typically supports 500-1000 rows per request
        - For error isolation, consider catching exceptions and falling back to
          insert_lead() for individual inserts
    """
    if not leads:
        return

    payloads = [_lead_to_row(lead) for lead in leads]
    response = supabase.table(_LEADS_TABLE).insert(payloads).execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to bulk insert {len(leads)} leads: {error}")


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
    "insert_leads_bulk",
    "get_lead_by_id",
    "list_leads_by_filter",
]


