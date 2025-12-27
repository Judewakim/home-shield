"""
Lead classification logic for CSV ingestion.

Implements the Gold/Silver classification criteria as defined in:
docs/behavior/lead_classification_and_inventory.md
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path to import domain models
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.lead import LeadClassification


# Gold criteria fields - ALL must be non-empty for Gold classification
GOLD_REQUIRED_FIELDS = [
    "Source",
    "Borrower Age",
    "Borrower Medical Issues",
    "Borrower Tobacco Use",
    "Co-Borrower ?",
    "Borrower Phone",
]


def classify_lead(row: dict[str, str]) -> LeadClassification:
    """
    Classify a lead as Gold or Silver based on data completeness.

    Classification Rules:
    - Gold: ALL six qualification fields are present and non-empty
    - Silver: Any qualification field is missing or empty

    Gold Required Fields:
    1. Source
    2. Borrower Age
    3. Borrower Medical Issues
    4. Borrower Tobacco Use
    5. Co-Borrower ?
    6. Borrower Phone

    Args:
        row: Dictionary of CSV row data (column name → value)

    Returns:
        LeadClassification.GOLD if all required fields are non-empty,
        LeadClassification.SILVER otherwise.

    Examples:
        >>> classify_lead({
        ...     "Borrower Age": "36",
        ...     "Borrower Medical Issues": "No",
        ...     "Borrower Tobacco Use": "No",
        ...     "Co-Borrower ?": "No",
        ...     "Borrower Phone": "1234567890"
        ... })
        <LeadClassification.GOLD: 'Gold'>

        >>> classify_lead({
        ...     "Borrower Age": "36",
        ...     "Borrower Medical Issues": "No",
        ...     "Borrower Tobacco Use": "",  # Empty
        ...     "Co-Borrower ?": "No",
        ...     "Borrower Phone": "1234567890"
        ... })
        <LeadClassification.SILVER: 'Silver'>

        >>> classify_lead({
        ...     "Borrower Age": "",
        ...     "Borrower Medical Issues": "",
        ...     "Borrower Tobacco Use": "",
        ...     "Co-Borrower ?": "",
        ...     "Borrower Phone": ""
        ... })
        <LeadClassification.SILVER: 'Silver'>
    """
    # Check if ALL Gold required fields are present and non-empty
    all_fields_present = all(
        row.get(field, "").strip() != ""
        for field in GOLD_REQUIRED_FIELDS
    )

    if all_fields_present:
        return LeadClassification.GOLD
    else:
        return LeadClassification.SILVER


def get_classification_summary(rows: list[dict[str, str]]) -> dict[str, int]:
    """
    Get a summary of Gold vs Silver classification counts for a list of rows.

    Args:
        rows: List of CSV row dictionaries

    Returns:
        Dictionary with counts: {"Gold": count, "Silver": count, "Total": count}

    Example:
        >>> rows = [
        ...     {"Borrower Age": "36", "Borrower Medical Issues": "No", ...},
        ...     {"Borrower Age": "", "Borrower Medical Issues": "", ...},
        ... ]
        >>> get_classification_summary(rows)
        {'Gold': 1, 'Silver': 1, 'Total': 2}
    """
    gold_count = 0
    silver_count = 0

    for row in rows:
        classification = classify_lead(row)
        if classification == LeadClassification.GOLD:
            gold_count += 1
        else:
            silver_count += 1

    return {
        "Gold": gold_count,
        "Silver": silver_count,
        "Total": gold_count + silver_count,
    }


__all__ = [
    "classify_lead",
    "get_classification_summary",
    "GOLD_REQUIRED_FIELDS",
]
