#!/usr/bin/env python3
"""
Inventory Generation Script

Scans all leads and creates inventory records for eligible age buckets.
This script should be run daily via cron to keep inventory up-to-date.

Usage:
    python generate_inventory.py
    python generate_inventory.py --as-of-date "2025-12-27"
    python generate_inventory.py --dry-run

Schedule via cron (daily at 1 AM UTC):
    0 1 * * * cd /app/lead-sales-platform && python scripts/generate_inventory.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.age_bucket import AgeBucket, LeadAge
from repositories.client import supabase


def generate_inventory_for_all_leads(
    as_of_date: datetime,
    dry_run: bool = False
) -> dict[str, int]:
    """
    Scan all leads and create inventory records for eligible age buckets.

    Args:
        as_of_date: The timestamp to use for age calculation
        dry_run: If True, only simulate without inserting records

    Returns:
        Dictionary with statistics: {
            'total_leads': int,
            'eligible_leads': int,
            'new_inventory_created': int,
            'already_exists': int,
            'too_young': int
        }
    """
    stats = {
        'total_leads': 0,
        'eligible_leads': 0,
        'new_inventory_created': 0,
        'already_exists': 0,
        'too_young': 0,
    }

    print(f"Generating inventory as of: {as_of_date.isoformat()}")
    print(f"Dry run: {dry_run}")
    print()

    # Query all leads (Supabase RPC to get count first, then paginate)
    print("Fetching all leads from database...")

    # Get total count first
    count_response = supabase.table("leads").select("*", count="exact").execute()
    total_leads_in_db = getattr(count_response, "count", 0) or 0
    print(f"Database contains {total_leads_in_db} total leads")

    # Fetch all leads with pagination
    all_leads = []
    page_size = 1000
    offset = 0

    while offset < total_leads_in_db:
        print(f"  Fetching leads {offset} to {offset + page_size}...")
        response = (
            supabase.table("leads")
            .select("lead_id, created_at_utc")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        error = getattr(response, "error", None)
        if error:
            raise RuntimeError(f"Failed to fetch leads: {error}")

        page_leads = getattr(response, "data", None) or []
        if not page_leads:
            break

        all_leads.extend(page_leads)
        offset += len(page_leads)

    leads = all_leads
    stats['total_leads'] = len(leads)

    print(f"Found {stats['total_leads']} leads")
    print()

    # Process each lead
    for idx, lead_row in enumerate(leads, start=1):
        lead_id = UUID(lead_row["lead_id"])
        created_at_utc_str = lead_row["created_at_utc"]

        # Parse timestamp
        if isinstance(created_at_utc_str, str):
            created_at_utc_str = created_at_utc_str.replace("Z", "+00:00")
            created_at_utc = datetime.fromisoformat(created_at_utc_str)
        elif isinstance(created_at_utc_str, datetime):
            created_at_utc = created_at_utc_str
        else:
            print(f"  WARNING: Lead {lead_id} has invalid created_at_utc type")
            continue

        # Ensure UTC
        if created_at_utc.tzinfo is None:
            created_at_utc = created_at_utc.replace(tzinfo=timezone.utc)

        # Calculate age
        lead_age = LeadAge(created_at_utc=created_at_utc, as_of_utc=as_of_date)
        age_days = lead_age.age_days()
        bucket = lead_age.bucket()

        # Progress indicator
        if idx % 500 == 0:
            print(f"Processed {idx}/{stats['total_leads']} leads...")

        # Skip if too young (< 90 days)
        if bucket is None:
            stats['too_young'] += 1
            continue

        stats['eligible_leads'] += 1

        # Check if inventory already exists
        check_response = (
            supabase.table("inventory")
            .select("inventory_id")
            .eq("lead_id", str(lead_id))
            .eq("age_bucket", bucket.value)
            .limit(1)
            .execute()
        )

        existing = getattr(check_response, "data", None) or []

        if existing:
            stats['already_exists'] += 1
            continue

        # Create new inventory record
        if not dry_run:
            inventory_payload = {
                "lead_id": str(lead_id),
                "age_bucket": bucket.value,
                "created_at_utc": as_of_date.isoformat(),
                "sold_at_utc": None,  # Available
            }

            insert_response = supabase.table("inventory").insert(inventory_payload).execute()
            insert_error = getattr(insert_response, "error", None)

            if insert_error:
                print(f"  ERROR: Failed to create inventory for lead {lead_id}: {insert_error}")
                continue

        stats['new_inventory_created'] += 1

        if stats['new_inventory_created'] % 100 == 0:
            print(f"  Created {stats['new_inventory_created']} new inventory records...")

    return stats


def print_summary(stats: dict[str, int], dry_run: bool) -> None:
    """Print inventory generation summary."""
    print()
    print("=" * 60)
    print("INVENTORY GENERATION SUMMARY")
    print("=" * 60)
    print(f"Total Leads:              {stats['total_leads']}")
    print(f"Eligible Leads:           {stats['eligible_leads']} (>= 90 days old)")
    print(f"Too Young:                {stats['too_young']} (< 90 days old)")
    print()
    print(f"New Inventory Created:    {stats['new_inventory_created']}")
    print(f"Already Exists:           {stats['already_exists']}")
    print()

    if dry_run:
        print("** DRY RUN - No records were inserted **")
    else:
        print(f"SUCCESS: Created {stats['new_inventory_created']} inventory records")

    print("=" * 60)


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Generate inventory records for all eligible leads",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate inventory with current date
  python generate_inventory.py

  # Generate inventory for specific date
  python generate_inventory.py --as-of-date "2025-12-27"

  # Dry run (no inserts)
  python generate_inventory.py --dry-run

Schedule via cron (daily at 1 AM UTC):
  0 1 * * * cd /app/lead-sales-platform && python scripts/generate_inventory.py
        """
    )

    parser.add_argument(
        "--as-of-date",
        type=str,
        help="ISO date to use for age calculation (default: now)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without inserting records"
    )

    args = parser.parse_args()

    try:
        # Determine as-of date
        if args.as_of_date:
            as_of_date = datetime.fromisoformat(args.as_of_date)
            if as_of_date.tzinfo is None:
                as_of_date = as_of_date.replace(tzinfo=timezone.utc)
        else:
            as_of_date = datetime.now(timezone.utc)

        # Run inventory generation
        print("Starting inventory generation...")
        print()

        stats = generate_inventory_for_all_leads(
            as_of_date=as_of_date,
            dry_run=args.dry_run
        )

        # Print summary
        print_summary(stats, args.dry_run)

        return 0

    except KeyboardInterrupt:
        print("\n\nInventory generation interrupted by user")
        return 130

    except Exception as e:
        print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
