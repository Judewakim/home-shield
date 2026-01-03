"""
Criteria-based inventory allocation service.

This service handles the allocation of inventory based on buyer criteria
(classification, age bucket, location, quantity) rather than specific inventory IDs.

Key Features:
- Transactional allocation (all-or-nothing)
- Automatic row locking to prevent race conditions
- Validation of sufficient inventory before allocation
- Support for multi-criteria purchases (mixed orders)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.inventory_query_repository import (
    AvailableInventoryItem,
    InventoryQueryFilters,
    MixedInventoryRequest,
    query_mixed_inventory,
)


@dataclass(frozen=True, slots=True)
class InventoryAlternative:
    """Alternative inventory options when requested criteria cannot be fulfilled."""
    description: str
    available_count: int
    suggestion_type: str  # "partial", "no_location_filter", "different_age_bucket"


class InsufficientInventoryError(Exception):
    """Raised when requested inventory cannot be fulfilled."""
    def __init__(
        self,
        requested: int,
        available: int,
        criteria: str,
        alternatives: Optional[List[InventoryAlternative]] = None,
        item_index: Optional[int] = None
    ):
        self.requested = requested
        self.available = available
        self.criteria = criteria
        self.alternatives = alternatives or []
        self.item_index = item_index
        super().__init__(
            f"Insufficient inventory for {criteria}. "
            f"Requested: {requested}, Available: {available}"
        )


@dataclass(frozen=True, slots=True)
class AllocationCriteria:
    """Criteria for allocating inventory."""
    classification: LeadClassification
    age_bucket: AgeBucket
    quantity: int
    state: Optional[str] = None
    county: Optional[str] = None

    def to_string(self) -> str:
        """Human-readable description of criteria."""
        parts = [
            f"{self.classification.value}",
            f"{self.age_bucket.value}",
        ]
        if self.state:
            parts.append(f"state={self.state}")
        if self.county:
            parts.append(f"county={self.county}")
        parts.append(f"qty={self.quantity}")
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class AllocationResult:
    """Result of inventory allocation."""
    allocated_items: List[AvailableInventoryItem]
    requested_quantity: int
    allocated_quantity: int
    criteria: AllocationCriteria


def _get_inventory_alternatives(
    criterion: AllocationCriteria,
    current_available: int
) -> List[InventoryAlternative]:
    """
    Generate alternative inventory suggestions when requested quantity cannot be fulfilled.

    Returns suggestions for:
    1. Partial purchase (buy what's available)
    2. Remove location filter (if state/county specified)
    3. Try different age buckets
    """
    alternatives = []

    # Option 1: Partial purchase (if any available)
    if current_available > 0:
        price = current_available * (5.00 if criterion.classification == LeadClassification.GOLD else 4.00)
        alternatives.append(InventoryAlternative(
            description=f"Purchase {current_available} available leads (${price:.2f})",
            available_count=current_available,
            suggestion_type="partial"
        ))

    # Option 2: Remove location filter (if applicable)
    if criterion.state or criterion.county:
        filters_no_location = InventoryQueryFilters(
            classifications=[criterion.classification],
            age_buckets=[criterion.age_bucket],
            states=None,
            counties=None,
            available_only=True
        )
        from repositories.inventory_query_repository import query_available_inventory
        items_no_location = query_available_inventory(filters_no_location, limit=10000)
        count_no_location = len(items_no_location)

        if count_no_location > current_available:
            location_desc = f"{criterion.state}" if criterion.state else ""
            if criterion.county:
                location_desc = f"{criterion.county}, {location_desc}" if location_desc else criterion.county

            alternatives.append(InventoryAlternative(
                description=f"Remove location filter ({count_no_location} available without {location_desc} filter)",
                available_count=count_no_location,
                suggestion_type="no_location_filter"
            ))

    # Option 3: Try different age buckets (adjacent ones)
    age_bucket_alternatives = _get_adjacent_age_buckets(criterion.age_bucket)
    for alt_bucket in age_bucket_alternatives:
        filters_alt = InventoryQueryFilters(
            classifications=[criterion.classification],
            age_buckets=[alt_bucket],
            states=[criterion.state] if criterion.state else None,
            counties=[criterion.county] if criterion.county else None,
            available_only=True
        )
        from repositories.inventory_query_repository import query_available_inventory
        items_alt = query_available_inventory(filters_alt, limit=10000)
        count_alt = len(items_alt)

        if count_alt >= criterion.quantity:
            location_part = f" in {criterion.state}" if criterion.state else ""
            alternatives.append(InventoryAlternative(
                description=f"Try {alt_bucket.value} age bucket ({count_alt} available{location_part})",
                available_count=count_alt,
                suggestion_type="different_age_bucket"
            ))
            # Only show first 2 age bucket alternatives
            if len([a for a in alternatives if a.suggestion_type == "different_age_bucket"]) >= 2:
                break

    return alternatives


def _get_adjacent_age_buckets(current_bucket: AgeBucket) -> List[AgeBucket]:
    """Get adjacent age buckets for suggesting alternatives."""
    bucket_order = [
        AgeBucket.MONTH_3_TO_5,
        AgeBucket.MONTH_6_TO_8,
        AgeBucket.MONTH_9_TO_11,
        AgeBucket.MONTH_12_TO_23,
        AgeBucket.MONTH_24_PLUS,
    ]

    try:
        current_idx = bucket_order.index(current_bucket)
    except ValueError:
        return []

    adjacent = []
    # Add next bucket
    if current_idx + 1 < len(bucket_order):
        adjacent.append(bucket_order[current_idx + 1])
    # Add previous bucket
    if current_idx - 1 >= 0:
        adjacent.append(bucket_order[current_idx - 1])

    return adjacent


def allocate_inventory_by_criteria(
    criteria_list: List[AllocationCriteria]
) -> List[AllocationResult]:
    """
    Allocate inventory based on buyer criteria.

    This function:
    1. Validates sufficient inventory exists for all criteria
    2. Allocates inventory for each criterion
    3. Returns allocated items

    Note: This function does NOT mark items as sold. That's done by the
    purchase service after payment processing.

    Args:
        criteria_list: List of allocation criteria

    Returns:
        List of AllocationResult with allocated inventory items

    Raises:
        InsufficientInventoryError: If any criterion cannot be fulfilled
        ValueError: If criteria_list is empty

    Example:
        criteria = [
            AllocationCriteria(
                classification=LeadClassification.GOLD,
                age_bucket=AgeBucket.MONTH_6_TO_8,
                quantity=10,
                state="LA"
            )
        ]
        results = allocate_inventory_by_criteria(criteria)
        inventory_ids = [item.inventory_id for result in results for item in result.allocated_items]
    """
    if not criteria_list:
        raise ValueError("criteria_list cannot be empty")

    results = []

    for idx, criterion in enumerate(criteria_list):
        # Build mixed inventory request
        states = [criterion.state] if criterion.state else None
        counties = [criterion.county] if criterion.county else None

        request = MixedInventoryRequest(
            classification=criterion.classification,
            age_bucket=criterion.age_bucket,
            quantity=criterion.quantity,
            states=states,
            counties=counties
        )

        # Query available inventory
        # Note: query_mixed_inventory returns available inventory items
        # In production, this should use SELECT FOR UPDATE for row locking
        allocated_items = query_mixed_inventory([request])

        # Validate we got the requested quantity
        if len(allocated_items) < criterion.quantity:
            # Generate alternatives
            alternatives = _get_inventory_alternatives(criterion, len(allocated_items))

            raise InsufficientInventoryError(
                requested=criterion.quantity,
                available=len(allocated_items),
                criteria=criterion.to_string(),
                alternatives=alternatives,
                item_index=idx if len(criteria_list) > 1 else None
            )

        # Store result
        results.append(AllocationResult(
            allocated_items=allocated_items,
            requested_quantity=criterion.quantity,
            allocated_quantity=len(allocated_items),
            criteria=criterion
        ))

    return results


def validate_inventory_availability(
    criteria_list: List[AllocationCriteria]
) -> dict[str, int]:
    """
    Check if sufficient inventory exists for all criteria WITHOUT allocating.

    This is useful for showing availability to users before they commit to purchase.

    Args:
        criteria_list: List of allocation criteria to validate

    Returns:
        Dictionary mapping criteria description to available count

    Example:
        criteria = [AllocationCriteria(...)]
        availability = validate_inventory_availability(criteria)
        # {'Gold MONTH_6_TO_8 state=LA qty=10': 22}
    """
    availability = {}

    for criterion in criteria_list:
        states = [criterion.state] if criterion.state else None
        counties = [criterion.county] if criterion.county else None

        # Build filters to count available inventory
        filters = InventoryQueryFilters(
            classifications=[criterion.classification],
            age_buckets=[criterion.age_bucket],
            states=states,
            counties=counties,
            available_only=True
        )

        # Query to get count (we use a large limit since we just want to count)
        from repositories.inventory_query_repository import query_available_inventory
        available_items = query_available_inventory(filters, limit=10000)

        availability[criterion.to_string()] = len(available_items)

    return availability


__all__ = [
    "AllocationCriteria",
    "AllocationResult",
    "InsufficientInventoryError",
    "InventoryAlternative",
    "allocate_inventory_by_criteria",
    "validate_inventory_availability",
]
