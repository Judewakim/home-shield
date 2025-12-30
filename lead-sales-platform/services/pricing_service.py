"""
Pricing service for calculating purchase quotes.

Calculates the total cost for purchasing inventory items based on
current active pricing rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List
from uuid import UUID

from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.inventory_query_repository import AvailableInventoryItem
from repositories.pricing_repository import get_pricing_for_inventory_items


@dataclass(frozen=True, slots=True)
class PriceCalculation:
    """
    Individual line item price calculation for a single inventory item.
    """
    inventory_id: UUID
    lead_id: UUID
    classification: LeadClassification
    age_bucket: AgeBucket
    unit_price: Decimal


@dataclass(frozen=True, slots=True)
class PurchaseQuote:
    """
    Complete purchase quote with itemized breakdown.

    Includes:
    - Individual item prices
    - Subtotal (sum of all items)
    - Quote expiration (prevents stale price abuse)
    """
    items: List[PriceCalculation]
    subtotal: Decimal
    currency: str
    created_at: datetime
    expires_at: datetime  # Quote valid for limited time (e.g., 15 minutes)

    @property
    def total_items(self) -> int:
        """Total number of items in this quote."""
        return len(self.items)

    def is_expired(self) -> bool:
        """Check if this quote has expired."""
        return datetime.now(timezone.utc) > self.expires_at


def calculate_purchase_quote(
    inventory_items: List[AvailableInventoryItem],
    quote_validity_minutes: int = 15
) -> PurchaseQuote:
    """
    Calculate a purchase quote for the given inventory items.

    Args:
        inventory_items: List of inventory items to purchase
        quote_validity_minutes: How long the quote is valid (default: 15 minutes)

    Returns:
        PurchaseQuote with itemized pricing

    Raises:
        RuntimeError: If pricing not found for any item

    Example:
        items = query_available_inventory(...)
        quote = calculate_purchase_quote(items)
        print(f"Total: ${quote.subtotal} for {quote.total_items} leads")
        print(f"Quote expires at: {quote.expires_at}")
    """
    # Fetch pricing for all items efficiently
    pricing_map = get_pricing_for_inventory_items(inventory_items)

    # Build line items
    line_items: List[PriceCalculation] = []
    subtotal = Decimal("0.00")

    for item in inventory_items:
        unit_price = pricing_map[item.inventory_id]

        line_items.append(PriceCalculation(
            inventory_id=item.inventory_id,
            lead_id=item.lead_id,
            classification=item.classification,
            age_bucket=item.age_bucket,
            unit_price=unit_price
        ))

        subtotal += unit_price

    # Calculate expiration
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=quote_validity_minutes)

    return PurchaseQuote(
        items=line_items,
        subtotal=subtotal,
        currency="USD",
        created_at=now,
        expires_at=expires_at
    )


def get_price_for_single_item(
    classification: LeadClassification,
    age_bucket: AgeBucket
) -> Decimal:
    """
    Get the price for a single lead with given classification and age bucket.

    Args:
        classification: Lead classification (Gold or Silver)
        age_bucket: Age bucket (MONTH_3_TO_5, etc.)

    Returns:
        Price as Decimal

    Example:
        price = get_price_for_single_item(LeadClassification.GOLD, AgeBucket.MONTH_6_TO_8)
        # Returns Decimal('8.00')
    """
    from repositories.pricing_repository import get_active_pricing

    price = get_active_pricing(classification, age_bucket)

    if price is None:
        raise RuntimeError(
            f"No active pricing found for {classification.value} + {age_bucket.value}"
        )

    return price


__all__ = [
    "PriceCalculation",
    "PurchaseQuote",
    "calculate_purchase_quote",
    "get_price_for_single_item",
]
