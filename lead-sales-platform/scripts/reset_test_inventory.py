"""
Reset test inventory - mark all sold inventory as available again.

This is for development/testing purposes only.
NEVER run this in production!
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from repositories.client import supabase


def reset_inventory():
    """Reset all sold inventory back to available status."""

    print("=" * 60)
    print("RESETTING TEST INVENTORY")
    print("=" * 60)
    print("WARNING: This will mark ALL sold inventory as available again.")
    print("This is for testing/demo purposes ONLY.")
    print("=" * 60)

    # Count currently sold items
    sold_response = (
        supabase.table("inventory")
        .select("*", count="exact")
        .not_.is_("sold_at_utc", "null")
        .execute()
    )
    sold_count = getattr(sold_response, "count", 0) or 0

    print(f"\nCurrently sold items: {sold_count}")

    if sold_count == 0:
        print("No sold items to reset. Inventory is already clean.")
        return

    # Reset all sold inventory
    print(f"\nResetting {sold_count} sold items back to available...")

    update_response = (
        supabase.table("inventory")
        .update({"sold_at_utc": None})
        .not_.is_("sold_at_utc", "null")
        .execute()
    )

    # Verify reset
    remaining_sold = (
        supabase.table("inventory")
        .select("*", count="exact")
        .not_.is_("sold_at_utc", "null")
        .execute()
    )
    remaining_count = getattr(remaining_sold, "count", 0) or 0

    if remaining_count == 0:
        print(f"[SUCCESS] All {sold_count} items have been reset to available!")
    else:
        print(f"[WARNING] {remaining_count} items still marked as sold")

    # Show updated stats
    available_response = (
        supabase.table("inventory")
        .select("*", count="exact")
        .is_("sold_at_utc", "null")
        .execute()
    )
    available_count = getattr(available_response, "count", 0) or 0

    print("\n" + "=" * 60)
    print("INVENTORY RESET COMPLETE")
    print("=" * 60)
    print(f"Available inventory: {available_count}")
    print(f"Sold inventory:      {remaining_count}")
    print("=" * 60)


if __name__ == "__main__":
    reset_inventory()
