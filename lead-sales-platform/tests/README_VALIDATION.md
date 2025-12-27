# Database Validation Guide

This guide helps you verify that your Supabase database is properly configured and working with the Home Shield platform.

## Prerequisites

1. **Python 3.12+** installed
2. **Supabase account** with a project created
3. **Database credentials** (URL and API key)

## Setup Steps

### 1. Install Dependencies

```bash
cd lead-sales-platform
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the `lead-sales-platform` directory:

```bash
cp .env.example .env
```

Edit `.env` and add your Supabase credentials:

```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-or-service-key
```

**Where to find these values:**
- Go to your Supabase project dashboard
- Click on "Project Settings" (gear icon)
- Go to "API" section
- Copy "Project URL" → use as `SUPABASE_URL`
- Copy "anon public" key → use as `SUPABASE_KEY` (for testing, you can use service_role key for full access)

### 3. Load Environment Variables

The repository client automatically loads from `.env`, but you can also manually export:

```bash
# Windows Command Prompt
set SUPABASE_URL=https://your-project-id.supabase.co
set SUPABASE_KEY=your-key

# Windows PowerShell
$env:SUPABASE_URL="https://your-project-id.supabase.co"
$env:SUPABASE_KEY="your-key"

# Linux/Mac
export SUPABASE_URL=https://your-project-id.supabase.co
export SUPABASE_KEY=your-key
```

## Running Validation Tests

### Option 1: Run as Python Script (Recommended for first-time)

```bash
cd lead-sales-platform
python tests/test_db_validation.py
```

This will show detailed output for each test.

### Option 2: Run with pytest

```bash
cd lead-sales-platform
pytest tests/test_db_validation.py -v -s
```

The `-v` flag shows verbose output, `-s` shows print statements.

## What the Tests Check

The validation script tests in this order:

1. ✅ **Environment Variables Set** - Verifies SUPABASE_URL and SUPABASE_KEY are configured
2. ✅ **Supabase Client Initialization** - Tests that the client can be created
3. ✅ **Supabase Connection** - Attempts to connect to the database
4. ✅ **Leads Table Exists** - Checks if `leads` table exists
5. ✅ **Inventory Table Exists** - Checks if `inventory` table exists
6. ✅ **Sales Table Exists** - Checks if `sales` table exists
7. ✅ **Lead Repository CRUD** - Tests insert/select operations on leads
8. ✅ **Inventory Repository CRUD** - Tests insert/select operations on inventory
9. ✅ **Sale Repository CRUD** - Tests insert/select operations on sales

## Expected Results

### If Everything Works
You should see:
```
============================================================
DATABASE VALIDATION TESTS
============================================================
...
RESULTS: 9 passed, 0 failed
============================================================
```

### If Tables Don't Exist
You'll see errors like:
```
[FAIL] Leads Table
  Error: 'leads' table does not exist or cannot be accessed
```

**Next step:** Create the required tables in Supabase (see "Creating Database Schema" below)

### If Credentials Are Wrong
You'll see:
```
[FAIL] Supabase Connection
  Error: Failed to connect to Supabase: Invalid API key
```

**Next step:** Double-check your SUPABASE_URL and SUPABASE_KEY values

## Creating Database Schema

If tables don't exist, you need to create them in Supabase:

### Method 1: Supabase SQL Editor (Recommended)

1. Go to your Supabase project dashboard
2. Click on "SQL Editor" in the left sidebar
3. Create a new query
4. Run this SQL (based on the domain model requirements):

```sql
-- Create leads table
CREATE TABLE IF NOT EXISTS leads (
    lead_id UUID PRIMARY KEY,
    source TEXT NOT NULL,
    state TEXT NOT NULL,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    classification TEXT NOT NULL CHECK (classification IN ('Gold', 'Silver')),
    created_at_utc TIMESTAMPTZ NOT NULL,
    updated_at_utc TIMESTAMPTZ DEFAULT NOW()
);

-- Create inventory table
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    age_bucket TEXT NOT NULL CHECK (age_bucket IN ('MONTH_3_TO_5', 'MONTH_6_TO_8', 'MONTH_9_TO_11', 'MONTH_12_TO_23', 'MONTH_24_PLUS')),
    created_at_utc TIMESTAMPTZ NOT NULL,
    sold_at_utc TIMESTAMPTZ,
    updated_at_utc TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(lead_id, age_bucket)
);

-- Create sales table
CREATE TABLE IF NOT EXISTS sales (
    sale_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    age_bucket TEXT NOT NULL CHECK (age_bucket IN ('MONTH_3_TO_5', 'MONTH_6_TO_8', 'MONTH_9_TO_11', 'MONTH_12_TO_23', 'MONTH_24_PLUS')),
    sold_at_utc TIMESTAMPTZ NOT NULL,
    created_at_utc TIMESTAMPTZ DEFAULT NOW()
);

-- Create indices for performance
CREATE INDEX IF NOT EXISTS idx_inventory_lead_bucket ON inventory(lead_id, age_bucket);
CREATE INDEX IF NOT EXISTS idx_inventory_available ON inventory(lead_id) WHERE sold_at_utc IS NULL;
CREATE INDEX IF NOT EXISTS idx_sales_lead ON sales(lead_id);
CREATE INDEX IF NOT EXISTS idx_sales_bucket ON sales(age_bucket);
CREATE INDEX IF NOT EXISTS idx_leads_classification ON leads(classification);
```

5. Click "Run" to execute the SQL

### Method 2: Check Existing Tables

If you're unsure what tables exist:

```sql
-- List all tables in your database
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public';

-- Check structure of a specific table
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'leads';
```

## Troubleshooting

### Import Errors
```
ImportError: No module named 'supabase'
```
**Solution:** Run `pip install -r requirements.txt`

### Connection Timeout
```
Error: Connection timeout
```
**Solution:** Check your internet connection and verify SUPABASE_URL is correct

### Permission Denied
```
Error: permission denied for table leads
```
**Solution:** Use the `service_role` key instead of `anon` key for full access during testing

### Module Not Found: repositories
```
ModuleNotFoundError: No module named 'repositories'
```
**Solution:** Make sure you're running from the `lead-sales-platform` directory

## Next Steps After Validation

Once all tests pass:

1. ✅ Database layer is confirmed working
2. Run existing domain tests: `pytest tests/test_*.py` (excluding test_db_validation.py)
3. Start building the service layer
4. Create API endpoints
5. Add authentication/authorization

## Need Help?

- Check Supabase dashboard logs for database errors
- Review Supabase documentation: https://supabase.com/docs
- Verify your API key has the correct permissions
