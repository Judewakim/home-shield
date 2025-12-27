#!/usr/bin/env python3
"""
Lead Export Script

Exports leads from the Supabase database to CSV format for client delivery.
All lead fields are exported as individual CSV columns.

Usage:
    python export_leads.py --output leads_export.csv
    python export_leads.py --classification Gold --output gold_leads.csv
    python export_leads.py --state LA --output louisiana_leads.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.lead import Lead
from repositories.lead_repository import list_leads_by_filter

# CSV column names in order (matching original CSV format)
CSV_COLUMNS = [
    "Mortage ID",
    "Campaign ID",
    "Type",
    "Call In Date",
    "Status",
    "Full Name",
    "First Name",
    "Last Name",
    "Co-Borrower Name",
    "Address",
    "City",
    "County",
    "State",
    "Zip",
    "Mortgage Amount",
    "Lender",
    "Sale Date",
    "Agent ID",
    "Call In Phone Number",
    "Borrower Age",
    "Borrower Medical Issues",
    "Borrower Tobacco Use",
    "Co-Borrower ?",
    "Borrower Phone",
    "Source",
]


def lead_to_csv_row(lead: Lead) -> dict[str, str]:
    """
    Convert a Lead domain object to a CSV row dictionary.

    Args:
        lead: Lead domain object

    Returns:
        Dictionary mapping CSV column names to values
    """
    return {
        "Mortage ID": lead.mortgage_id or "",
        "Campaign ID": lead.campaign_id or "",
        "Type": lead.type or "",
        "Call In Date": lead.call_in_date or "",
        "Status": lead.status or "",
        "Full Name": lead.full_name or "",
        "First Name": lead.first_name or "",
        "Last Name": lead.last_name or "",
        "Co-Borrower Name": lead.co_borrower_name or "",
        "Address": lead.address or "",
        "City": lead.city or "",
        "County": lead.county or "",
        "State": lead.state,
        "Zip": lead.zip or "",
        "Mortgage Amount": lead.mortgage_amount or "",
        "Lender": lead.lender or "",
        "Sale Date": lead.sale_date or "",
        "Agent ID": lead.agent_id or "",
        "Call In Phone Number": lead.call_in_phone_number or "",
        "Borrower Age": lead.borrower_age or "",
        "Borrower Medical Issues": lead.borrower_medical_issues or "",
        "Borrower Tobacco Use": lead.borrower_tobacco_use or "",
        "Co-Borrower ?": lead.co_borrower or "",
        "Borrower Phone": lead.borrower_phone or "",
        "Source": lead.source or "",
    }


def export_leads_to_csv(
    leads: List[Lead],
    output_path: str,
) -> None:
    """
    Export leads to CSV file with all columns.

    Args:
        leads: List of Lead objects to export
        output_path: Path to output CSV file

    Raises:
        ValueError: If leads list is empty
    """
    if not leads:
        raise ValueError("No leads to export")

    print(f"Exporting {len(leads)} leads to {output_path}")
    print(f"CSV will contain {len(CSV_COLUMNS)} columns")

    # Write CSV
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for lead in leads:
            writer.writerow(lead_to_csv_row(lead))

    print(f"✓ Successfully exported {len(leads)} leads")


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Export leads from Supabase database to CSV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all leads
  python export_leads.py --output all_leads.csv

  # Export only Gold leads
  python export_leads.py --classification Gold --output gold_leads.csv

  # Export only Silver leads
  python export_leads.py --classification Silver --output silver_leads.csv

  # Export leads from a specific state
  python export_leads.py --state LA --output louisiana_leads.csv

  # Export Gold leads from Louisiana
  python export_leads.py --classification Gold --state LA --output la_gold.csv
        """
    )

    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Path to output CSV file"
    )

    parser.add_argument(
        "--classification",
        "-c",
        choices=["Gold", "Silver"],
        help="Filter by classification (Gold or Silver)"
    )

    parser.add_argument(
        "--state",
        "-s",
        help="Filter by state code (e.g., LA, CA, NY)"
    )

    args = parser.parse_args()

    try:
        # Fetch leads from database
        print("Fetching leads from database...")
        print(f"  Classification filter: {args.classification or 'None (all)'}")
        print(f"  State filter: {args.state or 'None (all)'}")
        print()

        leads = list_leads_by_filter(
            state=args.state,
            classification=args.classification,
        )

        if not leads:
            print("No leads found matching the specified filters")
            return 1

        # Export to CSV
        export_leads_to_csv(leads, args.output)

        # Print summary
        print()
        print("=" * 60)
        print("EXPORT SUMMARY")
        print("=" * 60)
        print(f"Total leads exported: {len(leads)}")

        # Count classifications
        gold_count = sum(1 for lead in leads if lead.classification.value == "Gold")
        silver_count = len(leads) - gold_count

        print(f"  Gold leads:   {gold_count}")
        print(f"  Silver leads: {silver_count}")
        print()
        print(f"Output file: {args.output}")
        print("=" * 60)

        return 0

    except KeyboardInterrupt:
        print("\n\nExport interrupted by user")
        return 130

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
