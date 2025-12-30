"""
Purchase service for executing lead purchases.

Handles:
- Automatic replacement of unavailable leads
- All-or-nothing transaction strategy
- Integration with execute_sale_atomic() PostgreSQL function
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.client import supabase
from repositories.client_repository import get_client_by_id
from repositories.inventory_query_repository import (
    AvailableInventoryItem,
    InventoryQueryFilters,
    query_available_inventory,
)
from repositories.sale_repository import record_sale
from services.pricing_service import PriceCalculation, calculate_purchase_quote


@dataclass(frozen=True, slots=True)
class PurchaseRequest:
    """
    Request to purchase specific inventory items.
    """
    client_id: UUID
    inventory_item_ids: List[UUID]  # Specific inventory IDs to purchase


@dataclass(frozen=True, slots=True)
class PurchaseResult:
    """
    Result of a purchase attempt.

    success: True if purchase completed successfully
    sale_ids: List of sale IDs created
    total_paid: Total amount charged
    items_requested: Number of items originally requested
    items_purchased: Number of items actually purchased
    items_replaced: Number of items that were automatically replaced
    errors: List of error messages (empty if success=True)
    """
    success: bool
    sale_ids: List[UUID]
    total_paid: Decimal
    items_requested: int
    items_purchased: int
    items_replaced: int
    errors: List[str]


@dataclass(frozen=True, slots=True)
class AtomicSaleResult:
    """Result from execute_sale_atomic PostgreSQL function."""
    success: bool
    sale_id: Optional[UUID]
    error_code: Optional[str]
    error_message: Optional[str]


def _execute_atomic_sale(
    lead_id: UUID,
    age_bucket: AgeBucket,
    client_id: UUID,
    purchase_price: Decimal
) -> AtomicSaleResult:
    """
    Execute atomic sale via PostgreSQL function.

    Calls execute_sale_atomic() which:
    - Locks inventory row (FOR UPDATE NOWAIT)
    - Checks if available (sold_at_utc IS NULL)
    - Marks as sold
    - Creates sale record
    All in a single atomic transaction.

    Args:
        lead_id: Lead to sell
        age_bucket: Age bucket being sold
        client_id: Buyer
        purchase_price: Price for this lead

    Returns:
        AtomicSaleResult with success status and sale_id or error
    """
    from postgrest.exceptions import APIError

    sold_at = datetime.now(timezone.utc)

    try:
        response = supabase.rpc(
            'execute_sale_atomic',
            {
                'p_lead_id': str(lead_id),
                'p_age_bucket': age_bucket.value,
                'p_client_id': str(client_id),
                'p_sold_at': sold_at.isoformat(),
                'p_purchase_price': float(purchase_price)
            }
        ).execute()

        error = getattr(response, "error", None)
        if error:
            return AtomicSaleResult(
                success=False,
                sale_id=None,
                error_code="RPC_ERROR",
                error_message=str(error)
            )

        result = response.data

        if result.get('success'):
            return AtomicSaleResult(
                success=True,
                sale_id=UUID(result['sale_id']),
                error_code=None,
                error_message=None
            )
        else:
            return AtomicSaleResult(
                success=False,
                sale_id=None,
                error_code=result.get('error'),
                error_message=result.get('message')
            )

    except APIError as e:
        # Supabase-py throws APIError when PostgreSQL function returns JSON
        # This happens for BOTH success and error responses from the RPC function
        try:
            error_data = e.json() if callable(getattr(e, 'json', None)) else {}
        except:
            error_data = {}

        # Check if it's actually a success response wrapped in an APIError
        if error_data.get('success') is True:
            return AtomicSaleResult(
                success=True,
                sale_id=UUID(error_data['sale_id']),
                error_code=None,
                error_message=None
            )

        # It's a real error
        return AtomicSaleResult(
            success=False,
            sale_id=None,
            error_code=error_data.get('error', 'API_ERROR'),
            error_message=error_data.get('message', str(e))
        )

    except Exception as e:
        return AtomicSaleResult(
            success=False,
            sale_id=None,
            error_code="EXCEPTION",
            error_message=str(e)
        )


def _find_replacement_leads(
    failed_items: List[AvailableInventoryItem],
    already_attempted: set[UUID]
) -> List[AvailableInventoryItem]:
    """
    Find replacement leads matching the criteria of failed items.

    For each failed item, query for leads with:
    - Same classification (Gold/Silver)
    - Same age bucket
    - Same state (if specified)
    - Same county (if specified)
    - Not already attempted

    Args:
        failed_items: Items that failed to purchase
        already_attempted: Set of inventory IDs already attempted (to avoid retrying same leads)

    Returns:
        List of replacement leads (may be fewer than requested)
    """
    replacements: List[AvailableInventoryItem] = []

    for failed_item in failed_items:
        # Query for similar leads
        filters = InventoryQueryFilters(
            classifications=[failed_item.classification],
            age_buckets=[failed_item.age_bucket],
            states=[failed_item.state] if failed_item.state else None,
            counties=[failed_item.county] if failed_item.county else None,
            available_only=True
        )

        # Fetch more than we need (in case some are also sold)
        candidates = query_available_inventory(filters, limit=10)

        # Filter out already attempted
        available_candidates = [
            c for c in candidates
            if c.inventory_id not in already_attempted
        ]

        if available_candidates:
            # Take first available candidate as replacement
            replacements.append(available_candidates[0])

    return replacements


def execute_purchase(request: PurchaseRequest) -> PurchaseResult:
    """
    Execute a purchase with automatic replacement.

    Process:
    1. Validate client exists and is active
    2. Fetch requested inventory items
    3. Calculate quote (pricing)
    4. Attempt to purchase each item via execute_sale_atomic()
    5. If any fail (already sold):
       - Find replacement leads matching same criteria
       - Attempt to purchase replacements
    6. If still can't get requested quantity:
       - REJECT entire purchase (all-or-nothing strategy)
       - Return error explaining shortage
    7. If successful:
       - Return sale IDs and total paid

    Args:
        request: PurchaseRequest with client_id and inventory_item_ids

    Returns:
        PurchaseResult with success status, sale_ids, and detailed metrics

    Example:
        request = PurchaseRequest(
            client_id=client.client_id,
            inventory_item_ids=[...]  # 100 inventory IDs
        )
        result = execute_purchase(request)

        if result.success:
            print(f"Purchased {result.items_purchased} leads for ${result.total_paid}")
            if result.items_replaced > 0:
                print(f"  ({result.items_replaced} leads were automatically replaced)")
        else:
            print(f"Purchase failed: {result.errors}")
    """
    items_requested = len(request.inventory_item_ids)

    # 1. Validate client
    client = get_client_by_id(request.client_id)

    if client is None:
        return PurchaseResult(
            success=False,
            sale_ids=[],
            total_paid=Decimal("0.00"),
            items_requested=items_requested,
            items_purchased=0,
            items_replaced=0,
            errors=["Client not found"]
        )

    if not client.can_purchase():
        return PurchaseResult(
            success=False,
            sale_ids=[],
            total_paid=Decimal("0.00"),
            items_requested=items_requested,
            items_purchased=0,
            items_replaced=0,
            errors=[f"Client account cannot purchase (status: {client.status}, email_verified: {client.email_verified})"]
        )

    # 2. Fetch inventory items
    # Need to implement get_inventory_items_by_ids in inventory_query_repository
    # For now, query all and filter (will optimize later)
    from repositories.inventory_query_repository import query_available_inventory

    all_available = query_available_inventory(
        InventoryQueryFilters(),
        limit=10000  # TODO: Optimize with direct ID query
    )

    requested_items = [
        item for item in all_available
        if item.inventory_id in request.inventory_item_ids
    ]

    if len(requested_items) != items_requested:
        missing_count = items_requested - len(requested_items)
        return PurchaseResult(
            success=False,
            sale_ids=[],
            total_paid=Decimal("0.00"),
            items_requested=items_requested,
            items_purchased=0,
            items_replaced=0,
            errors=[f"{missing_count} requested items are no longer available or don't exist"]
        )

    # 3. Calculate quote
    quote = calculate_purchase_quote(requested_items)

    if quote.is_expired():
        return PurchaseResult(
            success=False,
            sale_ids=[],
            total_paid=Decimal("0.00"),
            items_requested=items_requested,
            items_purchased=0,
            items_replaced=0,
            errors=["Quote has expired. Please request a new quote."]
        )

    # 4. Attempt to purchase each item
    successful_sales: List[UUID] = []
    failed_items: List[AvailableInventoryItem] = []
    attempted_inventory_ids: set[UUID] = set(request.inventory_item_ids)

    # Map inventory_id to price for lookup
    price_map = {item.inventory_id: item.unit_price for item in quote.items}

    for item in requested_items:
        unit_price = price_map[item.inventory_id]

        result = _execute_atomic_sale(
            lead_id=item.lead_id,
            age_bucket=item.age_bucket,
            client_id=request.client_id,
            purchase_price=unit_price
        )

        if result.success:
            successful_sales.append(result.sale_id)
        else:
            failed_items.append(item)

    # 5. Automatic replacement for failed items
    items_replaced = 0

    if failed_items:
        # Find replacements
        replacements = _find_replacement_leads(failed_items, attempted_inventory_ids)

        # Calculate pricing for replacements
        if replacements:
            replacement_quote = calculate_purchase_quote(replacements)
            replacement_price_map = {
                item.inventory_id: item.unit_price
                for item in replacement_quote.items
            }

            # Attempt to purchase replacements
            for replacement in replacements:
                attempted_inventory_ids.add(replacement.inventory_id)
                unit_price = replacement_price_map[replacement.inventory_id]

                result = _execute_atomic_sale(
                    lead_id=replacement.lead_id,
                    age_bucket=replacement.age_bucket,
                    client_id=request.client_id,
                    purchase_price=unit_price
                )

                if result.success:
                    successful_sales.append(result.sale_id)
                    items_replaced += 1

    # 6. Check if we got the requested quantity (ALL-OR-NOTHING)
    items_purchased = len(successful_sales)

    if items_purchased != items_requested:
        shortage = items_requested - items_purchased

        return PurchaseResult(
            success=False,
            sale_ids=[],  # Don't return sale IDs for failed purchase
            total_paid=Decimal("0.00"),
            items_requested=items_requested,
            items_purchased=0,  # All-or-nothing: report 0 purchased
            items_replaced=0,
            errors=[
                f"Unable to fulfill complete order. Requested {items_requested} leads, "
                f"but only {items_purchased} available (shortage of {shortage}).",
                f"Please try again with {items_purchased} leads or wait for more inventory."
            ]
        )

    # 7. Success! Calculate total paid
    # Note: In all-or-nothing, we either get all or none, so this is always the full quote amount
    total_paid = quote.subtotal

    return PurchaseResult(
        success=True,
        sale_ids=successful_sales,
        total_paid=total_paid,
        items_requested=items_requested,
        items_purchased=items_purchased,
        items_replaced=items_replaced,
        errors=[]
    )


__all__ = [
    "PurchaseRequest",
    "PurchaseResult",
    "execute_purchase",
]
