# Behavioral Contract — Lead Classification & Inventory

This document is the authoritative behavioral contract for the lead sales platform.

It defines exactly how:
- leads are classified (Gold vs Silver)
- lead age is calculated
- age buckets are assigned
- inventory eligibility is determined
- resale across age buckets is enforced

All application code MUST conform to this document.

Any change in behavior requires:
1. Updating this document
2. Versioning the change
3. Explicit review and approval

Implementation code is not allowed to invent, simplify, or bypass rules defined here.

========================================
SECTION 1 — CORE DEFINITIONS
========================================

Lead:
- A Lead represents a single consumer inquiry.
- A Lead is immutable after ingestion except for system-generated metadata.
- A Lead is uniquely identified by lead_id.

Lead Attributes (minimum required):
- lead_id (UUID)
- source
- state
- raw_payload
- classification (Gold | Silver)
- created_at_utc (UTC timestamp, authoritative)

Age:
- Lead age is calculated in whole calendar days.
- Age is defined as:
  age_days = floor((as_of_utc - created_at_utc) / 24 hours)
- Partial days are not rounded up.

Month Definition (Explicit):
- “Months” are defined as fixed 30-day intervals.
- No calendar month logic
- No partial month rounding
- No date arithmetic beyond day-diff

Formal Definition:
  age_months = floor(age_days / 30)

Age Bucket:
- An Age Bucket represents a discrete resale eligibility window.
- Buckets are defined strictly as:
    MONTH_3_TO_5:
    age_days ∈ [  90, 179 ]

    MONTH_6_TO_8:
    age_days ∈ [ 180, 269 ]

    MONTH_9_TO_11:
    age_days ∈ [ 270, 359 ]

    MONTH_12_TO_23:
    age_days ∈ [ 360, 719 ]

    MONTH_24_PLUS:
    age_days ≥ 720

Leads Younger Than 90 Days:
- Leads with age_days < 90 do not fall into any Age Bucket and are not sellable.

========================================
SECTION 2 — LEAD CLASSIFICATION RULES
========================================

Classification Process:
- Classification occurs exactly once at ingestion time.
- Classification is deterministic and rule-based.
- Classification must not change after ingestion.

Gold Lead:
- A Lead is classified as Gold if it satisfies ALL required Gold criteria.
- Gold criteria are defined externally and injected at runtime (rules engine, config, or static mapping).
- If Gold criteria evaluation fails, the Lead is NOT Gold.

Silver Lead:
- A Lead is classified as Silver if it does not meet Gold criteria.

Classification Invariants:
- Every Lead must be classified as exactly one of: Gold or Silver.
- Classification does NOT affect inventory lifecycle or resale eligibility.
- Classification affects only data completeness, pricing, and buyer segmentation.

========================================
SECTION 3 — INVENTORY MODEL
========================================

Inventory Record:
- Inventory represents sellable eligibility for a Lead within an Age Bucket.
- Inventory is derived, not manually created.

Inventory Attributes:
- inventory_id
- lead_id
- age_bucket
- is_available (boolean)
- created_at (UTC timestamp)
- sold_at (UTC timestamp, nullable)

Uniqueness Constraint:
- There must never exist more than one Inventory record for the same:
  (lead_id, age_bucket)

========================================
SECTION 4 — INVENTORY ELIGIBILITY RULES
========================================

Eligibility Evaluation:
- Inventory eligibility is determined solely by:
  - Lead age
  - Prior sales history
- Lead classification (Gold or Silver) does NOT alter eligibility rules.

Universal Eligibility Rule:
- A Lead is eligible for sale in an Age Bucket if:
  - The Lead's age falls within the bucket range
  - No prior sale exists for (lead_id, age_bucket)

Bucket Eligibility (applies to ALL leads):
- MONTH_3_TO_5: eligible
- MONTH_6_TO_8: eligible
- MONTH_9_TO_11: eligible
- MONTH_12_TO_23: eligible
- MONTH_24_PLUS: eligible

========================================
SECTION 5 — SALE CONSTRAINTS
========================================

Single-Sale-Per-Bucket Rule:
- A Lead may be sold at most once per Age Bucket.
- Once sold in a bucket:
  - That (lead_id, age_bucket) is permanently closed
  - Future buckets remain eligible

Cross-Bucket Resale:
- Selling a Lead in one Age Bucket has NO effect on eligibility in future buckets.
- This applies equally to Gold and Silver Leads.

========================================
SECTION 6 — INVENTORY GENERATION LOGIC
========================================

Inventory Creation:
- Inventory records may be generated lazily or eagerly.
- Inventory MUST be created when:
  - The Lead enters a new Age Bucket
  - No Inventory record exists for (lead_id, age_bucket)

Inventory Availability:
- is_available is TRUE if:
  - sold_at is NULL
- Availability is independent of Lead classification.

========================================
SECTION 7 — TIME & REEVALUATION
========================================

Reevaluation Rules:
- Eligibility is reevaluated automatically when a Lead transitions into a new Age Bucket.
- Transition into a new bucket restores eligibility exactly once.
- Historical Inventory records are immutable.

========================================
SECTION 9 — NON-GOALS (EXPLICITLY OUT OF SCOPE)
========================================

The following are NOT governed by this specification:
- Pricing differences between Gold and Silver
- Buyer access rules
- Marketing language
- Bundle construction logic

These concerns must reference classification but must not alter inventory rules.