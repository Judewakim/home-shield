"""
CSV export service for purchased leads.

Generates CSV files containing full lead details for purchased leads,
including contact information, address, classification, and purchase details.

Security:
- Authorization: Verifies client owns all sales before export
- CSV Injection Prevention: Sanitizes all fields to prevent formula execution
- Security Logging: Logs when dangerous characters are stripped
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import StringIO
from typing import List
from uuid import UUID

from domain.age_bucket import AgeBucket
from domain.lead import LeadClassification
from repositories.lead_repository import get_lead_by_id
from repositories.sale_repository import get_sale_by_id

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when authorization check fails (client doesn't own sales)."""
    pass


def sanitize_csv_field(value: str | None, field_name: str = "unknown") -> str:
    """
    Sanitize field to prevent CSV injection attacks with security logging.

    Strips leading characters that can trigger formula execution in Excel/Sheets:
    =, +, -, @, tab, carriage return

    If dangerous characters are found and stripped, a warning is logged for
    security monitoring. This allows detection of both accidental issues and
    potential injection attempts.

    Args:
        value: Field value to sanitize
        field_name: Name of the field being sanitized (for logging)

    Returns:
        Sanitized string safe for CSV export

    Example:
        sanitize_csv_field("=1+1", "full_name")
        # Returns "1+1" and logs warning about stripped "=" character

        sanitize_csv_field("@SUM(1+1)", "phone")
        # Returns "SUM(1+1)" and logs warning about stripped "@" character

        sanitize_csv_field("Normal Name", "full_name")
        # Returns "Normal Name" (unchanged, no logging)
    """
    if value is None or value == "":
        return ""

    text = str(value).strip()
    original_text = text
    dangerous_chars = {'=', '+', '-', '@', '\t', '\r'}

    # Strip dangerous leading characters
    stripped_chars = []
    while text and text[0] in dangerous_chars:
        stripped_chars.append(text[0])
        text = text[1:]

    # Log warning if we modified the data (potential CSV injection attempt)
    if stripped_chars:
        logger.warning(
            f"CSV injection character(s) stripped from field '{field_name}'",
            extra={
                "field_name": field_name,
                "stripped_characters": "".join(stripped_chars),
                "original_value": original_text[:100],  # First 100 chars
                "sanitized_value": text[:100],
                "modification_type": "csv_injection_prevention"
            }
        )

    return text


@dataclass(frozen=True, slots=True)
class PurchasedLeadExport:
    """
    Combined lead + purchase information for CSV export.
    """
    # Sale information
    sale_id: UUID
    purchase_price: Decimal
    currency: str
    purchased_at: datetime
    age_bucket: AgeBucket

    # Lead classification
    classification: LeadClassification

    # Contact information
    full_name: str
    first_name: str
    last_name: str
    borrower_phone: str
    call_in_phone_number: str

    # Address
    address: str
    city: str
    county: str
    state: str
    zip: str

    # Additional lead details
    mortgage_id: str
    mortgage_amount: str
    lender: str
    sale_date: str
    call_in_date: str

    # Co-borrower info
    co_borrower_name: str

    # Qualification details
    borrower_age: str
    borrower_medical_issues: str
    borrower_tobacco_use: str
    co_borrower: str

    # Metadata
    source: str
    campaign_id: str
    type: str
    status: str
    agent_id: str


def _fetch_purchased_lead_data(sale_id: UUID) -> PurchasedLeadExport:
    """
    Fetch combined sale + lead data for a single sale.

    Args:
        sale_id: Sale record ID

    Returns:
        PurchasedLeadExport with all lead and purchase details

    Raises:
        RuntimeError: If sale or lead not found
    """
    # Fetch sale record
    sale = get_sale_by_id(sale_id)
    if sale is None:
        raise RuntimeError(f"Sale not found: {sale_id}")

    # Fetch lead record
    lead = get_lead_by_id(sale.lead_id)
    if lead is None:
        raise RuntimeError(f"Lead not found for sale {sale_id}: {sale.lead_id}")

    # Combine into export record with CSV injection sanitization
    return PurchasedLeadExport(
        # Sale information
        sale_id=sale.sale_id,
        purchase_price=sale.purchase_price,
        currency=sale.currency,
        purchased_at=sale.sold_at,
        age_bucket=sale.age_bucket,

        # Lead classification
        classification=lead.classification,

        # Contact information (sanitized with field names for logging)
        full_name=sanitize_csv_field(lead.full_name, "full_name"),
        first_name=sanitize_csv_field(lead.first_name, "first_name"),
        last_name=sanitize_csv_field(lead.last_name, "last_name"),
        borrower_phone=sanitize_csv_field(lead.borrower_phone, "borrower_phone"),
        call_in_phone_number=sanitize_csv_field(lead.call_in_phone_number, "call_in_phone_number"),

        # Address (sanitized with field names for logging)
        address=sanitize_csv_field(lead.address, "address"),
        city=sanitize_csv_field(lead.city, "city"),
        county=sanitize_csv_field(lead.county, "county"),
        state=sanitize_csv_field(lead.state, "state"),
        zip=sanitize_csv_field(lead.zip, "zip"),

        # Additional lead details (sanitized with field names for logging)
        mortgage_id=sanitize_csv_field(lead.mortgage_id, "mortgage_id"),
        mortgage_amount=sanitize_csv_field(lead.mortgage_amount, "mortgage_amount"),
        lender=sanitize_csv_field(lead.lender, "lender"),
        sale_date=sanitize_csv_field(lead.sale_date, "sale_date"),
        call_in_date=sanitize_csv_field(lead.call_in_date, "call_in_date"),

        # Co-borrower info (sanitized with field names for logging)
        co_borrower_name=sanitize_csv_field(lead.co_borrower_name, "co_borrower_name"),

        # Qualification details (sanitized with field names for logging)
        borrower_age=sanitize_csv_field(lead.borrower_age, "borrower_age"),
        borrower_medical_issues=sanitize_csv_field(lead.borrower_medical_issues, "borrower_medical_issues"),
        borrower_tobacco_use=sanitize_csv_field(lead.borrower_tobacco_use, "borrower_tobacco_use"),
        co_borrower=sanitize_csv_field(lead.co_borrower, "co_borrower"),

        # Metadata (sanitized with field names for logging)
        source=sanitize_csv_field(lead.source, "source"),
        campaign_id=sanitize_csv_field(lead.campaign_id, "campaign_id"),
        type=sanitize_csv_field(lead.type, "type"),
        status=sanitize_csv_field(lead.status, "status"),
        agent_id=sanitize_csv_field(lead.agent_id, "agent_id"),
    )


