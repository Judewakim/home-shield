"""
Pricing repository for querying pricing rules.

Fetches current active pricing from the pricing_rules table based on
classification (Gold/Silver) and age bucket.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.client import supabase


def get_active_pricing(
    classification: LeadClassification,
    age_bucket: AgeBucket
) -> Optional[Decimal]:
    """
    Get the current active price for a classification + age bucket combination.

    Args:
        classification: Lead classification (Gold or Silver)
        age_bucket: Age bucket (MONTH_3_TO_5, etc.)

    Returns:
        Decimal price or None if no pricing rule found

    Example:
        price = get_active_pricing(LeadClassification.GOLD, AgeBucket.MONTH_6_TO_8)
        # Returns Decimal('8.00') based on seed_pricing.sql
    """
    response = (
        supabase.table("pricing_rules")
        .select("base_price")
        .eq("classification", classification.value)
        .eq("age_bucket", age_bucket.value)
        .is_("effective_to", "null")  # Only active pricing (not historical)
        .limit(1)
        .execute()
    )

    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to fetch pricing: {error}")

    rows = getattr(response, "data", None) or []

    if not rows:
        return None

    return Decimal(str(rows[0]["base_price"]))


def get_pricing_for_inventory_items(
    items: list
) -> dict[UUID, Decimal]:
    """
    Get pricing for multiple inventory items efficiently.

    Args:
        items: List of AvailableInventoryItem objects

    Returns:
        Dictionary mapping inventory_id to unit price

    Example:
        items = query_available_inventory(...)
        pricing = get_pricing_for_inventory_items(items)
        # Returns: {UUID('...'): Decimal('8.00'), UUID('...'): Decimal('7.50'), ...}
    """
    # Group items by (classification, age_bucket) to minimize queries
    unique_combinations = set(
        (item.classification, item.age_bucket) for item in items
    )

    # Fetch pricing for each unique combination
    pricing_cache: dict[tuple[LeadClassification, AgeBucket], Decimal] = {}

    for classification, age_bucket in unique_combinations:
        price = get_active_pricing(classification, age_bucket)
        if price is None:
            raise RuntimeError(
                f"No active pricing found for {classification.value} + {age_bucket.value}"
            )
        pricing_cache[(classification, age_bucket)] = price

    # Map inventory_id to price
    result: dict[UUID, Decimal] = {}
    for item in items:
        key = (item.classification, item.age_bucket)
        result[item.inventory_id] = pricing_cache[key]

    return result


def get_all_active_pricing() -> dict[tuple[str, str], Decimal]:
    """
    Get all currently active pricing rules.

    Returns:
        Dictionary mapping (classification, age_bucket) to price

    Example:
        pricing = get_all_active_pricing()
        # Returns: {
        #   ('Gold', 'MONTH_6_TO_8'): Decimal('8.00'),
        #   ('Silver', 'MONTH_6_TO_8'): Decimal('6.00'),
        #   ...
        # }
    """
    response = (
        supabase.table("pricing_rules")
        .select("classification, age_bucket, base_price")
        .is_("effective_to", "null")
        .execute()
    )

    error = getattr(response, "error", None)
    if error:
        raise RuntimeError(f"Failed to fetch pricing rules: {error}")

    rows = getattr(response, "data", None) or []

    result: dict[tuple[str, str], Decimal] = {}
    for row in rows:
        key = (row["classification"], row["age_bucket"])
        result[key] = Decimal(str(row["base_price"]))

    return result


__all__ = [
    "get_active_pricing",
    "get_pricing_for_inventory_items",
    "get_all_active_pricing",
]
