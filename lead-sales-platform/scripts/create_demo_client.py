"""
Create demo client for testing and demos.

This script creates the hardcoded demo client used in the frontend:
- Client ID: 123e4567-e89b-12d3-a456-426614174002
- Name: Demo Client
- Email: demo@example.com
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import from repositories
sys.path.insert(0, str(Path(__file__).parent.parent))

from uuid import UUID

from repositories.client import supabase


DEMO_CLIENT_ID = UUID("123e4567-e89b-12d3-a456-426614174002")


def create_demo_client():
    """Create or update the demo client."""

    # Check if client already exists
    existing = supabase.table("clients").select("*").eq("client_id", str(DEMO_CLIENT_ID)).execute()

    if existing.data:
        print(f"Demo client already exists: {DEMO_CLIENT_ID}")
        print(f"Client data: {existing.data[0]}")
        return

    # Insert demo client with correct schema
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    client_data = {
        "client_id": str(DEMO_CLIENT_ID),
        "email": "demo@example.com",
        "status": "active",
        "company_name": "Demo Corporation",
        "contact_name": "Demo User",
        "auth_provider": "local",
        "email_verified": True,
        "created_at_utc": now,
        "updated_at_utc": now
    }

    result = supabase.table("clients").insert(client_data).execute()

    if result.data:
        print(f"[SUCCESS] Demo client created successfully!")
        print(f"  Client ID: {DEMO_CLIENT_ID}")
        print(f"  Company: Demo Corporation")
        print(f"  Email: demo@example.com")
        print(f"  Status: active")
    else:
        print(f"[ERROR] Failed to create demo client")
        print(f"  Error: {result}")


if __name__ == "__main__":
    create_demo_client()
