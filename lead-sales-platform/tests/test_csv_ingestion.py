"""
Unit tests for CSV ingestion functionality.

Tests classification logic, timestamp parsing, and Lead factory functions.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.lead import LeadClassification
from scripts.classification import classify_lead, get_classification_summary
from scripts.timezone_utils import (
    get_timezone_for_state,
    parse_timestamp_with_state_timezone,
)


class TestClassification:
    """Tests for lead classification logic."""

    def test_classify_gold_all_fields_present(self):
        """All required fields present → Gold"""
        row = {
            "Source": "CALL",
            "Borrower Age": "36",
            "Borrower Medical Issues": "No",
            "Borrower Tobacco Use": "No",
            "Co-Borrower ?": "No",
            "Borrower Phone": "2254859918",
        }
        assert classify_lead(row) == LeadClassification.GOLD

    def test_classify_gold_with_yes_values(self):
        """Yes values count as non-empty → Gold"""
        row = {
            "Source": "CALL",
            "Borrower Age": "68",
            "Borrower Medical Issues": "Yes",
            "Borrower Tobacco Use": "No",
            "Co-Borrower ?": "No",
            "Borrower Phone": "2253486122",
        }
        assert classify_lead(row) == LeadClassification.GOLD

    def test_classify_silver_missing_one_field(self):
        """Missing one field → Silver"""
        row = {
            "Source": "CALL",
            "Borrower Age": "49",
            "Borrower Medical Issues": "No",
            "Borrower Tobacco Use": "",  # Empty
            "Co-Borrower ?": "",
            "Borrower Phone": "",
        }
        assert classify_lead(row) == LeadClassification.SILVER

    def test_classify_silver_missing_source(self):
        """Missing Source field → Silver"""
        row = {
            "Source": "",  # Empty
            "Borrower Age": "36",
            "Borrower Medical Issues": "No",
            "Borrower Tobacco Use": "No",
            "Co-Borrower ?": "No",
            "Borrower Phone": "2254859918",
        }
        assert classify_lead(row) == LeadClassification.SILVER

    def test_classify_silver_all_fields_empty(self):
        """All fields empty → Silver"""
        row = {
            "Borrower Age": "",
            "Borrower Medical Issues": "",
            "Borrower Tobacco Use": "",
            "Co-Borrower ?": "",
            "Borrower Phone": "",
        }
        assert classify_lead(row) == LeadClassification.SILVER

    def test_classify_silver_whitespace_only(self):
        """Whitespace-only values → Silver"""
        row = {
            "Source": "CALL",
            "Borrower Age": "36",
            "Borrower Medical Issues": "No",
            "Borrower Tobacco Use": "   ",  # Whitespace
            "Co-Borrower ?": "No",
            "Borrower Phone": "1234567890",
        }
        assert classify_lead(row) == LeadClassification.SILVER

    def test_classify_silver_missing_columns(self):
        """Missing columns in dict → Silver"""
        row = {
            "Borrower Age": "36",
            "Borrower Medical Issues": "No",
            # Missing other fields
        }
        assert classify_lead(row) == LeadClassification.SILVER

    def test_get_classification_summary(self):
        """Test classification summary aggregation"""
        rows = [
            {
                "Source": "CALL",
                "Borrower Age": "36",
                "Borrower Medical Issues": "No",
                "Borrower Tobacco Use": "No",
                "Co-Borrower ?": "No",
                "Borrower Phone": "1234567890",
            },
            {
                "Source": "",  # Missing Source = Silver
                "Borrower Age": "",
                "Borrower Medical Issues": "",
                "Borrower Tobacco Use": "",
                "Co-Borrower ?": "",
                "Borrower Phone": "",
            },
            {
                "Source": "CALL",
                "Borrower Age": "68",
                "Borrower Medical Issues": "Yes",
                "Borrower Tobacco Use": "No",
                "Co-Borrower ?": "No",
                "Borrower Phone": "9876543210",
            },
        ]

        summary = get_classification_summary(rows)

        assert summary["Gold"] == 2
        assert summary["Silver"] == 1
        assert summary["Total"] == 3


class TestTimezoneUtils:
    """Tests for timezone detection and timestamp parsing."""

    def test_get_timezone_for_louisiana(self):
        """Louisiana → Central Time"""
        tz = get_timezone_for_state("LA")
        assert str(tz) == "America/Chicago"

    def test_get_timezone_for_california(self):
        """California → Pacific Time"""
        tz = get_timezone_for_state("CA")
        assert str(tz) == "America/Los_Angeles"

    def test_get_timezone_for_new_york(self):
        """New York → Eastern Time"""
        tz = get_timezone_for_state("NY")
        assert str(tz) == "America/New_York"

    def test_get_timezone_case_insensitive(self):
        """State code is case-insensitive"""
        tz_lower = get_timezone_for_state("la")
        tz_upper = get_timezone_for_state("LA")
        assert tz_lower == tz_upper

    def test_get_timezone_unknown_state_fallback(self):
        """Unknown state → UTC fallback"""
        tz = get_timezone_for_state("XX")
        assert str(tz) == "UTC"

    def test_get_timezone_whitespace_handling(self):
        """Handles whitespace in state code"""
        tz = get_timezone_for_state(" LA ")
        assert str(tz) == "America/Chicago"

    def test_parse_timestamp_with_state_timezone(self):
        """Parse timestamp and convert to UTC"""
        # Louisiana (Central Time) timestamp
        # During standard time (CST = UTC-6)
        result = parse_timestamp_with_state_timezone(
            "01-15-2025 10:00:00",  # Jan 15, 2025 10:00 AM CST
            "LA"
        )

        assert result.tzinfo == timezone.utc
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        # 10:00 CST = 16:00 UTC (+ 6 hours)
        assert result.hour == 16

    def test_parse_timestamp_daylight_saving(self):
        """Test timestamp during daylight saving time"""
        # Louisiana during DST (CDT = UTC-5)
        result = parse_timestamp_with_state_timezone(
            "06-09-2025 15:55:13",  # Jun 9, 2025 3:55 PM CDT
            "LA"
        )

        assert result.tzinfo == timezone.utc
        assert result.year == 2025
        assert result.month == 6
        assert result.day == 9
        # 15:55 CDT = 20:55 UTC (+ 5 hours)
        assert result.hour == 20
        assert result.minute == 55
        assert result.second == 13

    def test_parse_timestamp_different_states(self):
        """Same timestamp in different states produces different UTC times"""
        timestamp_str = "06-09-2025 12:00:00"

        # Eastern Time (UTC-4 during DST)
        ny_time = parse_timestamp_with_state_timezone(timestamp_str, "NY")

        # Central Time (UTC-5 during DST)
        la_time = parse_timestamp_with_state_timezone(timestamp_str, "LA")

        # Pacific Time (UTC-7 during DST)
        ca_time = parse_timestamp_with_state_timezone(timestamp_str, "CA")

        # All should be different UTC times (NY is earliest, CA is latest)
        assert ny_time < la_time < ca_time

    def test_parse_timestamp_unknown_state_uses_utc(self):
        """Unknown state falls back to UTC (no conversion)"""
        result = parse_timestamp_with_state_timezone(
            "06-09-2025 12:00:00",
            "XX"  # Unknown state
        )

        assert result.tzinfo == timezone.utc
        assert result.hour == 12  # No conversion, interpreted as UTC


class TestLeadFactory:
    """Tests for creating Lead objects from CSV rows."""

    def test_create_lead_basic(self):
        """Test basic Lead creation from CSV row"""
        from scripts.ingest_csv_leads import create_lead_from_row

        row = {
            "Mortage ID": "89536905",
            "State": "LA",
            "Source": "CALL",
            "Call In Date": "06-09-2025 15:55:13",
            "Borrower Age": "",
            "Borrower Medical Issues": "",
            "Borrower Tobacco Use": "",
            "Co-Borrower ?": "",
            "Borrower Phone": "",
        }

        lead = create_lead_from_row(row)

        assert lead.state == "LA"
        assert lead.source == "CALL"
        assert lead.classification == LeadClassification.SILVER
        assert lead.created_at_utc.tzinfo == timezone.utc
        assert lead.mortgage_id == "89536905"

    def test_create_lead_gold_classification(self):
        """Test Lead creation with Gold classification"""
        from scripts.ingest_csv_leads import create_lead_from_row

        row = {
            "State": "LA",
            "Source": "CALL",
            "Call In Date": "06-07-2025 08:05:14",
            "Borrower Age": "36",
            "Borrower Medical Issues": "No",
            "Borrower Tobacco Use": "No",
            "Co-Borrower ?": "No",
            "Borrower Phone": "2254859918",
        }

        lead = create_lead_from_row(row)

        assert lead.classification == LeadClassification.GOLD

    def test_create_lead_preserves_all_columns(self):
        """Test that all CSV columns are mapped to Lead fields"""
        from scripts.ingest_csv_leads import create_lead_from_row

        row = {
            "Mortage ID": "123",
            "Campaign ID": "WK060225A",
            "Type": "NEW MTG",
            "State": "LA",
            "Source": "CALL",
            "Call In Date": "06-09-2025 15:55:13",
            "Status": "NEW",
            "Full Name": "John Doe",
            "Mortgage Amount": "$100,000",
            "Borrower Age": "",
            "Borrower Medical Issues": "",
            "Borrower Tobacco Use": "",
            "Co-Borrower ?": "",
            "Borrower Phone": "",
        }

        lead = create_lead_from_row(row)

        assert lead.mortgage_id == "123"
        assert lead.campaign_id == "WK060225A"
        assert lead.type == "NEW MTG"
        assert lead.status == "NEW"
        assert lead.full_name == "John Doe"
        assert lead.mortgage_amount == "$100,000"


class TestValidation:
    """Tests for CSV row validation."""

    def test_validate_row_all_required_fields_present(self):
        """Valid row passes validation (Source is optional)"""
        from scripts.ingest_csv_leads import validate_row

        row = {
            "State": "LA",
            "Call In Date": "06-09-2025 15:55:13",
        }

        is_valid, error = validate_row(row, 2)

        assert is_valid is True
        assert error is None

    def test_validate_row_with_source(self):
        """Valid row with Source also passes validation"""
        from scripts.ingest_csv_leads import validate_row

        row = {
            "State": "LA",
            "Source": "CALL",
            "Call In Date": "06-09-2025 15:55:13",
        }

        is_valid, error = validate_row(row, 2)

        assert is_valid is True
        assert error is None

    def test_validate_row_missing_state(self):
        """Missing State fails validation"""
        from scripts.ingest_csv_leads import validate_row

        row = {
            "State": "",
            "Source": "CALL",
            "Call In Date": "06-09-2025 15:55:13",
        }

        is_valid, error = validate_row(row, 2)

        assert is_valid is False
        assert "State" in error

    def test_validate_row_empty_source_is_valid(self):
        """Empty Source is valid (classifies as Silver, but passes validation)"""
        from scripts.ingest_csv_leads import validate_row

        row = {
            "State": "LA",
            "Source": "",
            "Call In Date": "06-09-2025 15:55:13",
        }

        is_valid, error = validate_row(row, 2)

        assert is_valid is True
        assert error is None

    def test_validate_row_missing_call_in_date(self):
        """Missing Call In Date fails validation"""
        from scripts.ingest_csv_leads import validate_row

        row = {
            "State": "LA",
            "Source": "CALL",
            "Call In Date": "",
        }

        is_valid, error = validate_row(row, 2)

        assert is_valid is False
        assert "Call In Date" in error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
