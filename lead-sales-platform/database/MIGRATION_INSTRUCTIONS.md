# Database Schema Migration Instructions

## Overview
This migration updates the `leads` table to store all CSV columns as individual database columns instead of using a JSONB `raw_payload` field.

## Steps to Apply Schema

### 1. Backup Existing Data (if needed)
If you have existing data you want to preserve, export it first:
```bash
cd lead-sales-platform
python scripts/export_leads.py --output backup_leads.csv
```

### 2. Apply Schema in Supabase

1. Go to your Supabase dashboard: https://supabase.com/dashboard
2. Navigate to your project
3. Click on **SQL Editor** in the left sidebar
4. Click **New Query**
5. Copy and paste the contents of `database/schema.sql` into the editor
6. Click **Run** to execute the SQL

The schema will:
- Drop the old `leads` table structure (if using DROP TABLE)
- Create a new `leads` table with all CSV columns as individual fields
- Create indexes for common queries (classification, state, etc.)

### 3. Clear Existing Data (if needed)

If you want to start fresh (recommended after schema change):

```sql
-- Run this in Supabase SQL Editor
DELETE FROM leads;
```

Or drop and recreate:
```sql
DROP TABLE IF EXISTS leads CASCADE;
-- Then re-run the schema.sql
```

### 4. Re-ingest Data

After the schema is applied, re-ingest your leads:

```bash
cd lead-sales-platform
python scripts/ingest_csv_leads.py "path/to/leads.csv"
```

For the Louisiana leads:
```bash
python scripts/ingest_csv_leads.py "c:\Users\wjude\Downloads\Jude Steve Collab 12.16.25 - Louisiana Leads.csv"
```

### 5. Verify Schema in Supabase

After running the schema:

1. Go to **Table Editor** in Supabase
2. Select the `leads` table
3. You should now see all these columns:
   - lead_id (UUID, Primary Key)
   - created_at_utc (timestamptz)
   - classification (text)
   - source (text)
   - state (text)
   - mortgage_id (text)
   - campaign_id (text)
   - type (text)
   - status (text)
   - full_name (text)
   - first_name (text)
   - last_name (text)
   - co_borrower_name (text)
   - address (text)
   - city (text)
   - county (text)
   - zip (text)
   - mortgage_amount (text)
   - lender (text)
   - sale_date (text)
   - agent_id (text)
   - call_in_phone_number (text)
   - borrower_phone (text)
   - borrower_age (text)
   - borrower_medical_issues (text)
   - borrower_tobacco_use (text)
   - co_borrower (text)
   - call_in_date (text)
   - created_at (timestamptz)

### 6. Verify Data

Query a few records to ensure data is properly structured:

```sql
SELECT
    lead_id,
    state,
    classification,
    first_name,
    last_name,
    mortgage_amount,
    source
FROM leads
LIMIT 10;
```

All fields should now be visible as individual columns, not nested in a JSONB field!

## Troubleshooting

### Error: "column does not exist"
- Make sure you ran the full schema.sql file
- Try dropping the table and recreating it

### Data not appearing after ingestion
- Check that the CSV file path is correct
- Look for errors in the ingestion output
- Check the `ingestion_errors.json` file for validation issues

### Foreign key constraints
- If you have other tables referencing `leads`, you may need to drop those first
- Use `DROP TABLE IF EXISTS leads CASCADE;` to drop dependent objects

## Rolling Back

If you need to rollback to the old schema (with raw_payload):

1. You'll need to restore from your backup CSV
2. Checkout the previous git commit
3. Re-run the old schema and ingestion scripts

However, the new schema is recommended as it provides:
- Better query performance
- Direct column access in Supabase UI
- Easier data exports
- No need to parse JSONB in queries
