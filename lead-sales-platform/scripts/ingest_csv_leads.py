#!/usr/bin/env python3
"""
CSV Lead Ingestion Script

Imports leads from CSV files into the Supabase database with:
- Gold/Silver classification based on data completeness
- Dynamic timezone detection from State column
- Batch processing with error handling
- Summary statistics and error logging

Usage:
    python ingest_csv_leads.py path/to/leads.csv
    python ingest_csv_leads.py path/to/leads.csv --batch-size 500 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.lead import Lead
from repositories.lead_repository import insert_lead, insert_leads_bulk
from scripts.classification import classify_lead, get_classification_summary
from scripts.timezone_utils import parse_timestamp_with_state_timezone


@dataclass
class IngestionResult:
    """Results from CSV ingestion operation."""
    total_rows: int
    successful: int
    failed: int
    skipped: int
    gold_count: int
    silver_count: int
    errors: list[dict]


def validate_row(row: dict[str, str], row_num: int) -> tuple[bool, str | None]:
    """
    Validate that a CSV row has all required fields.

    Required fields for ingestion:
    - State: Used for timezone detection
    - Call In Date: Timestamp for created_at_utc

    Note: Source is now optional - empty Source classifies lead as Silver.

    Args:
        row: CSV row dictionary
        row_num: Row number for error reporting

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_fields = ["State", "Call In Date"]

    for field in required_fields:
        value = row.get(field, "").strip()
        if not value:
            return False, f"Missing required field: {field}"

    return True, None


def create_lead_from_row(row: dict[str, str]) -> Lead:
    """
    Create a Lead domain object from a CSV row.

    Args:
        row: CSV row dictionary

    Returns:
        Lead domain object with all fields populated

    Raises:
        ValueError: If timestamp parsing fails or required fields are missing

    Notes:
        - Source field is optional; empty Source classifies lead as Silver
        - All CSV columns are mapped to individual Lead fields
        - Empty strings are preserved (not converted to None)
    """
    # Parse timestamp with state-based timezone detection
    created_at_utc = parse_timestamp_with_state_timezone(
        timestamp_str=row["Call In Date"],
        state_code=row["State"]
    )

    # Classify lead based on data completeness (including Source)
    classification = classify_lead(row)

    # Helper to get optional field (preserve empty strings)
    def get_field(key: str) -> str | None:
        value = row.get(key, "").strip()
        return value if value else None

    # Create frozen Lead domain object with all fields
    return Lead(
        # Core identifiers (required)
        lead_id=uuid4(),
        state=row["State"],
        classification=classification,
        created_at_utc=created_at_utc,

        # Optional fields
        source=get_field("Source"),

        # Mortgage identification
        mortgage_id=get_field("Mortage ID"),  # Note: CSV has typo "Mortage"
        campaign_id=get_field("Campaign ID"),
        type=get_field("Type"),
        status=get_field("Status"),

        # Contact information
        full_name=get_field("Full Name"),
        first_name=get_field("First Name"),
        last_name=get_field("Last Name"),
        co_borrower_name=get_field("Co-Borrower Name"),

        # Address fields
        address=get_field("Address"),
        city=get_field("City"),
        county=get_field("County"),
        zip=get_field("Zip"),

        # Financial information
        mortgage_amount=get_field("Mortgage Amount"),
        lender=get_field("Lender"),
        sale_date=get_field("Sale Date"),

        # Agent and contact details
        agent_id=get_field("Agent ID"),
        call_in_phone_number=get_field("Call In Phone Number"),
        borrower_phone=get_field("Borrower Phone"),

        # Qualification fields
        borrower_age=get_field("Borrower Age"),
        borrower_medical_issues=get_field("Borrower Medical Issues"),
        borrower_tobacco_use=get_field("Borrower Tobacco Use"),
        co_borrower=get_field("Co-Borrower ?"),

        # Original timestamp string
        call_in_date=row.get("Call In Date", ""),
    )


def process_batch(
    batch: list[Lead],
    dry_run: bool = False
) -> tuple[int, list[dict]]:
    """
    Process a batch of leads with bulk insert and error fallback.

    Strategy:
    1. Try bulk insert first (fast)
    2. On error, fallback to one-by-one inserts (error isolation)

    Args:
        batch: List of Lead objects to insert
        dry_run: If True, skip database insertion

    Returns:
        Tuple of (success_count, errors)
    """
    if not batch:
        return 0, []

    if dry_run:
        # Dry run: just validate, don't insert
        return len(batch), []

    try:
        # Try bulk insert (fast path)
        insert_leads_bulk(batch)
        return len(batch), []

    except Exception as bulk_error:
        # Bulk insert failed - fall back to one-by-one for error isolation
        print(f"  Bulk insert failed: {bulk_error}")
        print(f"  Falling back to individual inserts for error isolation...")

        success_count = 0
        errors = []

        for lead in batch:
            try:
                insert_lead(lead)
                success_count += 1
            except Exception as e:
                errors.append({
                    "lead_id": str(lead.lead_id),
                    "error": str(e),
                    "state": lead.state,
                    "source": lead.source,
                })

        return success_count, errors


