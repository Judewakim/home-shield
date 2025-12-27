-- ============================================================================
-- Seed Pricing Data
-- ============================================================================
--
-- Initial pricing rules for Gold and Silver leads across all age buckets.
-- These are default/placeholder prices - adjust based on your business model.
--
-- Pricing Strategy:
-- - Gold leads are more expensive than Silver (all 6 qualification fields present)
-- - Newer leads (MONTH_3_TO_5) are more expensive than older leads
-- - Prices decrease as leads age
--
-- Run this AFTER running schema.sql to populate initial pricing.
-- ============================================================================

-- Clear existing pricing (if re-running)
DELETE FROM pricing_rules;

-- ============================================================================
-- GOLD LEAD PRICING
-- ============================================================================

-- Gold - MONTH_3_TO_5 (Most valuable: newest + complete data)
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Gold',
    'MONTH_3_TO_5',
    10.00,  --$10 per lead
    'USD',
    'Premium pricing for Gold leads aged 3-5 months',
    'system'
);

-- Gold - MONTH_6_TO_8
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Gold',
    'MONTH_6_TO_8',
    8.00,  -- $8 per lead
    'USD',
    'Gold leads aged 6-8 months',
    'system'
);

-- Gold - MONTH_9_TO_11
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Gold',
    'MONTH_9_TO_11',
    6.00,  -- $6 per lead
    'USD',
    'Gold leads aged 9-11 months',
    'system'
);

-- Gold - MONTH_12_TO_23
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Gold',
    'MONTH_12_TO_23',
    5.00,  -- $5 per lead
    'USD',
    'Gold leads aged 12-23 months (1-2 years)',
    'system'
);

-- Gold - MONTH_24_PLUS (Oldest)
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Gold',
    'MONTH_24_PLUS',
    4.00,  -- $4 per lead
    'USD',
    'Gold leads aged 24+ months (2+ years)',
    'system'
);

-- ============================================================================
-- SILVER LEAD PRICING
-- ============================================================================

-- Silver - MONTH_3_TO_5
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Silver',
    'MONTH_3_TO_5',
    7.50,  -- $7.50 per lead
    'USD',
    'Silver leads aged 3-5 months (missing some qualification data)',
    'system'
);

-- Silver - MONTH_6_TO_8
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Silver',
    'MONTH_6_TO_8',
    6.00,  -- $6 per lead
    'USD',
    'Silver leads aged 6-8 months',
    'system'
);

-- Silver - MONTH_9_TO_11
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Silver',
    'MONTH_9_TO_11',
    4.50,  -- $4.50 per lead
    'USD',
    'Silver leads aged 9-11 months',
    'system'
);

-- Silver - MONTH_12_TO_23
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Silver',
    'MONTH_12_TO_23',
    4.00,  -- $4 per lead
    'USD',
    'Silver leads aged 12-23 months (1-2 years)',
    'system'
);

-- Silver - MONTH_24_PLUS (Oldest, least valuable)
INSERT INTO pricing_rules (classification, age_bucket, base_price, currency, notes, created_by)
VALUES (
    'Silver',
    'MONTH_24_PLUS',
    3.00,  -- $3 per lead
    'USD',
    'Silver leads aged 24+ months (2+ years)',
    'system'
);

-- ============================================================================
-- VERIFY PRICING
-- ============================================================================

-- Display all pricing rules
SELECT
    classification,
    age_bucket,
    base_price,
    currency,
    notes
FROM pricing_rules
ORDER BY
    classification DESC,  -- Gold first
    CASE age_bucket
        WHEN 'MONTH_3_TO_5' THEN 1
        WHEN 'MONTH_6_TO_8' THEN 2
        WHEN 'MONTH_9_TO_11' THEN 3
        WHEN 'MONTH_12_TO_23' THEN 4
        WHEN 'MONTH_24_PLUS' THEN 5
    END;

-- ============================================================================
-- PRICING SUMMARY
-- ============================================================================
--
-- Gold Lead Pricing:
--   MONTH_3_TO_5:   $10.00 (newest, most valuable)
--   MONTH_6_TO_8:   $8.00
--   MONTH_9_TO_11:  $6.00
--   MONTH_12_TO_23: $5.00
--   MONTH_24_PLUS:  $4.00 (oldest)
--
-- Silver Lead Pricing (50% of Gold):
--   MONTH_3_TO_5:   $7.50
--   MONTH_6_TO_8:   $6.00
--   MONTH_9_TO_11:  $4.50
--   MONTH_12_TO_23: $4.00
--   MONTH_24_PLUS:  $3.00
--
-- To adjust pricing:
-- 1. Update base_price in pricing_rules table
-- 2. Set effective_to = NOW() on old price
-- 3. Insert new price with effective_from = NOW()
-- 4. Historical pricing is preserved for revenue reporting
--
-- ============================================================================
