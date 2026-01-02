"""
Purchases API Endpoints.

Endpoints for executing purchases and downloading purchased lead data.
"""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from api.models import (
    PurchaseRequest as APIPurchaseRequest,
    CriteriaBasedPurchaseRequest,
    PurchaseResponse
)
from services.purchase_service import PurchaseRequest, execute_purchase
from services.csv_export_service import generate_csv_for_sales, SecurityError
from services.inventory_allocation_service import (
    AllocationCriteria,
    allocate_inventory_by_criteria,
    InsufficientInventoryError,
)
from domain.lead import LeadClassification
from domain.age_bucket import AgeBucket
from repositories.sale_repository import get_sale_by_id

router = APIRouter()


@router.post(
    "/purchases",
    response_model=PurchaseResponse,
    summary="Execute Purchase",
    description="Execute a lead purchase with automatic replacement and all-or-nothing strategy."
)
def execute_lead_purchase(request: APIPurchaseRequest):
    """
    Execute a purchase of lead inventory.

    **Process:**
    1. Validates client exists and can purchase
    2. Fetches requested inventory items
    3. Calculates quote pricing
    4. Attempts to purchase each item atomically
    5. If any items are already sold, automatically finds replacements
    6. If complete order cannot be fulfilled, rejects entire purchase (all-or-nothing)

    **Automatic Replacement:**
    If requested leads are sold during checkout, the system automatically
    finds similar leads (same classification, age bucket, location) as replacements.

    **All-or-Nothing Strategy:**
    If the complete order cannot be fulfilled (even with replacements),
    the entire purchase is rejected to prevent partial fulfillment.

    **Example request:**
    ```json
    {
      "client_id": "123e4567-e89b-12d3-a456-426614174002",
      "inventory_item_ids": [
        "123e4567-e89b-12d3-a456-426614174000",
        "123e4567-e89b-12d3-a456-426614174001"
      ]
    }
    ```

    **Success response:**
    ```json
    {
      "success": true,
      "sale_ids": ["uuid1", "uuid2"],
      "total_paid": "80.00",
      "items_requested": 10,
      "items_purchased": 10,
      "items_replaced": 2,
      "errors": [],
      "message": "Purchase completed successfully. 2 leads were automatically replaced."
    }
    ```

    **Failure response (insufficient inventory):**
    ```json
    {
      "success": false,
      "sale_ids": [],
      "total_paid": "0.00",
      "items_requested": 100,
      "items_purchased": 0,
      "items_replaced": 0,
      "errors": ["Unable to fulfill complete order. Requested 100 leads, but only 85 available."],
      "message": "Purchase failed due to insufficient inventory."
    }
    ```
    """
    try:
        # Convert API request to service request
        service_request = PurchaseRequest(
            client_id=request.client_id,
            inventory_item_ids=request.inventory_item_ids
        )

        # Execute purchase
        result = execute_purchase(service_request)

        # Build response message
        message = None
        if result.success:
            if result.items_replaced > 0:
                message = f"Purchase completed successfully. {result.items_replaced} leads were automatically replaced."
            else:
                message = "Purchase completed successfully."
        else:
            message = "Purchase failed. " + " ".join(result.errors)

        return PurchaseResponse(
            success=result.success,
            sale_ids=result.sale_ids,
            total_paid=result.total_paid,
            items_requested=result.items_requested,
            items_purchased=result.items_purchased,
            items_replaced=result.items_replaced,
            errors=result.errors,
            message=message
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute purchase: {str(e)}"
        )


