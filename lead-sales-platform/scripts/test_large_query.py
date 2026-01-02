"""Test with large limit"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from repositories.client import supabase

# Query with large limit
response = (
    supabase.table("inventory")
    .select("*, leads!inner(classification)")
    .is_("sold_at_utc", "null")
    .eq("age_bucket", "MONTH_12_TO_23")
    .eq("leads.classification", "Gold")
    .limit(500)
    .execute()
)

print(f"Query with limit=500 returned: {len(response.data)} items")
print(f"First few items:")
for i, row in enumerate(response.data[:10], 1):
    print(f"{i}. {row['inventory_id'][:8]}...")
