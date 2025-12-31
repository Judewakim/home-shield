"""
API Request and Response Models.

Pydantic models for validating API requests and serializing responses.
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ============================================================================
# Inventory Models
# ============================================================================

class InventoryItemResponse(BaseModel):
    """Single inventory item in API response."""
    inventory_id: UUID
    lead_id: UUID
    classification: str  # "Gold" or "Silver"
    age_bucket: str  # "MONTH_3_TO_5", etc.
    state: str
    county: Optional[str] = None
    created_at: datetime
    unit_price: Decimal

    class Config:
        json_schema_extra = {
            "example": {
                "inventory_id": "123e4567-e89b-12d3-a456-426614174000",
                "lead_id": "123e4567-e89b-12d3-a456-426614174001",
                "classification": "Gold",
                "age_bucket": "MONTH_6_TO_8",
                "state": "LA",
                "county": "Caddo",
                "created_at": "2025-01-01T12:00:00Z",
                "unit_price": "8.00"
            }
        }


class InventoryListResponse(BaseModel):
    """Response for inventory listing."""
    items: List[InventoryItemResponse]
    total_count: int
    filters_applied: dict

    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "total_count": 150,
                "filters_applied": {
                    "state": "LA",
                    "classification": "Gold"
                }
            }
        }


# ============================================================================
# Quote Models
# ============================================================================

class QuoteRequest(BaseModel):
    """Request to calculate a purchase quote."""
    inventory_item_ids: List[UUID] = Field(
        ...,
        min_length=1,
        description="List of inventory item IDs to quote"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "inventory_item_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "123e4567-e89b-12d3-a456-426614174001"
                ]
            }
        }


class QuoteLineItem(BaseModel):
    """Single line item in a quote."""
    inventory_id: UUID
    lead_id: UUID
    classification: str
    age_bucket: str
    state: str
    county: Optional[str]
    unit_price: Decimal


class QuoteResponse(BaseModel):
    """Response with purchase quote details."""
    items: List[QuoteLineItem]
    subtotal: Decimal
    currency: str
    total_items: int
    created_at: datetime
    expires_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "items": [],
                "subtotal": "80.00",
                "currency": "USD",
                "total_items": 10,
                "created_at": "2025-01-01T12:00:00Z",
                "expires_at": "2025-01-01T12:15:00Z"
            }
        }


# ============================================================================
# Purchase Models
# ============================================================================

class PurchaseRequest(BaseModel):
    """Request to execute a purchase."""
    client_id: UUID = Field(
        ...,
        description="Client ID making the purchase"
    )
    inventory_item_ids: List[UUID] = Field(
        ...,
        min_length=1,
        description="List of inventory item IDs to purchase"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "client_id": "123e4567-e89b-12d3-a456-426614174002",
                "inventory_item_ids": [
                    "123e4567-e89b-12d3-a456-426614174000",
                    "123e4567-e89b-12d3-a456-426614174001"
                ]
            }
        }


class PurchaseResponse(BaseModel):
    """Response after purchase execution."""
    success: bool
    sale_ids: List[UUID]
    total_paid: Decimal
    items_requested: int
    items_purchased: int
    items_replaced: int
    errors: List[str]
    message: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "sale_ids": [
                    "123e4567-e89b-12d3-a456-426614174003",
                    "123e4567-e89b-12d3-a456-426614174004"
                ],
                "total_paid": "80.00",
                "items_requested": 10,
                "items_purchased": 10,
                "items_replaced": 2,
                "errors": [],
                "message": "Purchase completed successfully"
            }
        }


# ============================================================================
# Error Models
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    status_code: int

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Invalid request",
                "detail": "Inventory items not found",
                "status_code": 400
            }
        }
