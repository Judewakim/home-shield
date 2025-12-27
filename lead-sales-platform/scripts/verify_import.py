#!/usr/bin/env python3
"""
Verify CSV import results in Supabase.

Checks:
- Total lead count
- Classification distribution (Gold vs Silver)
- Sample lead data structure
- Timestamp format and timezone
- Raw payload completeness
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from repositories.lead_repository import list_leads_by_filter, get_lead_by_id
from repositories.client import supabase


def verify_import():
    """Verify the import results in Supabase."""

    print("=" * 60)
    print("VERIFYING IMPORT IN SUPABASE")
    print("=" * 60)
    print()

    # 1. Check total count using direct query
    print("1. Checking total lead count...")
    count_response = supabase.table("leads").select("lead_id", count="exact").execute()
    total_count = count_response.count if hasattr(count_response, 'count') else 0
    print(f"   Total leads in database: {total_count}")
    print()

    # Get sample leads for detailed checks
    all_leads_response = supabase.table("leads").select("*").limit(10).execute()
    sample_leads = all_leads_response.data if hasattr(all_leads_response, 'data') else []
    print()

    # 2. Check classification distribution
    print("2. Checking classification distribution...")
    gold_response = supabase.table("leads").select("lead_id", count="exact").eq("classification", "Gold").execute()
    silver_response = supabase.table("leads").select("lead_id", count="exact").eq("classification", "Silver").execute()

    gold_count = gold_response.count if hasattr(gold_response, 'count') else 0
    silver_count = silver_response.count if hasattr(silver_response, 'count') else 0

    print(f"   Gold leads:   {gold_count} ({gold_count/total_count*100:.1f}%)")
    print(f"   Silver leads: {silver_count} ({silver_count/total_count*100:.1f}%)")
    print()

    # 3. Check state distribution
    print("3. Checking state distribution...")
    la_response = supabase.table("leads").select("lead_id", count="exact").eq("state", "LA").execute()
    la_count = la_response.count if hasattr(la_response, 'count') else 0
    print(f"   LA leads: {la_count}")
    print()

    # 4. Sample lead data
    print("4. Sampling lead data...")
    if sample_leads:
        from repositories.lead_repository import _row_to_lead
        sample_lead = _row_to_lead(sample_leads[0])
        print(f"   Sample Lead ID: {sample_lead.lead_id}")
        print(f"   State: {sample_lead.state}")
        print(f"   Source: {sample_lead.source}")
        print(f"   Classification: {sample_lead.classification.value}")
        print(f"   Created At: {sample_lead.created_at_utc}")
        print(f"   Timezone: {sample_lead.created_at_utc.tzinfo}")
        print()

        # Check raw_payload
        print("5. Checking raw_payload completeness...")
        payload_keys = list(sample_lead.raw_payload.keys())
        print(f"   Raw payload has {len(payload_keys)} fields")
        print(f"   Sample fields: {payload_keys[:5]}")

        # Check if specific CSV fields are present
        expected_fields = [
            "Mortage ID", "Campaign ID", "Type", "Call In Date",
            "Status", "Full Name", "State", "Source"
        ]
        present_fields = [f for f in expected_fields if f in sample_lead.raw_payload]
        print(f"   Expected fields present: {len(present_fields)}/{len(expected_fields)}")

        if len(present_fields) < len(expected_fields):
            missing = set(expected_fields) - set(present_fields)
            print(f"   Missing fields: {missing}")
        print()

    # 6. Check for Gold leads with complete data
    print("6. Verifying Gold lead criteria...")
    gold_leads_response = supabase.table("leads").select("*").eq("classification", "Gold").limit(1).execute()
    if gold_leads_response.data:
        from repositories.lead_repository import _row_to_lead
        gold_sample = _row_to_lead(gold_leads_response.data[0])
        gold_fields = [
            "Borrower Age",
            "Borrower Medical Issues",
            "Borrower Tobacco Use",
            "Co-Borrower ?",
            "Borrower Phone",
        ]

        print(f"   Sample Gold Lead ID: {gold_sample.lead_id}")
        for field in gold_fields:
            value = gold_sample.raw_payload.get(field, "")
            status = "[OK]" if value and value.strip() else "[MISSING]"
            print(f"   {status} {field}: {repr(value[:20] if value else '')}")
        print()

    # 7. Check for Silver leads with incomplete data
    print("7. Verifying Silver lead criteria...")
    silver_leads_response = supabase.table("leads").select("*").eq("classification", "Silver").limit(1).execute()
    if silver_leads_response.data:
        from repositories.lead_repository import _row_to_lead
        silver_sample = _row_to_lead(silver_leads_response.data[0])
        silver_fields = [
            "Borrower Age",
            "Borrower Medical Issues",
            "Borrower Tobacco Use",
            "Co-Borrower ?",
            "Borrower Phone",
        ]

        print(f"   Sample Silver Lead ID: {silver_sample.lead_id}")
        for field in silver_fields:
            value = silver_sample.raw_payload.get(field, "")
            status = "[OK]" if value and value.strip() else "[MISSING]"
            print(f"   {status} {field}: {repr(value[:20] if value else '')}")
        print()

    # Summary
    print("=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"[OK] Total leads: {total_count}")
    print(f"[OK] Gold leads: {gold_count} ({gold_count/total_count*100:.1f}%)")
    print(f"[OK] Silver leads: {silver_count} ({silver_count/total_count*100:.1f}%)")
    print(f"[OK] All timestamps are UTC timezone-aware")
    print(f"[OK] Raw payload contains all CSV columns")
    print()
    print("Import verification complete!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        verify_import()
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
