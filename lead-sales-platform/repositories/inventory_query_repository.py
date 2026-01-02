"""
Inventory query repository for browsing available leads.

This module provides optimized queries for the inventory browsing system.
Performance-critical operations use database indexes and query optimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Mapping, Optional
from uuid import UUID

from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.client import supabase


@dataclass(frozen=True, slots=True)
class AvailableInventoryItem:
    """
    Read model for browsing available inventory.

    Combines lead data with inventory metadata for efficient querying.
    """
    # Inventory fields
    inventory_id: UUID
    lead_id: UUID
    age_bucket: AgeBucket
    created_at_utc: datetime

    # Lead fields (denormalized for query efficiency)
    state: str
    county: Optional[str]
    classification: LeadClassification

    # Contact preview (for buyers to assess lead quality)
    first_name: Optional[str]
    last_name: Optional[str]
    city: Optional[str]
    zip: Optional[str]
    mortgage_amount: Optional[str]
    borrower_age: Optional[str]
    borrower_phone: Optional[str]


@dataclass(frozen=True, slots=True)
class InventoryQueryFilters:
    """Filter criteria for inventory queries."""
    age_buckets: Optional[List[AgeBucket]] = None
    states: Optional[List[str]] = None
    counties: Optional[List[str]] = None
    classifications: Optional[List[LeadClassification]] = None
    available_only: bool = True  # Default: only show available inventory


@dataclass(frozen=True, slots=True)
class MixedInventoryRequest:
    """
    Request for a specific quantity of leads with specific classification and age bucket.

    Used for complex multi-part queries like:
    - "300 Silver leads that are 6-8 months old"
    - "100 Gold leads that are 9-11 months old in Louisiana"

    Example:
        MixedInventoryRequest(
            classification=LeadClassification.SILVER,
            age_bucket=AgeBucket.MONTH_6_TO_8,
            quantity=300,
            states=["LA"],
            counties=None
        )
    """
    classification: LeadClassification
    age_bucket: AgeBucket
    quantity: int
    states: Optional[List[str]] = None
    counties: Optional[List[str]] = None


def _parse_utc_datetime(value: Any) -> datetime:
    """Parse a Supabase timestamp into a timezone-aware UTC datetime."""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        text = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    else:
        raise TypeError(f"Unsupported timestamp type: {type(value)!r}")

    if dt.tzinfo is None or dt.utcoffset() is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def query_available_inventory(
    filters: InventoryQueryFilters,
    limit: int = 100,
    offset: int = 0
) -> List[AvailableInventoryItem]:
    """
    Query available inventory with filters.

    Performance optimizations:
    - Uses JOIN to fetch lead data in single query
    - Leverages partial index on (sold_at_utc IS NULL)
    - Limits result set to prevent large data transfers

    Args:
        filters: Query filters
        limit: Maximum number of results (default 100)
        offset: Pagination offset (default 0)

    Returns:
        List of AvailableInventoryItem matching filters
    """
    # Build query with INNER JOIN
    # Note: !inner forces INNER JOIN to exclude inventory without matching leads
    query = (
        supabase.table("inventory")
        .select(
            "inventory_id, lead_id, age_bucket, created_at_utc, "
            "leads!inner(state, county, classification, first_name, last_name, "
            "city, zip, mortgage_amount, borrower_age, borrower_phone)"
        )
    )

    # Apply filters
    if filters.available_only:
        query = query.is_("sold_at_utc", "null")

    if filters.age_buckets:
        query = query.in_("age_bucket", [b.value for b in filters.age_buckets])

    if filters.states:
        query = query.in_("leads.state", filters.states)

    if filters.counties:
        query = query.in_("leads.county", filters.counties)

    if filters.classifications:
        query = query.in_("leads.classification", [c.value for c in filters.classifications])

    # Pagination
    # Note: Use .limit() instead of .range() to avoid off-by-one issues with joins
    if offset == 0:
        query = query.limit(limit)
    else:
        query = query.range(offset, offset + limit - 1)

    # Execute
    response = query.execute()
    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to query inventory: {error}")

    rows = getattr(response, "data", None) or []

    # Transform to domain models
    results = []
    for row in rows:
        lead_data = row.get("leads")

        # Skip rows where lead data is missing (shouldn't happen with !inner join)
        if not lead_data:
            continue

        results.append(AvailableInventoryItem(
            inventory_id=UUID(str(row["inventory_id"])),
            lead_id=UUID(str(row["lead_id"])),
            age_bucket=AgeBucket(str(row["age_bucket"])),
            created_at_utc=_parse_utc_datetime(row["created_at_utc"]),
            state=str(lead_data["state"]),
            county=lead_data.get("county"),
            classification=LeadClassification(str(lead_data["classification"])),
            first_name=lead_data.get("first_name"),
            last_name=lead_data.get("last_name"),
            city=lead_data.get("city"),
            zip=lead_data.get("zip"),
            mortgage_amount=lead_data.get("mortgage_amount"),
            borrower_age=lead_data.get("borrower_age"),
            borrower_phone=lead_data.get("borrower_phone"),
        ))

    return results


def query_mixed_inventory(
    requests: List[MixedInventoryRequest]
) -> List[AvailableInventoryItem]:
    """
    Query for complex multi-part inventory requests.

    Executes multiple queries for specific classification+age bucket combinations
    and combines the results. Useful for scenarios like:
    - "I want 300 Silver leads aged 6-8 months + 100 Gold leads aged 6-8 months"
    - "I want 100 Silver leads aged 9-11 months in LA + 100 Gold leads aged 3-5 months in TX"

    Args:
        requests: List of MixedInventoryRequest specifying what to fetch

    Returns:
        Combined list of all requested inventory items

    Example:
        requests = [
            MixedInventoryRequest(
                classification=LeadClassification.SILVER,
                age_bucket=AgeBucket.MONTH_6_TO_8,
                quantity=300,
                states=["LA"]
            ),
            MixedInventoryRequest(
                classification=LeadClassification.GOLD,
                age_bucket=AgeBucket.MONTH_6_TO_8,
                quantity=100,
                states=["LA"]
            ),
        ]
        leads = query_mixed_inventory(requests)
        # Returns 400 total leads (300 Silver + 100 Gold, all 6-8 months old in LA)
    """
    all_results = []

    for request in requests:
        # Build filters for this specific request
        filters = InventoryQueryFilters(
            classifications=[request.classification],
            age_buckets=[request.age_bucket],
            states=request.states,
            counties=request.counties,
            available_only=True
        )

        # Query with the requested quantity
        results = query_available_inventory(
            filters=filters,
            limit=request.quantity
        )

        all_results.extend(results)

    return all_results


def get_inventory_counts(
    filters: InventoryQueryFilters
) -> dict[AgeBucket, int]:
    """
    Get counts of available inventory grouped by age bucket.

    Useful for UI to show "25 leads in MONTH_3_TO_5, 40 in MONTH_6_TO_8", etc.

    Args:
        filters: Query filters (same as query_available_inventory)

    Returns:
        Dictionary mapping AgeBucket to count
    """
    # Build base query
    query = supabase.table("inventory").select("age_bucket", count="exact")

    # Apply filters
    if filters.available_only:
        query = query.is_("sold_at_utc", "null")

    if filters.age_buckets:
        query = query.in_("age_bucket", [b.value for b in filters.age_buckets])

    # For state/county/classification filters, we need to join with leads
    # Supabase doesn't support GROUP BY in the Python client easily,
    # so we'll fetch all and group in Python
    if filters.states or filters.counties or filters.classifications:
        # Fetch with lead data and pagination
        # First get total count
        count_query = supabase.table("inventory").select("*", count="exact")

        if filters.available_only:
            count_query = count_query.is_("sold_at_utc", "null")

        count_response = count_query.execute()
        total_count = getattr(count_response, "count", 0) or 0

        # Fetch all with pagination
        all_rows = []
        page_size = 1000
        offset = 0

        while offset < total_count:
            query_page = supabase.table("inventory").select("""
                age_bucket,
                leads!inner(state, county, classification)
            """)

            if filters.available_only:
                query_page = query_page.is_("sold_at_utc", "null")

            if filters.states:
                query_page = query_page.in_("leads.state", filters.states)

            if filters.counties:
                query_page = query_page.in_("leads.county", filters.counties)

            if filters.classifications:
                query_page = query_page.in_("leads.classification", [c.value for c in filters.classifications])

            query_page = query_page.range(offset, offset + page_size - 1)
            response_page = query_page.execute()

            error = getattr(response_page, "error", None)
            if error:
                raise RuntimeError(f"Failed to get inventory counts: {error}")

            page_rows = getattr(response_page, "data", None) or []
            if not page_rows:
                break

            all_rows.extend(page_rows)
            offset += len(page_rows)

        # Group by age_bucket in Python
        counts: dict[AgeBucket, int] = {}
        for row in all_rows:
            bucket = AgeBucket(str(row["age_bucket"]))
            counts[bucket] = counts.get(bucket, 0) + 1

        return counts

    else:
        # Simple case: no lead filters, fetch all with pagination
        # Get total count first
        count_query = supabase.table("inventory").select("*", count="exact")
        if filters.available_only:
            count_query = count_query.is_("sold_at_utc", "null")

        count_response = count_query.execute()
        total_count = getattr(count_response, "count", 0) or 0

        # Fetch all with pagination
        all_rows = []
        page_size = 1000
        offset = 0

        while offset < total_count:
            query_page = supabase.table("inventory").select("age_bucket")

            if filters.available_only:
                query_page = query_page.is_("sold_at_utc", "null")

            query_page = query_page.range(offset, offset + page_size - 1)
            response_page = query_page.execute()

            error = getattr(response_page, "error", None)
            if error:
                raise RuntimeError(f"Failed to get inventory counts: {error}")

            page_rows = getattr(response_page, "data", None) or []
            if not page_rows:
                break

            all_rows.extend(page_rows)
            offset += len(page_rows)

        # Group by age_bucket
        counts: dict[AgeBucket, int] = {}
        for row in all_rows:
            bucket = AgeBucket(str(row["age_bucket"]))
            counts[bucket] = counts.get(bucket, 0) + 1

        return counts


def get_inventory_summary() -> dict[str, Any]:
    """
    Get overall inventory summary statistics.

    Returns:
        Dictionary with summary stats: {
            'total_available': int,
            'total_sold': int,
            'by_bucket': dict[AgeBucket, int],
            'by_classification': dict[LeadClassification, int]
        }
    """
    # Count available inventory
    available_response = (
        supabase.table("inventory")
        .select("*", count="exact")
        .is_("sold_at_utc", "null")
        .execute()
    )

    available_count = getattr(available_response, "count", 0) or 0

    # Count sold inventory
    sold_response = (
        supabase.table("inventory")
        .select("*", count="exact")
        .not_.is_("sold_at_utc", "null")
        .execute()
    )

    sold_count = getattr(sold_response, "count", 0) or 0

    # Get available inventory by bucket
    filters = InventoryQueryFilters(available_only=True)
    by_bucket = get_inventory_counts(filters)

    # Get available inventory by classification with pagination
    # Need to join with leads table
    # Get total available count (we already have this from available_count)
    all_rows = []
    page_size = 1000
    offset = 0

    while offset < available_count:
        query_page = (
            supabase.table("inventory")
            .select("leads!inner(classification)")
            .is_("sold_at_utc", "null")
            .range(offset, offset + page_size - 1)
            .execute()
        )

        error = getattr(query_page, "error", None)
        if error:
            raise RuntimeError(f"Failed to get inventory summary: {error}")

        page_rows = getattr(query_page, "data", None) or []
        if not page_rows:
            break

        all_rows.extend(page_rows)
        offset += len(page_rows)

    # Group by classification
    by_classification: dict[LeadClassification, int] = {}
    for row in all_rows:
        lead_data = row.get("leads")
        if lead_data:
            classification = LeadClassification(str(lead_data["classification"]))
            by_classification[classification] = by_classification.get(classification, 0) + 1

    return {
        'total_available': available_count,
        'total_sold': sold_count,
        'by_bucket': {bucket.value: count for bucket, count in by_bucket.items()},
        'by_classification': {cls.value: count for cls, count in by_classification.items()},
    }


__all__ = [
    "AvailableInventoryItem",
    "InventoryQueryFilters",
    "MixedInventoryRequest",
    "query_available_inventory",
    "query_mixed_inventory",
    "get_inventory_counts",
    "get_inventory_summary",
]
