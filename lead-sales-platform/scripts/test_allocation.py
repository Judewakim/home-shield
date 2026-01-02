"""Test inventory allocation"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.lead import LeadClassification
from domain.age_bucket import AgeBucket
from repositories.inventory_query_repository import (
    MixedInventoryRequest,
    query_mixed_inventory
)

# Test allocation
request = MixedInventoryRequest(
    classification=LeadClassification.GOLD,
    age_bucket=AgeBucket.MONTH_12_TO_23,
    quantity=5,
    states=None,
    counties=None
)

print(f"Requesting: {request.quantity} Gold 12-23 month leads")
results = query_mixed_inventory([request])
print(f"Got: {len(results)} items")

for i, item in enumerate(results, 1):
    print(f"{i}. {item.inventory_id} - {item.classification.value} {item.age_bucket.value} in {item.state}")
