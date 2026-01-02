"""
Check inventory status - how many items are sold vs available.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from repositories.client import supabase


def check_inventory_status():
    """Check how many inventory items are sold vs available."""

    # Count total inventory
    total_response = supabase.table("inventory").select("*", count="exact").execute()
    total_count = getattr(total_response, "count", 0) or 0

    # Count available (not sold)
    available_response = (
        supabase.table("inventory")
        .select("*", count="exact")
        .is_("sold_at_utc", "null")
        .execute()
    )
    available_count = getattr(available_response, "count", 0) or 0

    # Count sold
    sold_response = (
        supabase.table("inventory")
        .select("*", count="exact")
        .not_.is_("sold_at_utc", "null")
        .execute()
    )
    sold_count = getattr(sold_response, "count", 0) or 0

    print("=" * 50)
    print("INVENTORY STATUS")
    print("=" * 50)
    print(f"Total inventory items:     {total_count}")
    print(f"Available (not sold):      {available_count}")
    print(f"Sold:                      {sold_count}")
    print(f"Percentage sold:           {(sold_count / total_count * 100):.1f}%" if total_count > 0 else "N/A")
    print("=" * 50)

    # Check if we're running out of specific types
    print("\nBreakdown by classification and age bucket:")
    print("-" * 50)

    # Get available inventory with classification
    query = (
        supabase.table("inventory")
        .select("age_bucket, leads!inner(classification)")
        .is_("sold_at_utc", "null")
        .limit(1000)
        .execute()
    )

    rows = getattr(query, "data", [])

    # Count by classification and age bucket
    counts = {}
    for row in rows:
        age_bucket = row.get("age_bucket", "Unknown")
        classification = row.get("leads", {}).get("classification", "Unknown")
        key = f"{classification} - {age_bucket}"
        counts[key] = counts.get(key, 0) + 1

    # Sort and display
    for key in sorted(counts.keys()):
        print(f"{key}: {counts[key]} available")

    print("-" * 50)


if __name__ == "__main__":
    check_inventory_status()