def generate_csv_for_sales(sale_ids: List[UUID], client_id: UUID) -> str:
    """
    Generate a CSV file containing full lead details for purchased leads.

    Security:
    - Verifies that ALL sales belong to the requesting client (authorization)
    - Sanitizes all fields to prevent CSV injection attacks

    Args:
        sale_ids: List of sale IDs to include in the export
        client_id: Client requesting the export (for authorization)

    Returns:
        CSV content as a string

    Raises:
        ValueError: If sale_ids is empty
        SecurityError: If any sale doesn't belong to the requesting client
        RuntimeError: If any sale or lead is not found

    Example:
        csv_content = generate_csv_for_sales(
            sale_ids=[sale_id_1, sale_id_2, ...],
            client_id=current_client.client_id
        )

        # Save to file
        with open("purchased_leads.csv", "w") as f:
            f.write(csv_content)

        # Or return in API response
        return Response(content=csv_content, media_type="text/csv")
    """
    if not sale_ids:
        raise ValueError("sale_ids cannot be empty")

    # AUTHORIZATION: Verify ALL sales belong to requesting client
    for sale_id in sale_ids:
        sale = get_sale_by_id(sale_id)
        if sale is None:
            raise RuntimeError(f"Sale not found: {sale_id}")

        if sale.client_id != client_id:
            raise SecurityError(
                f"Authorization failed: Sale {sale_id} does not belong to client {client_id}"
            )

    # Fetch all purchased lead data (already sanitized in _fetch_purchased_lead_data)
    purchased_leads = [_fetch_purchased_lead_data(sale_id) for sale_id in sale_ids]

    # Generate CSV
    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Sale ID",
        "Purchase Price",
        "Currency",
        "Purchased At",
        "Age Bucket",
        "Classification",

        # Contact
        "Full Name",
        "First Name",
        "Last Name",
        "Borrower Phone",
        "Call-In Phone Number",

        # Address
        "Address",
        "City",
        "County",
        "State",
        "ZIP",

        # Lead Details
        "Mortgage ID",
        "Mortgage Amount",
        "Lender",
        "Sale Date",
        "Call-In Date",

        # Co-borrower
        "Co-Borrower Name",
        "Co-Borrower?",

        # Qualification
        "Borrower Age",
        "Medical Issues",
        "Tobacco Use",

        # Metadata
        "Source",
        "Campaign ID",
        "Type",
        "Status",
        "Agent ID",
    ])

    # Write data rows
    for lead in purchased_leads:
        writer.writerow([
            str(lead.sale_id),
            str(lead.purchase_price),
            lead.currency,
            lead.purchased_at.isoformat(),
            lead.age_bucket.value,
            lead.classification.value,

            # Contact
            lead.full_name,
            lead.first_name,
            lead.last_name,
            lead.borrower_phone,
            lead.call_in_phone_number,

            # Address
            lead.address,
            lead.city,
            lead.county,
            lead.state,
            lead.zip,

            # Lead Details
            lead.mortgage_id,
            lead.mortgage_amount,
            lead.lender,
            lead.sale_date,
            lead.call_in_date,

            # Co-borrower
            lead.co_borrower_name,
            lead.co_borrower,

            # Qualification
            lead.borrower_age,
            lead.borrower_medical_issues,
            lead.borrower_tobacco_use,

            # Metadata
            lead.source,
            lead.campaign_id,
            lead.type,
            lead.status,
            lead.agent_id,
        ])

    return output.getvalue()


__all__ = [
    "PurchasedLeadExport",
    "generate_csv_for_sales",
    "SecurityError",
    "sanitize_csv_field",
]
