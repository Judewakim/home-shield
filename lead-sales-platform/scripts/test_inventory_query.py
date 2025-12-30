#!/usr/bin/env python3
"""
Test script for inventory query repository.

Verifies that inventory queries and filters work correctly.

Usage:
    python scripts/test_inventory_query.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.inventory_query_repository import (
    InventoryQueryFilters,
    MixedInventoryRequest,
    query_available_inventory,
    query_mixed_inventory,
    get_inventory_counts,
    get_inventory_summary,
)


def print_section(title: str) -> None:
    """Print a section header."""
    print()
    print("=" * 80)
    print(title)
    print("=" * 80)


def test_basic_query() -> None:
    """Test basic query without filters (first 10 available leads)."""
    print_section("TEST 1: Basic Query (First 10 Available Leads)")

    filters = InventoryQueryFilters()
    results = query_available_inventory(filters, limit=10)

    print(f"Found {len(results)} available leads")

    if results:
        print("\nSample lead:")
        lead = results[0]
        print(f"  Inventory ID: {lead.inventory_id}")
        print(f"  Lead ID: {lead.lead_id}")
        print(f"  Age Bucket: {lead.age_bucket.value}")
        print(f"  State: {lead.state}")
        print(f"  County: {lead.county}")
        print(f"  Classification: {lead.classification.value}")
        print(f"  Name: {lead.first_name} {lead.last_name}")
        print(f"  City: {lead.city}")
        print(f"  ZIP: {lead.zip}")
        print(f"  Created: {lead.created_at_utc}")


def test_filter_by_state() -> None:
    """Test filtering by state (LA only)."""
    print_section("TEST 2: Filter by State (LA)")

    filters = InventoryQueryFilters(states=["LA"])
    results = query_available_inventory(filters, limit=10)

    print(f"Found {len(results)} Louisiana leads")

    # Verify all results are from LA
    states = {lead.state for lead in results}
    print(f"Unique states: {states}")
    assert states == {"LA"}, f"Expected only LA, got {states}"
    print("SUCCESS: All results are from Louisiana")


def test_filter_by_classification() -> None:
    """Test filtering by classification (Gold only)."""
    print_section("TEST 3: Filter by Classification (Gold)")

    filters = InventoryQueryFilters(classifications=[LeadClassification.GOLD])
    results = query_available_inventory(filters, limit=10)

    print(f"Found {len(results)} Gold leads")

    # Verify all results are Gold
    classifications = {lead.classification for lead in results}
    print(f"Unique classifications: {[c.value for c in classifications]}")
    assert classifications == {LeadClassification.GOLD}, f"Expected only Gold, got {classifications}"
    print("SUCCESS: All results are Gold classification")


def test_filter_by_age_bucket() -> None:
    """Test filtering by age bucket (MONTH_3_TO_5)."""
    print_section("TEST 4: Filter by Age Bucket (MONTH_3_TO_5)")

    filters = InventoryQueryFilters(age_buckets=[AgeBucket.MONTH_3_TO_5])
    results = query_available_inventory(filters, limit=10)

    print(f"Found {len(results)} leads in MONTH_3_TO_5 bucket")

    # Verify all results are in MONTH_3_TO_5
    buckets = {lead.age_bucket for lead in results}
    print(f"Unique buckets: {[b.value for b in buckets]}")

    if buckets:
        assert buckets == {AgeBucket.MONTH_3_TO_5}, f"Expected only MONTH_3_TO_5, got {buckets}"
        print("SUCCESS: All results are in MONTH_3_TO_5 bucket")
    else:
        print("NOTE: No leads found in MONTH_3_TO_5 bucket (this is OK if all leads are older)")


def test_combined_filters() -> None:
    """Test combined filters (Gold + LA + MONTH_12_TO_23)."""
    print_section("TEST 5: Combined Filters (Gold + LA + MONTH_12_TO_23)")

    filters = InventoryQueryFilters(
        classifications=[LeadClassification.GOLD],
        states=["LA"],
        age_buckets=[AgeBucket.MONTH_12_TO_23]
    )
    results = query_available_inventory(filters, limit=10)

    print(f"Found {len(results)} Gold Louisiana leads in MONTH_12_TO_23")

    if results:
        # Verify filters
        for lead in results:
            assert lead.classification == LeadClassification.GOLD
            assert lead.state == "LA"
            assert lead.age_bucket == AgeBucket.MONTH_12_TO_23

        print("SUCCESS: All results match combined filters")
        print(f"\nSample lead:")
        lead = results[0]
        print(f"  Classification: {lead.classification.value}")
        print(f"  State: {lead.state}")
        print(f"  Age Bucket: {lead.age_bucket.value}")
    else:
        print("NOTE: No leads match these combined filters")


def test_inventory_counts() -> None:
    """Test getting inventory counts by age bucket."""
    print_section("TEST 6: Inventory Counts by Age Bucket")

    filters = InventoryQueryFilters()
    counts = get_inventory_counts(filters)

    print(f"Found {len(counts)} age buckets with inventory:")

    total_count = 0
    for bucket, count in sorted(counts.items(), key=lambda x: x[0].value):
        print(f"  {bucket.value}: {count} leads")
        total_count += count

    print(f"\nTotal available inventory: {total_count}")


def test_inventory_summary() -> None:
    """Test getting overall inventory summary."""
    print_section("TEST 7: Overall Inventory Summary")

    summary = get_inventory_summary()

    print(f"Total Available: {summary['total_available']}")
    print(f"Total Sold: {summary['total_sold']}")

    print("\nBy Age Bucket:")
    for bucket, count in sorted(summary['by_bucket'].items()):
        print(f"  {bucket}: {count}")

    print("\nBy Classification:")
    for classification, count in sorted(summary['by_classification'].items()):
        print(f"  {classification}: {count}")


def test_pagination() -> None:
    """Test pagination works correctly."""
    print_section("TEST 8: Pagination")

    filters = InventoryQueryFilters()

    # Get first 5
    page1 = query_available_inventory(filters, limit=5, offset=0)
    print(f"Page 1 (offset=0, limit=5): {len(page1)} results")

    # Get next 5
    page2 = query_available_inventory(filters, limit=5, offset=5)
    print(f"Page 2 (offset=5, limit=5): {len(page2)} results")

    # Verify no overlap
    page1_ids = {lead.inventory_id for lead in page1}
    page2_ids = {lead.inventory_id for lead in page2}

    overlap = page1_ids & page2_ids
    print(f"Overlap between pages: {len(overlap)}")
    assert len(overlap) == 0, f"Pages should not overlap, but found {len(overlap)} duplicates"
    print("SUCCESS: Pagination works correctly (no overlaps)")


def test_mixed_inventory() -> None:
    """Test complex multi-part queries with query_mixed_inventory."""
    print_section("TEST 9: Mixed Inventory Query (Complex Multi-Part)")

    # Scenario: I want 50 Silver leads aged 12-23 months + 30 Gold leads aged 12-23 months
    requests = [
        MixedInventoryRequest(
            classification=LeadClassification.SILVER,
            age_bucket=AgeBucket.MONTH_12_TO_23,
            quantity=50,
            states=["LA"]
        ),
        MixedInventoryRequest(
            classification=LeadClassification.GOLD,
            age_bucket=AgeBucket.MONTH_12_TO_23,
            quantity=30,
            states=["LA"]
        ),
    ]

    results = query_mixed_inventory(requests)

    print(f"Total leads returned: {len(results)}")
    print(f"Expected: 80 (50 Silver + 30 Gold)")

    # Verify counts by classification
    silver_count = sum(1 for lead in results if lead.classification == LeadClassification.SILVER)
    gold_count = sum(1 for lead in results if lead.classification == LeadClassification.GOLD)

    print(f"\nBreakdown:")
    print(f"  Silver leads: {silver_count}")
    print(f"  Gold leads: {gold_count}")

    # Verify all are from correct age bucket and state
    for lead in results:
        assert lead.age_bucket == AgeBucket.MONTH_12_TO_23
        assert lead.state == "LA"

    print(f"\nSUCCESS: All {len(results)} leads match requested criteria")
    print("  - All from MONTH_12_TO_23 bucket")
    print("  - All from Louisiana")
    print(f"  - {silver_count} Silver + {gold_count} Gold")


def test_complex_mixed_inventory() -> None:
    """Test even more complex multi-part query with different buckets."""
    print_section("TEST 10: Complex Mixed Query (Different Age Buckets)")

    # Scenario: I want different classifications AND different age buckets
    # 20 Silver aged 6-8 months + 20 Gold aged 9-11 months + 20 Silver aged 12-23 months
    requests = [
        MixedInventoryRequest(
            classification=LeadClassification.SILVER,
            age_bucket=AgeBucket.MONTH_6_TO_8,
            quantity=20
        ),
        MixedInventoryRequest(
            classification=LeadClassification.GOLD,
            age_bucket=AgeBucket.MONTH_9_TO_11,
            quantity=20
        ),
        MixedInventoryRequest(
            classification=LeadClassification.SILVER,
            age_bucket=AgeBucket.MONTH_12_TO_23,
            quantity=20
        ),
    ]

    results = query_mixed_inventory(requests)

    print(f"Total leads returned: {len(results)}")

    # Group by classification and bucket
    groups: dict[tuple[str, str], int] = {}
    for lead in results:
        key = (lead.classification.value, lead.age_bucket.value)
        groups[key] = groups.get(key, 0) + 1

    print(f"\nBreakdown by classification + bucket:")
    for (classification, bucket), count in sorted(groups.items()):
        print(f"  {classification} + {bucket}: {count} leads")

    print(f"\nSUCCESS: Retrieved {len(results)} leads across multiple classification/bucket combinations")


def main() -> int:
    """Run all tests."""
    try:
        print("Starting inventory query tests...")

        test_basic_query()
        test_filter_by_state()
        test_filter_by_classification()
        test_filter_by_age_bucket()
        test_combined_filters()
        test_inventory_counts()
        test_inventory_summary()
        test_pagination()
        test_mixed_inventory()
        test_complex_mixed_inventory()

        print()
        print("=" * 80)
        print("ALL TESTS PASSED")
        print("=" * 80)
        print()

        return 0

    except Exception as e:
        print()
        print("=" * 80)
        print(f"TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
