#!/usr/bin/env python3
"""
Example: Using query_mixed_inventory for complex multi-part queries.

This demonstrates how to query for specific quantities of leads with
different classification and age bucket combinations.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.inventory_query_repository import (
    MixedInventoryRequest,
    query_mixed_inventory,
)


def example_1_same_bucket_different_classifications():
    """
    Example 1: Get 50 Silver + 30 Gold leads, all from the same age bucket.

    Use case: "I want to buy 80 leads aged 12-23 months,
              with a mix of 50 Silver and 30 Gold."
    """
    print("=" * 80)
    print("EXAMPLE 1: Same Age Bucket, Different Classifications")
    print("=" * 80)
    print()

    requests = [
        MixedInventoryRequest(
            classification=LeadClassification.SILVER,
            age_bucket=AgeBucket.MONTH_12_TO_23,
            quantity=50
        ),
        MixedInventoryRequest(
            classification=LeadClassification.GOLD,
            age_bucket=AgeBucket.MONTH_12_TO_23,
            quantity=30
        ),
    ]

    leads = query_mixed_inventory(requests)

    print(f"Total leads: {len(leads)}")
    print(f"Silver: {sum(1 for l in leads if l.classification == LeadClassification.SILVER)}")
    print(f"Gold: {sum(1 for l in leads if l.classification == LeadClassification.GOLD)}")
    print()


def example_2_different_buckets_with_state_filter():
    """
    Example 2: Different age buckets with state filtering.

    Use case: "I want 20 Silver leads aged 6-8 months from Louisiana,
              plus 20 Gold leads aged 9-11 months from Louisiana."
    """
    print("=" * 80)
    print("EXAMPLE 2: Different Age Buckets + State Filter")
    print("=" * 80)
    print()

    requests = [
        MixedInventoryRequest(
            classification=LeadClassification.SILVER,
            age_bucket=AgeBucket.MONTH_6_TO_8,
            quantity=20,
            states=["LA"]
        ),
        MixedInventoryRequest(
            classification=LeadClassification.GOLD,
            age_bucket=AgeBucket.MONTH_9_TO_11,
            quantity=20,
            states=["LA"]
        ),
    ]

    leads = query_mixed_inventory(requests)

    print(f"Total leads: {len(leads)}")

    # Group by classification and bucket
    for classification in [LeadClassification.SILVER, LeadClassification.GOLD]:
        for bucket in [AgeBucket.MONTH_6_TO_8, AgeBucket.MONTH_9_TO_11]:
            count = sum(1 for l in leads
                       if l.classification == classification and l.age_bucket == bucket)
            if count > 0:
                print(f"  {classification.value} + {bucket.value}: {count}")
    print()


def example_3_complex_multi_part():
    """
    Example 3: Complex multi-part with many combinations.

    Use case: "I want a diverse portfolio:
              - 100 Gold leads aged 12-23 months
              - 50 Silver leads aged 9-11 months
              - 50 Gold leads aged 6-8 months
              - 100 Silver leads aged 24+ months"
    """
    print("=" * 80)
    print("EXAMPLE 3: Complex Multi-Part Query (Diverse Portfolio)")
    print("=" * 80)
    print()

    requests = [
        MixedInventoryRequest(
            classification=LeadClassification.GOLD,
            age_bucket=AgeBucket.MONTH_12_TO_23,
            quantity=100
        ),
        MixedInventoryRequest(
            classification=LeadClassification.SILVER,
            age_bucket=AgeBucket.MONTH_9_TO_11,
            quantity=50
        ),
        MixedInventoryRequest(
            classification=LeadClassification.GOLD,
            age_bucket=AgeBucket.MONTH_6_TO_8,
            quantity=50
        ),
        MixedInventoryRequest(
            classification=LeadClassification.SILVER,
            age_bucket=AgeBucket.MONTH_24_PLUS,
            quantity=100
        ),
    ]

    leads = query_mixed_inventory(requests)

    print(f"Total leads: {len(leads)}")
    print("\nBreakdown:")

    # Group by classification and bucket
    groups = {}
    for lead in leads:
        key = (lead.classification, lead.age_bucket)
        groups[key] = groups.get(key, 0) + 1

    for (classification, bucket), count in sorted(groups.items(),
                                                   key=lambda x: (x[0][0].value, x[0][1].value)):
        print(f"  {classification.value:6} + {bucket.value:14} = {count:3} leads")
    print()


def main():
    """Run all examples."""
    print("\n")
    print("*" * 80)
    print("MIXED INVENTORY QUERY EXAMPLES")
    print("*" * 80)
    print()

    example_1_same_bucket_different_classifications()
    example_2_different_buckets_with_state_filter()
    example_3_complex_multi_part()

    print("*" * 80)
    print("All examples completed successfully!")
    print("*" * 80)
    print()


if __name__ == "__main__":
    main()
