#!/usr/bin/env python3
"""
Test script for the complete purchase flow.

Demonstrates:
1. Client creation/validation
2. Inventory browsing
3. Quote calculation
4. Purchase execution
5. Automatic replacement (if needed)
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.client_repository import create_test_client, get_client_by_id
from repositories.inventory_query_repository import (
    InventoryQueryFilters,
    MixedInventoryRequest,
    query_available_inventory,
    query_mixed_inventory,
)
from repositories.sale_repository import list_sales_by_client
from services.pricing_service import calculate_purchase_quote
from services.purchase_service import PurchaseRequest, execute_purchase


def print_section(title: str) -> None:
    """Print a section header."""
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def test_scenario_1_simple_purchase():
    """
    Scenario 1: Simple purchase (10 leads, any classification/bucket).
    """
    print_section("SCENARIO 1: Simple Purchase (10 Leads)")

    # Step 1: Create or get test client
    print("\n1. Creating test client...")
    from repositories.client_repository import get_client_by_email

    client = get_client_by_email("test_buyer_1@example.com")
    if client is None:
        client = create_test_client(
            email="test_buyer_1@example.com",
            company_name="Test Corp"
        )
        print(f"   Created client: {client.email}")
    else:
        print(f"   Using existing client: {client.email}")
    print(f"   Client ID: {client.client_id}")
    print(f"   Status: {client.status}")
    print(f"   Can purchase: {client.can_purchase()}")

    # Step 2: Query inventory
    print("\n2. Querying available inventory...")
    filters = InventoryQueryFilters()
    available_leads = query_available_inventory(filters, limit=10)
    print(f"   Found {len(available_leads)} available leads")

    if not available_leads:
        print("   ERROR: No available leads in database!")
        return

    # Show sample
    sample = available_leads[0]
    print(f"\n   Sample lead:")
    print(f"     Classification: {sample.classification.value}")
    print(f"     Age Bucket: {sample.age_bucket.value}")
    print(f"     State: {sample.state}")
    print(f"     County: {sample.county}")

    # Step 3: Calculate quote
    print("\n3. Calculating purchase quote...")
    quote = calculate_purchase_quote(available_leads)
    print(f"   Total items: {quote.total_items}")
    print(f"   Subtotal: ${quote.subtotal}")
    print(f"   Currency: {quote.currency}")
    print(f"   Quote valid until: {quote.expires_at}")
    print(f"   Is expired: {quote.is_expired()}")

    # Step 4: Execute purchase
    print("\n4. Executing purchase...")
    inventory_ids = [item.inventory_id for item in available_leads]
    request = PurchaseRequest(
        client_id=client.client_id,
        inventory_item_ids=inventory_ids
    )

    result = execute_purchase(request)

    print(f"\n   Purchase Result:")
    print(f"     Success: {result.success}")
    print(f"     Items requested: {result.items_requested}")
    print(f"     Items purchased: {result.items_purchased}")
    print(f"     Items replaced: {result.items_replaced}")
    print(f"     Total paid: ${result.total_paid}")
    print(f"     Sale IDs: {len(result.sale_ids)}")

    if result.errors:
        print(f"     Errors: {result.errors}")

    # Step 5: Verify sales in database
    if result.success:
        print("\n5. Verifying sales in database...")
        sales = list_sales_by_client(client.client_id)
        print(f"   Found {len(sales)} sales for this client")

        if sales:
            sample_sale = sales[0]
            print(f"\n   Sample sale:")
            print(f"     Sale ID: {sample_sale.sale_id}")
            print(f"     Lead ID: {sample_sale.lead_id}")
            print(f"     Age Bucket: {sample_sale.age_bucket.value}")
            print(f"     Purchase Price: ${sample_sale.purchase_price}")
            print(f"     Currency: {sample_sale.currency}")
            print(f"     Sold At: {sample_sale.sold_at}")

    print("\n" + "=" * 80)
    print("SCENARIO 1 COMPLETE")
    print("=" * 80)


def test_scenario_2_mixed_inventory_purchase():
    """
    Scenario 2: Your demo scenario -
    "100 6-8 month old gold leads from Caddo county Louisiana +
     300 3-5 month old silver leads from anywhere in Louisiana"
    """
    print_section("SCENARIO 2: Mixed Inventory Purchase (Demo Scenario)")

    # Step 1: Create or get test client
    print("\n1. Creating test client...")
    from repositories.client_repository import get_client_by_email

    client = get_client_by_email("test_buyer_2@example.com")
    if client is None:
        client = create_test_client(
            email="test_buyer_2@example.com",
            company_name="Demo Corp"
        )
        print(f"   Created client: {client.email}")
    else:
        print(f"   Using existing client: {client.email}")

    # Step 2: Query mixed inventory
    print("\n2. Querying mixed inventory...")
    print("   Request:")
    print("     - 100 Gold leads, 6-8 months old, Caddo County, LA")
    print("     - 300 Silver leads, 3-5 months old, anywhere in LA")

    requests = [
        MixedInventoryRequest(
            classification=LeadClassification.GOLD,
            age_bucket=AgeBucket.MONTH_6_TO_8,
            quantity=100,
            states=["LA"],
            counties=["Caddo"]
        ),
        MixedInventoryRequest(
            classification=LeadClassification.SILVER,
            age_bucket=AgeBucket.MONTH_3_TO_5,
            quantity=300,
            states=["LA"]
        ),
    ]

    leads = query_mixed_inventory(requests)
    print(f"\n   Found {len(leads)} leads matching criteria")

    # Analyze what we got
    gold_count = sum(1 for l in leads if l.classification == LeadClassification.GOLD)
    silver_count = sum(1 for l in leads if l.classification == LeadClassification.SILVER)

    print(f"   Breakdown:")
    print(f"     Gold leads: {gold_count}")
    print(f"     Silver leads: {silver_count}")

    if len(leads) < 400:
        print(f"\n   WARNING: Only found {len(leads)} leads (need 400)")
        print(f"   Shortage: {400 - len(leads)} leads")
        print("\n   This demonstrates the all-or-nothing strategy:")
        print("   Purchase would be REJECTED due to insufficient inventory")
        print("   User would be told to try again with available quantity")
        return

    # Step 3: Calculate quote
    print("\n3. Calculating purchase quote...")
    quote = calculate_purchase_quote(leads)
    print(f"   Total items: {quote.total_items}")
    print(f"   Subtotal: ${quote.subtotal}")

    # Show price breakdown
    gold_subtotal = sum(
        item.unit_price for item in quote.items
        if item.classification == LeadClassification.GOLD
    )
    silver_subtotal = sum(
        item.unit_price for item in quote.items
        if item.classification == LeadClassification.SILVER
    )

    print(f"\n   Price breakdown:")
    print(f"     Gold leads: ${gold_subtotal} ({gold_count} leads)")
    print(f"     Silver leads: ${silver_subtotal} ({silver_count} leads)")

    # Step 4: Execute purchase
    print("\n4. Executing purchase...")
    inventory_ids = [item.inventory_id for item in leads]
    request = PurchaseRequest(
        client_id=client.client_id,
        inventory_item_ids=inventory_ids
    )

    result = execute_purchase(request)

    print(f"\n   Purchase Result:")
    print(f"     Success: {result.success}")
    print(f"     Items requested: {result.items_requested}")
    print(f"     Items purchased: {result.items_purchased}")
    print(f"     Items replaced: {result.items_replaced}")
    print(f"     Total paid: ${result.total_paid}")

    if result.errors:
        print(f"     Errors:")
        for error in result.errors:
            print(f"       - {error}")

    if result.success and result.items_replaced > 0:
        print(f"\n   AUTOMATIC REPLACEMENT IN ACTION!")
        print(f"   {result.items_replaced} leads were sold during checkout")
        print(f"   System automatically found replacements")
        print(f"   Customer still got all {result.items_requested} leads!")

    print("\n" + "=" * 80)
    print("SCENARIO 2 COMPLETE")
    print("=" * 80)


def main():
    """Run all test scenarios."""
    print("\n")
    print("*" * 80)
    print("PURCHASE FLOW TEST SUITE")
    print("*" * 80)

    try:
        test_scenario_1_simple_purchase()
        print("\n\n")
        test_scenario_2_mixed_inventory_purchase()

        print("\n\n")
        print("*" * 80)
        print("ALL SCENARIOS COMPLETE")
        print("*" * 80)
        print()

    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