@router.post(
    "/purchases/by-criteria",
    response_model=PurchaseResponse,
    summary="Execute Purchase by Criteria",
    description="Purchase leads by specifying criteria (classification, age, location) instead of specific IDs."
)
def execute_purchase_by_criteria(request: CriteriaBasedPurchaseRequest):
    """
    Execute a purchase by specifying criteria instead of specific inventory IDs.

    This is the recommended approach for lead purchasing as it:
    - Eliminates race conditions (no stale inventory references)
    - Automatically selects best available inventory
    - Supports mixed orders (multiple criteria in one purchase)
    - Transactionally allocates inventory at purchase time

    **Example request:**
    ```json
    {
      "client_id": "123e4567-e89b-12d3-a456-426614174002",
      "criteria": [
        {
          "classification": "Gold",
          "age_bucket": "MONTH_6_TO_8",
          "quantity": 10,
          "state": "LA"
        },
        {
          "classification": "Silver",
          "age_bucket": "MONTH_9_TO_11",
          "quantity": 5,
          "state": "TX"
        }
      ]
    }
    ```

    **Success response:**
    ```json
    {
      "success": true,
      "sale_ids": ["uuid1", "uuid2", ...],
      "total_paid": "120.00",
      "items_requested": 15,
      "items_purchased": 15,
      "items_replaced": 0,
      "errors": [],
      "message": "Purchase completed successfully."
    }
    ```
    """
    try:
        # Convert API criteria to service criteria
        allocation_criteria = []
        for api_criterion in request.criteria:
            try:
                classification = LeadClassification(api_criterion.classification)
                age_bucket = AgeBucket(api_criterion.age_bucket)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid classification or age_bucket: {str(e)}"
                )

            allocation_criteria.append(AllocationCriteria(
                classification=classification,
                age_bucket=age_bucket,
                quantity=api_criterion.quantity,
                state=api_criterion.state,
                county=api_criterion.county
            ))

        # Allocate inventory based on criteria
        try:
            allocation_results = allocate_inventory_by_criteria(allocation_criteria)
        except InsufficientInventoryError as e:
            raise HTTPException(
                status_code=409,  # Conflict
                detail=f"Insufficient inventory: {str(e)}"
            )

        # Extract allocated inventory IDs
        inventory_ids = [
            item.inventory_id
            for result in allocation_results
            for item in result.allocated_items
        ]

        # Execute purchase with allocated inventory
        service_request = PurchaseRequest(
            client_id=request.client_id,
            inventory_item_ids=inventory_ids
        )

        result = execute_purchase(service_request)

        # Build response message
        message = None
        if result.success:
            if result.items_replaced > 0:
                message = f"Purchase completed successfully. {result.items_replaced} leads were automatically replaced."
            else:
                message = "Purchase completed successfully."
        else:
            message = "Purchase failed. " + " ".join(result.errors)

        return PurchaseResponse(
            success=result.success,
            sale_ids=result.sale_ids,
            total_paid=result.total_paid,
            items_requested=result.items_requested,
            items_purchased=result.items_purchased,
            items_replaced=result.items_replaced,
            errors=result.errors,
            message=message
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute purchase: {str(e)}"
        )


@router.get(
    "/purchases/download",
    summary="Download Purchased Leads CSV",
    description="Download CSV file containing full lead details for multiple sales.",
    response_class=Response
)
def download_purchase_csv(sale_ids: str, client_id: str):
    """
    Download CSV export of purchased leads for multiple sales.

    **Authorization:**
    Only the client who made the purchase can download the CSV.
    Requires `client_id` query parameter for authorization.

    **CSV Contents:**
    - Sale information (purchase price, date, age bucket)
    - Full lead details (name, phone, address, etc.)
    - All 33 fields with complete contact information

    **Security:**
    - Authorization check ensures clients can only access their own purchases
    - CSV injection prevention (dangerous characters stripped)
    - All data modifications are logged for audit trail

    **Example usage:**
    ```
    GET /api/v1/purchases/download?sale_ids=uuid1,uuid2,uuid3&client_id=123e4567-e89b-12d3-a456-426614174002
    ```

    **Response:**
    CSV file download with filename: `purchased_leads.csv`
    """
    try:
        from uuid import UUID

        # Parse sale_ids (comma-separated)
        sale_id_list = [s.strip() for s in sale_ids.split(',') if s.strip()]

        if not sale_id_list:
            raise HTTPException(
                status_code=400,
                detail="At least one sale_id is required"
            )

        # Parse UUIDs
        try:
            sale_uuids = [UUID(sid) for sid in sale_id_list]
            client_uuid = UUID(client_id)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid UUID format: {str(e)}"
            )

        # Verify all sales exist
        for sale_uuid in sale_uuids:
            sale = get_sale_by_id(sale_uuid)
            if sale is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Sale not found: {sale_uuid}"
                )

        # Generate CSV with authorization check (will verify all sales belong to client)
        try:
            csv_content = generate_csv_for_sales(sale_uuids, client_uuid)
        except SecurityError as e:
            raise HTTPException(
                status_code=403,
                detail=f"Not authorized to download these sales: {str(e)}"
            )

        # Return CSV as downloadable file
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=purchased_leads.csv"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate CSV: {str(e)}"
        )
