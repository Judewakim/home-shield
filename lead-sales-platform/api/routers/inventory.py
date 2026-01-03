"""
Inventory API Endpoints.

Endpoints for browsing and querying available lead inventory.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.models import InventoryItemResponse, InventoryListResponse
from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.inventory_query_repository import (
    InventoryQueryFilters,
    query_available_inventory,
)
from repositories.pricing_repository import get_pricing_for_inventory_items

router = APIRouter()


@router.get(
    "/inventory/locations",
    summary="Get Available Locations",
    description="Get list of available states and counties that have inventory."
)
def get_available_locations():
    """
    Get available states and counties from the database.

    Returns:
        Dictionary with states and counties_by_state
    """
    from repositories.client import supabase

    try:
        # Get unique states
        states_response = supabase.table('leads').select('state').execute()
        states = sorted(set(row['state'] for row in states_response.data if row.get('state')))

        # Get counties by state
        counties_by_state = {}
        for state in states:
            counties_response = supabase.table('leads').select('county').eq('state', state).execute()
            counties = sorted(set(row['county'] for row in counties_response.data if row.get('county')))
            counties_by_state[state] = counties

        return {
            "states": states,
            "counties_by_state": counties_by_state
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch locations: {str(e)}"
        )


@router.get(
    "/inventory",
    response_model=InventoryListResponse,
    summary="Query Available Inventory",
    description="Browse available leads with optional filters for state, classification, age bucket, and county."
)
def get_available_inventory(
    state: Optional[str] = Query(None, description="Filter by state (e.g., 'LA', 'TX')"),
    classification: Optional[str] = Query(None, description="Filter by classification ('Gold' or 'Silver')"),
    age_bucket: Optional[str] = Query(None, description="Filter by age bucket (e.g., 'MONTH_6_TO_8')"),
    county: Optional[str] = Query(None, description="Filter by county"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results to return"),
):
    """
    Query available inventory with optional filters.

    Returns a list of available leads that can be purchased, along with their
    pricing information.

    **Example usage:**
    - Get all available inventory: `GET /api/v1/inventory`
    - Filter by state: `GET /api/v1/inventory?state=LA`
    - Filter by classification: `GET /api/v1/inventory?classification=Gold`
    - Combine filters: `GET /api/v1/inventory?state=LA&classification=Gold&limit=50`
    """
    try:
        # Build filters
        classifications = None
        if classification:
            try:
                classifications = [LeadClassification(classification)]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid classification. Must be 'Gold' or 'Silver', got '{classification}'"
                )

        age_buckets = None
        if age_bucket:
            try:
                age_buckets = [AgeBucket(age_bucket)]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid age_bucket. Got '{age_bucket}'"
                )

        states = [state] if state else None
        counties = [county] if county else None

        filters = InventoryQueryFilters(
            classifications=classifications,
            age_buckets=age_buckets,
            states=states,
            counties=counties,
            available_only=True
        )

        # Query inventory
        items = query_available_inventory(filters, limit=limit)

        # Get pricing for all items
        pricing_map = get_pricing_for_inventory_items(items)

        # Convert to API response models
        response_items = [
            InventoryItemResponse(
                inventory_id=item.inventory_id,
                lead_id=item.lead_id,
                classification=item.classification.value,
                age_bucket=item.age_bucket.value,
                state=item.state,
                county=item.county,
                created_at=item.created_at_utc,
                unit_price=pricing_map[item.inventory_id]
            )
            for item in items
        ]

        # Build filters applied dict for response
        filters_applied = {}
        if state:
            filters_applied["state"] = state
        if classification:
            filters_applied["classification"] = classification
        if age_bucket:
            filters_applied["age_bucket"] = age_bucket
        if county:
            filters_applied["county"] = county

        return InventoryListResponse(
            items=response_items,
            total_count=len(response_items),
            filters_applied=filters_applied
        )

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"ERROR in get_available_inventory: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to query inventory: {str(e)}"
        )
