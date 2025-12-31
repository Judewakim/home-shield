"""
Quotes API Endpoints.

Endpoints for calculating purchase quotes.
"""

from fastapi import APIRouter, HTTPException

from api.models import QuoteRequest, QuoteResponse, QuoteLineItem
from repositories.inventory_query_repository import (
    InventoryQueryFilters,
    query_available_inventory,
)
from services.pricing_service import calculate_purchase_quote

router = APIRouter()


@router.post(
    "/quotes",
    response_model=QuoteResponse,
    summary="Calculate Purchase Quote",
    description="Calculate pricing quote for selected inventory items. Quote is valid for 15 minutes."
)
def calculate_quote(request: QuoteRequest):
    """
    Calculate a purchase quote for the specified inventory items.

    Returns itemized pricing breakdown, subtotal, and quote expiration time.

    **How it works:**
    1. Validates that all requested inventory items exist and are available
    2. Calculates pricing based on classification and age bucket
    3. Returns quote valid for 15 minutes

    **Example request:**
    ```json
    {
      "inventory_item_ids": [
        "123e4567-e89b-12d3-a456-426614174000",
        "123e4567-e89b-12d3-a456-426614174001"
      ]
    }
    ```
    """
    try:
        # Fetch all available inventory (we'll filter to requested IDs)
        # TODO: Optimize with direct ID query in future
        all_available = query_available_inventory(
            InventoryQueryFilters(),
            limit=10000
        )

        # Filter to requested items
        requested_items = [
            item for item in all_available
            if item.inventory_id in request.inventory_item_ids
        ]

        # Validate all items were found
        if len(requested_items) != len(request.inventory_item_ids):
            found_ids = {item.inventory_id for item in requested_items}
            missing_ids = [
                str(id) for id in request.inventory_item_ids
                if id not in found_ids
            ]
            raise HTTPException(
                status_code=404,
                detail=f"Some inventory items not found or unavailable: {missing_ids}"
            )

        # Calculate quote
        quote = calculate_purchase_quote(requested_items)

        # Check if quote is expired (shouldn't be, but safety check)
        if quote.is_expired():
            raise HTTPException(
                status_code=500,
                detail="Quote generation failed - timestamp error"
            )

        # Convert to API response model (need to get state/county from original items)
        item_map = {item.inventory_id: item for item in requested_items}

        line_items = [
            QuoteLineItem(
                inventory_id=item.inventory_id,
                lead_id=item.lead_id,
                classification=item.classification.value,
                age_bucket=item.age_bucket.value,
                state=item_map[item.inventory_id].state,
                county=item_map[item.inventory_id].county,
                unit_price=item.unit_price
            )
            for item in quote.items
        ]

        return QuoteResponse(
            items=line_items,
            subtotal=quote.subtotal,
            currency=quote.currency,
            total_items=quote.total_items,
            created_at=quote.created_at,
            expires_at=quote.expires_at
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate quote: {str(e)}"
        )
