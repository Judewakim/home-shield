"""
Database validation tests.

This module tests the Supabase connection and verifies that:
1. Connection credentials work
2. Required tables exist
3. Tables have expected columns
4. Basic CRUD operations work

Run this first to validate database setup before running other tests.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from dotenv import load_dotenv

# Load .env file before anything else
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Add parent directory to path to import repositories
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_environment_variables_set() -> None:
    """Verify required environment variables are set."""

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    assert supabase_url is not None, (
        "SUPABASE_URL environment variable is not set. "
        "Set it to your Supabase project URL."
    )
    assert supabase_key is not None, (
        "SUPABASE_KEY environment variable is not set. "
        "Set it to your Supabase API key."
    )
    assert supabase_url.startswith("https://"), "SUPABASE_URL should start with https://"

    print(f"\n[OK] Environment variables set")
    print(f"  SUPABASE_URL: {supabase_url[:30]}...")


def test_supabase_client_initialization() -> None:
    """Test that Supabase client can be initialized."""

    try:
        from repositories.client import supabase
        assert supabase is not None
        print("\n[OK] Supabase client initialized successfully")
    except RuntimeError as e:
        pytest.fail(f"Failed to initialize Supabase client: {e}")
    except ImportError as e:
        pytest.fail(f"Failed to import supabase module: {e}. Run: pip install supabase")


def test_supabase_connection() -> None:
    """Test basic connection to Supabase by attempting a simple query."""

    from repositories.client import supabase

    try:
        # Try to list tables or perform a simple query
        # This will fail if credentials are wrong or connection is broken
        response = supabase.table("leads").select("*").limit(1).execute()
        print("\n[OK] Successfully connected to Supabase")
        print(f"  Response type: {type(response)}")
    except Exception as e:
        pytest.fail(
            f"Failed to connect to Supabase or query 'leads' table: {e}\n"
            f"This could mean:\n"
            f"  1. Invalid credentials (check SUPABASE_URL and SUPABASE_KEY)\n"
            f"  2. Table 'leads' does not exist\n"
            f"  3. Network connectivity issue"
        )


def test_leads_table_exists() -> None:
    """Verify the 'leads' table exists and can be queried."""

    from repositories.client import supabase

    try:
        response = supabase.table("leads").select("*").limit(0).execute()
        print("\n[OK] 'leads' table exists")

        # Check if we can see the structure
        if hasattr(response, 'data'):
            print(f"  Query successful, data type: {type(response.data)}")
    except Exception as e:
        pytest.fail(
            f"'leads' table does not exist or cannot be accessed: {e}\n"
            f"You need to create this table in Supabase."
        )


def test_inventory_table_exists() -> None:
    """Verify the 'inventory' table exists and can be queried."""

    from repositories.client import supabase

    try:
        response = supabase.table("inventory").select("*").limit(0).execute()
        print("\n[OK] 'inventory' table exists")
    except Exception as e:
        pytest.fail(
            f"'inventory' table does not exist or cannot be accessed: {e}\n"
            f"You need to create this table in Supabase."
        )


def test_sales_table_exists() -> None:
    """Verify the 'sales' table exists and can be queried."""

    from repositories.client import supabase

    try:
        response = supabase.table("sales").select("*").limit(0).execute()
        print("\n[OK] 'sales' table exists")
    except Exception as e:
        pytest.fail(
            f"'sales' table does not exist or cannot be accessed: {e}\n"
            f"You need to create this table in Supabase."
        )


def test_lead_repository_basic_operations() -> None:
    """Test basic CRUD operations on leads table through repository."""

    from domain.lead import Lead, LeadClassification
    from repositories import lead_repository

    # Create a test lead
    test_lead_id = uuid4()
    test_lead = Lead(
        lead_id=test_lead_id,
        source="test-source",
        state="TX",
        raw_payload={"test": "data"},
        classification=LeadClassification.SILVER,
        created_at_utc=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )

    try:
        # Test INSERT
        lead_repository.insert_lead(test_lead)
        print(f"\n[OK] Successfully inserted test lead: {test_lead_id}")

        # Test SELECT
        retrieved = lead_repository.get_lead_by_id(test_lead_id)
        assert retrieved is not None, "Failed to retrieve inserted lead"
        assert retrieved.lead_id == test_lead_id
        assert retrieved.classification == LeadClassification.SILVER
        print(f"[OK] Successfully retrieved test lead")

        # Cleanup - delete test lead
        from repositories.client import supabase
        supabase.table("leads").delete().eq("lead_id", str(test_lead_id)).execute()
        print(f"[OK] Successfully cleaned up test lead")

    except Exception as e:
        # Try to cleanup even if test failed
        try:
            from repositories.client import supabase
            supabase.table("leads").delete().eq("lead_id", str(test_lead_id)).execute()
        except:
            pass

        pytest.fail(
            f"Failed to perform basic lead operations: {e}\n"
            f"This could indicate:\n"
            f"  1. Table schema doesn't match expected structure\n"
            f"  2. Missing required columns\n"
            f"  3. Column type mismatches\n"
            f"  4. Constraint violations"
        )


def test_inventory_repository_basic_operations() -> None:
    """Test basic operations on inventory table through repository."""

    from domain.age_bucket import AgeBucket
    from domain.lead import Lead, LeadClassification
    from repositories import inventory_repository, lead_repository

    # Create a test lead first (inventory needs a valid lead_id)
    test_lead_id = uuid4()
    test_lead = Lead(
        lead_id=test_lead_id,
        source="test-source",
        state="CA",
        raw_payload={"test": "inventory"},
        classification=LeadClassification.GOLD,
        created_at_utc=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_created_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    try:
        # First insert the lead
        lead_repository.insert_lead(test_lead)

        # Test INSERT inventory
        inventory_repository.create_inventory_record(
            lead_id=test_lead_id,
            bucket=AgeBucket.MONTH_3_TO_5,
            created_at=test_created_at,
        )
        print(f"\n[OK] Successfully created test inventory record")

        # Test SELECT
        records = inventory_repository.get_inventory_by_lead(test_lead_id)
        assert len(records) > 0, "Failed to retrieve inserted inventory"
        assert records[0].age_bucket == AgeBucket.MONTH_3_TO_5
        print(f"[OK] Successfully retrieved test inventory record")

        # Cleanup - delete inventory first (due to foreign key)
        from repositories.client import supabase
        supabase.table("inventory").delete().eq("lead_id", str(test_lead_id)).execute()
        supabase.table("leads").delete().eq("lead_id", str(test_lead_id)).execute()
        print(f"[OK] Successfully cleaned up test inventory and lead")

    except Exception as e:
        # Try to cleanup
        try:
            from repositories.client import supabase
            supabase.table("inventory").delete().eq("lead_id", str(test_lead_id)).execute()
            supabase.table("leads").delete().eq("lead_id", str(test_lead_id)).execute()
        except:
            pass

        pytest.fail(
            f"Failed to perform basic inventory operations: {e}\n"
            f"Check 'inventory' table schema matches expected structure."
        )


def test_sale_repository_basic_operations() -> None:
    """Test basic operations on sales table through repository."""

    from domain.age_bucket import AgeBucket
    from domain.lead import Lead, LeadClassification
    from repositories import lead_repository, sale_repository

    # Create a test lead first (sales needs a valid lead_id)
    test_lead_id = uuid4()
    test_lead = Lead(
        lead_id=test_lead_id,
        source="test-source",
        state="FL",
        raw_payload={"test": "sale"},
        classification=LeadClassification.SILVER,
        created_at_utc=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_sold_at = datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc)

    try:
        # First insert the lead
        lead_repository.insert_lead(test_lead)

        # Test INSERT sale
        sale_repository.record_sale(
            lead_id=test_lead_id,
            bucket=AgeBucket.MONTH_6_TO_8,
            sold_at=test_sold_at,
        )
        print(f"\n[OK] Successfully recorded test sale")

        # Test SELECT
        sales = sale_repository.list_sales_by_lead(test_lead_id)
        assert len(sales) > 0, "Failed to retrieve inserted sale"
        assert sales[0].age_bucket == AgeBucket.MONTH_6_TO_8
        print(f"[OK] Successfully retrieved test sale record")

        # Cleanup - delete sales first, then lead
        from repositories.client import supabase
        supabase.table("sales").delete().eq("lead_id", str(test_lead_id)).execute()
        supabase.table("leads").delete().eq("lead_id", str(test_lead_id)).execute()
        print(f"[OK] Successfully cleaned up test sale and lead")

    except Exception as e:
        # Try to cleanup
        try:
            from repositories.client import supabase
            supabase.table("sales").delete().eq("lead_id", str(test_lead_id)).execute()
            supabase.table("leads").delete().eq("lead_id", str(test_lead_id)).execute()
        except:
            pass

        pytest.fail(
            f"Failed to perform basic sale operations: {e}\n"
            f"Check 'sales' table schema matches expected structure."
        )


if __name__ == "__main__":
    """Run validation tests directly with python."""
    print("=" * 60)
    print("DATABASE VALIDATION TESTS")
    print("=" * 60)

    # Run tests manually for better output
    tests = [
        ("Environment Variables", test_environment_variables_set),
        ("Supabase Client Init", test_supabase_client_initialization),
        ("Supabase Connection", test_supabase_connection),
        ("Leads Table", test_leads_table_exists),
        ("Inventory Table", test_inventory_table_exists),
        ("Sales Table", test_sales_table_exists),
        ("Lead Repository CRUD", test_lead_repository_basic_operations),
        ("Inventory Repository CRUD", test_inventory_repository_basic_operations),
        ("Sale Repository CRUD", test_sale_repository_basic_operations),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"\n[Testing] {name}...")
            test_func()
            passed += 1
            print(f"[PASS] {name}")
        except Exception as e:
            failed += 1
            print(f"[FAIL] {name}")
            print(f"  Error: {e}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
