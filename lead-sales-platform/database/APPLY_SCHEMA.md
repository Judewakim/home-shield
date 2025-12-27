# Apply Complete Database Schema to Supabase

## ⚠️ IMPORTANT: This will DROP existing tables

The schema includes `DROP TABLE IF EXISTS` commands that will **delete all existing data** in:
- `leads` (3,838 Louisiana leads)
- `inventory`
- `sales`
- `clients`
- `pricing_rules`

**You will need to re-ingest leads after applying this schema.**

---

## Step-by-Step Instructions

### Step 1: Apply Main Schema

1. **Open Supabase Dashboard**
   - Go to https://supabase.com/dashboard
   - Select your project

2. **Open SQL Editor**
   - Click "SQL Editor" in the left sidebar
   - Click "New Query"

3. **Copy and Paste `schema.sql`**
   - Open `lead-sales-platform/database/schema.sql`
   - Copy **ALL** contents (375 lines)
   - Paste into Supabase SQL Editor

4. **Run the Schema**
   - Click **"Run"** button
   - Wait for confirmation (should complete in ~2 seconds)

**Expected Result:**
```
Success. No rows returned
```

### Step 2: Apply Pricing Seed Data

1. **Open New Query in SQL Editor**
   - Click "New Query" again

2. **Copy and Paste `seed_pricing.sql`**
   - Open `lead-sales-platform/database/seed_pricing.sql`
   - Copy **ALL** contents
   - Paste into Supabase SQL Editor

3. **Run the Seed Data**
   - Click **"Run"** button
   - You should see a results table with 10 pricing rules

**Expected Result:**
```
classification | age_bucket      | base_price | currency | notes
---------------|----------------|------------|----------|------
Gold           | MONTH_3_TO_5   | 150.00     | USD      | Premium pricing...
Gold           | MONTH_6_TO_8   | 120.00     | USD      | Gold leads aged...
... (10 rows total)
```

### Step 3: Verify Schema

1. **Go to Table Editor**
   - Click "Table Editor" in the left sidebar

2. **Verify Tables Exist:**
   - ✅ `leads`
   - ✅ `clients`
   - ✅ `inventory`
   - ✅ `sales`
   - ✅ `pricing_rules`

3. **Check `leads` Table Structure**
   - Click on `leads` table
   - You should see **28 columns**:
     - lead_id, created_at_utc, classification, source, state
     - mortgage_id, campaign_id, type, status
     - full_name, first_name, last_name, co_borrower_name
     - address, city, county, zip
     - mortgage_amount, lender, sale_date
     - agent_id, call_in_phone_number, borrower_phone
     - borrower_age, borrower_medical_issues, borrower_tobacco_use, co_borrower
     - call_in_date, created_at

4. **Verify Function Exists**
   - Go to "Database" → "Functions"
   - You should see: `execute_sale_atomic`

---

## Step 4: Re-ingest Louisiana Leads

Now that the schema is applied, re-ingest your leads:

```bash
cd lead-sales-platform
python scripts/ingest_csv_leads.py "c:\Users\wjude\Downloads\Jude Steve Collab 12.16.25 - Louisiana Leads.csv"
```

**Expected Output:**
```
Starting CSV ingestion...
...
============================================================
INGESTION SUMMARY
============================================================
Total Rows:       3838
Successful:       3838
Failed:           0
Skipped:          0

Gold Leads:       1872
Silver Leads:     1966
============================================================
```

---

## Verification Queries

### Query 1: Check Leads Count
```sql
SELECT COUNT(*) as total_leads FROM leads;
-- Expected: 3838
```

### Query 2: Check Classification Distribution
```sql
SELECT classification, COUNT(*) as count
FROM leads
GROUP BY classification;

-- Expected:
-- Gold: 1872
-- Silver: 1966
```

### Query 3: Check Pricing Rules
```sql
SELECT classification, age_bucket, base_price
FROM pricing_rules
ORDER BY classification DESC, base_price DESC;

-- Expected: 10 rows (5 Gold + 5 Silver)
```

### Query 4: Check Inventory (should be empty initially)
```sql
SELECT COUNT(*) FROM inventory;
-- Expected: 0 (inventory generation script hasn't run yet)
```

### Query 5: Test Atomic Sale Function
```sql
-- This will fail because no inventory exists yet (expected)
SELECT execute_sale_atomic(
    '00000000-0000-0000-0000-000000000000'::UUID,  -- fake lead_id
    'MONTH_3_TO_5',
    '00000000-0000-0000-0000-000000000000'::UUID,  -- fake client_id
    NOW(),
    150.00
);

-- Expected error: INVENTORY_NOT_FOUND
```

---

## Schema Summary

### Tables Created

1. **`leads`** (3,838 records after ingestion)
   - Lead records with all CSV columns
   - Indexes: classification, state, county, created_at_utc

2. **`clients`** (empty - will be populated via API registration)
   - Buyer accounts with OAuth2/JWT support
   - Supports: Google, Microsoft, GitHub, local auth
   - Fields: email, auth_provider, password_hash, refresh_token

3. **`inventory`** (empty - will be populated by generation script)
   - Tracks sellable eligibility per (lead_id, age_bucket)
   - Unique constraint prevents selling same lead twice in same bucket

4. **`sales`** (empty - will be populated by purchases)
   - Immutable sale records
   - Tracks: client_id, purchase_price, payment_status

5. **`pricing_rules`** (10 records after seed data)
   - Configurable pricing per (classification, age_bucket)
   - Historical pricing tracking

### Functions Created

1. **`execute_sale_atomic()`**
   - Atomic purchase with race condition prevention
   - Verifies client status
   - Locks inventory row
   - Creates sale record
   - Returns JSON result

---

## Troubleshooting

### Error: "relation does not exist"
**Solution:** Make sure you ran `schema.sql` first before `seed_pricing.sql`

### Error: "column does not exist"
**Solution:** Drop all tables and re-run `schema.sql`:
```sql
DROP TABLE IF EXISTS sales CASCADE;
DROP TABLE IF EXISTS inventory CASCADE;
DROP TABLE IF EXISTS pricing_rules CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS leads CASCADE;
```

### Error: "permission denied"
**Solution:** Ensure you're running queries as the database owner in Supabase

### No pricing rules after seed
**Solution:** Re-run `seed_pricing.sql` - the DELETE at the top clears existing data first

---

## Next Steps After Schema Applied

1. ✅ Schema applied successfully
2. ✅ Leads re-ingested (3,838 records)
3. ✅ Pricing rules seeded (10 records)
4. ⬜ Generate inventory records (Week 2)
5. ⬜ Build inventory query API (Week 2)
6. ⬜ Implement sales engine (Week 3)
7. ⬜ Add client authentication (Week 3)

---

**Status:** Ready to apply
**Estimated Time:** 5 minutes
**Risk Level:** Low (can re-ingest leads if needed)