def ingest_csv(
    csv_path: str,
    batch_size: int = 250,
    dry_run: bool = False
) -> IngestionResult:
    """
    Ingest leads from a CSV file into the database.

    Args:
        csv_path: Path to the CSV file
        batch_size: Number of rows to process per batch
        dry_run: If True, parse and validate but don't insert

    Returns:
        IngestionResult with statistics and errors

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV is malformed
    """
    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    result = IngestionResult(
        total_rows=0,
        successful=0,
        failed=0,
        skipped=0,
        gold_count=0,
        silver_count=0,
        errors=[],
    )

    print(f"Reading CSV: {csv_path}")
    print(f"Batch size: {batch_size}")
    print(f"Dry run: {dry_run}")
    print()

    with open(csv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        # Validate CSV has required columns
        if not reader.fieldnames:
            raise ValueError("CSV file is empty or malformed")

        required_columns = {"State", "Call In Date"}
        missing_columns = required_columns - set(reader.fieldnames)
        if missing_columns:
            raise ValueError(
                f"CSV missing required columns: {', '.join(missing_columns)}"
            )

        batch = []

        for row_num, row in enumerate(reader, start=2):  # Row 1 is header
            result.total_rows += 1

            # Validate row
            is_valid, error_msg = validate_row(row, row_num)
            if not is_valid:
                result.skipped += 1
                result.errors.append({
                    "row_num": row_num,
                    "error": error_msg,
                    "csv_row": row,
                })
                continue

            try:
                # Create Lead object
                lead = create_lead_from_row(row)
                batch.append(lead)

                # Track classification counts
                if lead.classification.value == "Gold":
                    result.gold_count += 1
                else:
                    result.silver_count += 1

                # Process batch when full
                if len(batch) >= batch_size:
                    success_count, batch_errors = process_batch(batch, dry_run)
                    result.successful += success_count
                    result.failed += len(batch_errors)
                    result.errors.extend(batch_errors)

                    print(f"Processed {result.total_rows} rows "
                          f"({result.successful} successful, "
                          f"{result.failed} failed, "
                          f"{result.skipped} skipped)")

                    batch = []

            except Exception as e:
                result.failed += 1
                result.errors.append({
                    "row_num": row_num,
                    "error": f"Failed to create Lead: {str(e)}",
                    "csv_row": row,
                })
                continue

        # Process remaining batch
        if batch:
            success_count, batch_errors = process_batch(batch, dry_run)
            result.successful += success_count
            result.failed += len(batch_errors)
            result.errors.extend(batch_errors)

    return result


def print_summary(result: IngestionResult) -> None:
    """Print ingestion summary statistics."""
    print()
    print("=" * 60)
    print("INGESTION SUMMARY")
    print("=" * 60)
    print(f"Total Rows:       {result.total_rows}")
    print(f"Successful:       {result.successful}")
    print(f"Failed:           {result.failed}")
    print(f"Skipped:          {result.skipped}")
    print()
    print(f"Gold Leads:       {result.gold_count}")
    print(f"Silver Leads:     {result.silver_count}")
    print()

    if result.errors:
        print(f"Errors:           {len(result.errors)}")
        print()
        print("First 5 errors:")
        for error in result.errors[:5]:
            print(f"  - Row {error.get('row_num', 'N/A')}: {error['error']}")
        if len(result.errors) > 5:
            print(f"  ... and {len(result.errors) - 5} more")
    else:
        print("No errors!")

    print("=" * 60)


def save_error_log(errors: list[dict], output_path: str) -> None:
    """Save error details to JSON file."""
    if not errors:
        return

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(errors, f, indent=2, default=str)

    print(f"\nError log saved to: {output_path}")


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="Ingest leads from CSV into Supabase database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic import
  python ingest_csv_leads.py leads.csv

  # Dry run (parse only, don't insert)
  python ingest_csv_leads.py leads.csv --dry-run

  # Custom batch size
  python ingest_csv_leads.py leads.csv --batch-size 500

  # Save error log to custom path
  python ingest_csv_leads.py leads.csv --error-log errors.json
        """
    )

    parser.add_argument(
        "csv_path",
        help="Path to the CSV file to ingest"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=250,
        help="Number of rows to process per batch (default: 250)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate CSV without inserting to database"
    )

    parser.add_argument(
        "--error-log",
        default="ingestion_errors.json",
        help="Path to save error log (default: ingestion_errors.json)"
    )

    args = parser.parse_args()

    try:
        # Run ingestion
        print("Starting CSV ingestion...")
        print()

        result = ingest_csv(
            csv_path=args.csv_path,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )

        # Print summary
        print_summary(result)

        # Save error log
        if result.errors:
            save_error_log(result.errors, args.error_log)

        # Exit code based on results
        if result.failed > 0 or result.skipped > 0:
            return 1  # Partial success
        else:
            return 0  # Full success

    except KeyboardInterrupt:
        print("\n\nIngestion interrupted by user")
        return 130

    except Exception as e:
        print(f"\nFATAL ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
