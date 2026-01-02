"""Test raw database query"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from repositories.client import supabase

# Raw query for Gold 12-23 month leads
response = (
    supabase.table("inventory")
    .select("*, leads!inner(classification)")
    .is_("sold_at_utc", "null")
    .eq("age_bucket", "MONTH_12_TO_23")
    .eq("leads.classification", "Gold")
    .limit(10)
    .execute()
)

print(f"Raw query returned: {len(response.data)} items")
for i, row in enumerate(response.data, 1):
    print(f"{i}. {row['inventory_id'][:8]}... - {row['age_bucket']} - {row['leads']['classification']}")

# Try without the inner join filter
print("\n--- Without classification filter ---")
response2 = (
    supabase.table("inventory")
    .select("*")
    .is_("sold_at_utc", "null")
    .eq("age_bucket", "MONTH_12_TO_23")
    .limit(10)
    .execute()
)

print(f"Query without classification returned: {len(response2.data)} items")
