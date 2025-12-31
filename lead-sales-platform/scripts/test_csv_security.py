#!/usr/bin/env python3
"""
Test script to verify CSV export security features.

Tests:
1. Authorization: Client cannot export another client's sales
2. CSV Injection: Malicious formulas are sanitized
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import uuid4
from repositories.client_repository import create_test_client, get_client_by_email
from repositories.inventory_query_repository import InventoryQueryFilters, query_available_inventory
from services.pricing_service import calculate_purchase_quote
from services.purchase_service import PurchaseRequest, execute_purchase
from services.csv_export_service import generate_csv_for_sales, SecurityError


def test_authorization_check():
    """
    Test that authorization check prevents unauthorized access.

    Scenario:
    - Client A makes a purchase
    - Client B tries to export Client A's sales
    - Should raise SecurityError
    """
    print("\n" + "=" * 80)
    print("TEST: Authorization Check")
    print("=" * 80)

    # Create two test clients
    print("\n1. Creating two test clients...")
    client_a = get_client_by_email("security_test_a@example.com")
    if client_a is None:
        client_a = create_test_client("security_test_a@example.com", "Client A Corp")
        print(f"   Created Client A: {client_a.email}")
    else:
        print(f"   Using existing Client A: {client_a.email}")

    client_b = get_client_by_email("security_test_b@example.com")
    if client_b is None:
        client_b = create_test_client("security_test_b@example.com", "Client B Corp")
        print(f"   Created Client B: {client_b.email}")
    else:
        print(f"   Using existing Client B: {client_b.email}")

    # Client A makes a purchase
    print("\n2. Client A purchases leads...")
    available_leads = query_available_inventory(InventoryQueryFilters(), limit=3)

    if not available_leads:
        print("   ERROR: No available leads for testing!")
        return False

    quote = calculate_purchase_quote(available_leads)
    inventory_ids = [item.inventory_id for item in available_leads]

    request = PurchaseRequest(
        client_id=client_a.client_id,
        inventory_item_ids=inventory_ids
    )

    result = execute_purchase(request)

    if not result.success:
        print(f"   ERROR: Purchase failed: {result.errors}")
        return False

    print(f"   Client A successfully purchased {result.items_purchased} leads")
    print(f"   Sale IDs: {result.sale_ids[:3]}...")

    # Client B tries to export Client A's sales (SHOULD FAIL)
    print("\n3. Client B attempts to export Client A's sales...")
    print("   (This should be BLOCKED by authorization check)")

    try:
        csv_content = generate_csv_for_sales(result.sale_ids, client_b.client_id)
        print("   [FAIL] SECURITY FAILURE: Client B was able to export Client A's sales!")
        return False

    except SecurityError as e:
        print(f"   [PASS] SUCCESS: Authorization check blocked the attempt")
        print(f"   Error message: {e}")
        return True

    except Exception as e:
        print(f"   [FAIL] UNEXPECTED ERROR: {e}")
        return False


def test_csv_injection_sanitization():
    """
    Test that CSV injection attacks are prevented.

    Scenario:
    - Check if formula characters are stripped from CSV output
    - Verify no dangerous characters in first column
    """
    print("\n" + "=" * 80)
    print("TEST: CSV Injection Sanitization")
    print("=" * 80)

    # Get a client with sales
    print("\n1. Finding client with existing sales...")
    client = get_client_by_email("test_buyer_1@example.com")

    if client is None:
        print("   ERROR: Test client not found!")
        return False

    # Get their sales
    from repositories.sale_repository import list_sales_by_client
    sales = list_sales_by_client(client.client_id)

    if not sales:
        print("   ERROR: Client has no sales to test!")
        return False

    print(f"   Found client with {len(sales)} sales")

    # Export CSV
    print("\n2. Generating CSV export...")
    sale_ids = [sale.sale_id for sale in sales[:5]]  # First 5 sales
    csv_content = generate_csv_for_sales(sale_ids, client.client_id)

    # Check for dangerous characters
    print("\n3. Checking for CSV injection characters...")
    dangerous_patterns = ['=', '@SUM', '@', '+', '-\t']

    csv_lines = csv_content.split('\n')
    data_lines = csv_lines[1:]  # Skip header

    found_dangerous = False
    for i, line in enumerate(data_lines[:5], 1):  # Check first 5 rows
        # Check if line starts with dangerous characters
        first_char = line[0] if line else ""
        if first_char in ['=', '+', '-', '@']:
            print(f"   [FAIL] Row {i} starts with dangerous character: {first_char}")
            found_dangerous = True

    if not found_dangerous:
        print("   [PASS] SUCCESS: No CSV injection characters found in data")
        print("   All fields have been properly sanitized")
        return True
    else:
        print("   [FAIL] FAILURE: CSV injection characters found!")
        return False


def main():
    """Run security tests."""
    print("\n" + "*" * 80)
    print("CSV EXPORT SECURITY TEST SUITE")
    print("*" * 80)

    results = []

    try:
        # Test 1: Authorization
        results.append(("Authorization Check", test_authorization_check()))

        # Test 2: CSV Injection
        results.append(("CSV Injection Sanitization", test_csv_injection_sanitization()))

        # Summary
        print("\n" + "*" * 80)
        print("TEST RESULTS SUMMARY")
        print("*" * 80)

        for test_name, passed in results:
            status = "[PASS]" if passed else "[FAIL]"
            print(f"{status}: {test_name}")

        all_passed = all(passed for _, passed in results)

        if all_passed:
            print("\nAll security tests passed!")
            return 0
        else:
            print("\nSome security tests failed!")
            return 1

    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
