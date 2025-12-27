-- ============================================================================
-- Lead Sales Platform - Complete Database Schema
-- ============================================================================
--
-- Phase 2: Inventory Query System & Sales Engine
--
-- Tables:
--   1. leads - Lead records from CSV ingestion
--   2. clients - Buyer accounts (JWT/OAuth2 authentication)
--   3. inventory - Sellable eligibility tracking per age bucket
--   4. sales - Immutable sale records
--   5. pricing_rules - Configurable pricing (Gold/Silver + age bucket)
--
-- Functions:
--   - execute_sale_atomic() - Atomic purchase with race condition prevention
--
-- ============================================================================

-- Drop existing tables in dependency order
DROP TABLE IF EXISTS sales CASCADE;
DROP TABLE IF EXISTS inventory CASCADE;
DROP TABLE IF EXISTS pricing_rules CASCADE;
DROP TABLE IF EXISTS clients CASCADE;
DROP TABLE IF EXISTS leads CASCADE;

-- ============================================================================
-- 1. LEADS TABLE
-- ============================================================================

CREATE TABLE leads (
    -- Primary identifiers
    lead_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at_utc TIMESTAMPTZ NOT NULL,

    -- Classification and core fields
    classification TEXT NOT NULL CHECK (classification IN ('Gold', 'Silver')),
    source TEXT,  -- Optional: empty = Silver classification
    state TEXT NOT NULL,

    -- Mortgage identification
    mortgage_id TEXT,
    campaign_id TEXT,
    type TEXT,
    status TEXT,

    -- Contact information
    full_name TEXT,
    first_name TEXT,
    last_name TEXT,
    co_borrower_name TEXT,

    -- Address fields
    address TEXT,
    city TEXT,
    county TEXT,
    zip TEXT,

    -- Financial information
    mortgage_amount TEXT,  -- Stored as text to preserve formatting like "$132,550"
    lender TEXT,
    sale_date TEXT,  -- Stored as text to preserve original format

    -- Agent and contact details
    agent_id TEXT,
    call_in_phone_number TEXT,
    borrower_phone TEXT,

    -- Qualification fields (for Gold/Silver classification)
    borrower_age TEXT,
    borrower_medical_issues TEXT,
    borrower_tobacco_use TEXT,
    co_borrower TEXT,  -- Maps to "Co-Borrower ?" column

    -- Timestamps for record management
    call_in_date TEXT,  -- Original timestamp string from CSV

    -- Indexes for common queries
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_leads_classification ON leads(classification);
CREATE INDEX IF NOT EXISTS idx_leads_state ON leads(state);
CREATE INDEX IF NOT EXISTS idx_leads_county ON leads(county);  -- NEW: for county filtering
CREATE INDEX IF NOT EXISTS idx_leads_created_at_utc ON leads(created_at_utc);
CREATE INDEX IF NOT EXISTS idx_leads_source ON leads(source);
CREATE INDEX IF NOT EXISTS idx_leads_state_classification ON leads(state, classification);

-- Add comments for documentation
COMMENT ON TABLE leads IS 'Lead records from CSV ingestion with full column expansion';
COMMENT ON COLUMN leads.lead_id IS 'Unique identifier (UUID) for each lead';
COMMENT ON COLUMN leads.created_at_utc IS 'Timestamp when lead was created (parsed from Call In Date with timezone)';
COMMENT ON COLUMN leads.classification IS 'Lead quality tier: Gold (all 6 fields) or Silver (missing fields)';
COMMENT ON COLUMN leads.source IS 'Lead source (e.g., CALL, WEB) - empty value = Silver classification';
COMMENT ON COLUMN leads.mortgage_amount IS 'Original mortgage amount string with formatting';
COMMENT ON COLUMN leads.call_in_date IS 'Original call in date string from CSV for reference';

-- ============================================================================
-- 2. CLIENTS TABLE (Buyer Accounts with OAuth2/JWT Support)
-- ============================================================================

CREATE TABLE clients (
    client_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Basic information
    email TEXT UNIQUE NOT NULL,
    company_name TEXT,
    contact_name TEXT,
    phone TEXT,

    -- Authentication - OAuth2 Support
    auth_provider TEXT CHECK (auth_provider IN ('local', 'google', 'microsoft', 'github')),
    auth_provider_user_id TEXT,  -- User ID from OAuth provider
    password_hash TEXT,  -- For local authentication (bcrypt)

    -- JWT Token Management
    refresh_token_hash TEXT,  -- Hashed refresh token for JWT rotation
    refresh_token_expires_at TIMESTAMPTZ,

    -- Account Status
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'closed')),
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    email_verification_token TEXT,
    email_verification_expires_at TIMESTAMPTZ,

    -- Password Reset (for local auth)
    password_reset_token TEXT,
    password_reset_expires_at TIMESTAMPTZ,

    -- Timestamps
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at_utc TIMESTAMPTZ,

    -- Ensure unique OAuth provider combinations
    CONSTRAINT uq_clients_oauth_provider UNIQUE (auth_provider, auth_provider_user_id)
);

-- Indexes for authentication and queries
CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email);
CREATE INDEX IF NOT EXISTS idx_clients_status ON clients(status);
CREATE INDEX IF NOT EXISTS idx_clients_oauth_provider ON clients(auth_provider, auth_provider_user_id);
CREATE INDEX IF NOT EXISTS idx_clients_email_verification ON clients(email_verification_token) WHERE email_verified = FALSE;
CREATE INDEX IF NOT EXISTS idx_clients_password_reset ON clients(password_reset_token) WHERE password_reset_token IS NOT NULL;

COMMENT ON TABLE clients IS 'Buyer accounts with OAuth2/JWT authentication support';
COMMENT ON COLUMN clients.auth_provider IS 'OAuth2 provider: local (password), google, microsoft, github';
COMMENT ON COLUMN clients.auth_provider_user_id IS 'Unique user ID from OAuth provider (sub claim)';
COMMENT ON COLUMN clients.password_hash IS 'Bcrypt hash for local authentication (NULL for OAuth users)';
COMMENT ON COLUMN clients.refresh_token_hash IS 'Hashed refresh token for JWT rotation';
COMMENT ON COLUMN clients.status IS 'active = can purchase, suspended = temporarily blocked, closed = permanently disabled';

-- ============================================================================
-- 3. INVENTORY TABLE (Sellable Eligibility Tracking)
-- ============================================================================

CREATE TABLE inventory (
    inventory_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    age_bucket TEXT NOT NULL CHECK (age_bucket IN (
        'MONTH_3_TO_5',
        'MONTH_6_TO_8',
        'MONTH_9_TO_11',
        'MONTH_12_TO_23',
        'MONTH_24_PLUS'
    )),

    -- Availability tracking
    created_at_utc TIMESTAMPTZ NOT NULL,
    sold_at_utc TIMESTAMPTZ,  -- NULL = available, NOT NULL = sold

    -- Uniqueness: one inventory record per (lead_id, age_bucket)
    CONSTRAINT uq_inventory_lead_bucket UNIQUE (lead_id, age_bucket)
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_inventory_lead_id ON inventory(lead_id);
CREATE INDEX IF NOT EXISTS idx_inventory_age_bucket ON inventory(age_bucket);
CREATE INDEX IF NOT EXISTS idx_inventory_availability ON inventory(sold_at_utc) WHERE sold_at_utc IS NULL;  -- Partial index for available inventory
CREATE INDEX IF NOT EXISTS idx_inventory_bucket_availability ON inventory(age_bucket, sold_at_utc) WHERE sold_at_utc IS NULL;

COMMENT ON TABLE inventory IS 'Tracks sellable eligibility per (lead_id, age_bucket) combination';
COMMENT ON COLUMN inventory.sold_at_utc IS 'NULL = available for sale, NOT NULL = already sold';
COMMENT ON CONSTRAINT uq_inventory_lead_bucket ON inventory IS 'Enforces single-sale-per-bucket rule: each lead can only be sold once per age bucket';

-- ============================================================================
-- 4. SALES TABLE (Immutable Sale Records)
-- ============================================================================

CREATE TABLE sales (
    sale_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES clients(client_id) ON DELETE RESTRICT,  -- Cannot delete client with sales history
    age_bucket TEXT NOT NULL CHECK (age_bucket IN (
        'MONTH_3_TO_5',
        'MONTH_6_TO_8',
        'MONTH_9_TO_11',
        'MONTH_12_TO_23',
        'MONTH_24_PLUS'
    )),

    -- Sale details
    sold_at_utc TIMESTAMPTZ NOT NULL,
    purchase_price NUMERIC(10, 2) NOT NULL,  -- Actual price paid (for revenue tracking)
    currency TEXT NOT NULL DEFAULT 'USD',

    -- Payment tracking (optional - for future payment integration)
    payment_status TEXT CHECK (payment_status IN ('pending', 'completed', 'failed', 'refunded')),
    payment_transaction_id TEXT,  -- External payment processor transaction ID

    -- Timestamps
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for reporting and queries
CREATE INDEX IF NOT EXISTS idx_sales_lead_id ON sales(lead_id);
CREATE INDEX IF NOT EXISTS idx_sales_client_id ON sales(client_id);
CREATE INDEX IF NOT EXISTS idx_sales_sold_at ON sales(sold_at_utc);
CREATE INDEX IF NOT EXISTS idx_sales_bucket ON sales(age_bucket);
CREATE INDEX IF NOT EXISTS idx_sales_payment_status ON sales(payment_status) WHERE payment_status IS NOT NULL;

COMMENT ON TABLE sales IS 'Immutable record of sale events - never update, only insert';
COMMENT ON COLUMN sales.purchase_price IS 'Actual sale price paid for revenue tracking and invoicing';
COMMENT ON COLUMN sales.payment_status IS 'Payment state: pending (awaiting payment), completed (paid), failed, refunded';

-- ============================================================================
-- 5. PRICING RULES TABLE (Configurable Pricing)
-- ============================================================================

CREATE TABLE pricing_rules (
    pricing_rule_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    classification TEXT NOT NULL CHECK (classification IN ('Gold', 'Silver')),
    age_bucket TEXT NOT NULL CHECK (age_bucket IN (
        'MONTH_3_TO_5',
        'MONTH_6_TO_8',
        'MONTH_9_TO_11',
        'MONTH_12_TO_23',
        'MONTH_24_PLUS'
    )),

    -- Pricing
    base_price NUMERIC(10, 2) NOT NULL CHECK (base_price >= 0),
    currency TEXT NOT NULL DEFAULT 'USD',

    -- Effective date range (for price history)
    effective_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    effective_to TIMESTAMPTZ,  -- NULL = currently active

    -- Metadata
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT,  -- Admin user who set this price
    notes TEXT,

    -- Ensure only one active price per (classification, age_bucket)
    CONSTRAINT uq_pricing_classification_bucket_active UNIQUE (classification, age_bucket, effective_from),

    -- Ensure effective_to is after effective_from
    CONSTRAINT chk_pricing_effective_dates CHECK (effective_to IS NULL OR effective_to > effective_from)
);

-- Index for active pricing queries
CREATE INDEX IF NOT EXISTS idx_pricing_active ON pricing_rules(classification, age_bucket, effective_from, effective_to)
    WHERE effective_to IS NULL;

COMMENT ON TABLE pricing_rules IS 'Configurable pricing per (classification, age_bucket) with historical tracking';
COMMENT ON COLUMN pricing_rules.effective_to IS 'NULL = currently active pricing, NOT NULL = historical pricing record';
COMMENT ON COLUMN pricing_rules.base_price IS 'Price in cents or dollars (depending on currency) - must be non-negative';

-- ============================================================================
-- 6. ATOMIC SALE FUNCTION (Race Condition Prevention)
-- ============================================================================

CREATE OR REPLACE FUNCTION execute_sale_atomic(
    p_lead_id UUID,
    p_age_bucket TEXT,
    p_client_id UUID,
    p_sold_at TIMESTAMPTZ,
    p_purchase_price NUMERIC
)
RETURNS JSON AS $$
DECLARE
    v_inventory_id UUID;
    v_inventory_rows_updated INTEGER;
    v_sale_id UUID;
    v_client_status TEXT;
BEGIN
    -- 1. Verify client is active
    SELECT status INTO v_client_status
    FROM clients
    WHERE client_id = p_client_id;

    IF v_client_status IS NULL THEN
        RETURN json_build_object(
            'success', false,
            'error', 'INVALID_CLIENT',
            'message', 'Client does not exist'
        );
    END IF;

    IF v_client_status != 'active' THEN
        RETURN json_build_object(
            'success', false,
            'error', 'CLIENT_SUSPENDED',
            'message', 'Client account is not active (status: ' || v_client_status || ')'
        );
    END IF;

    -- 2. Lock the inventory row first (atomic check-and-set)
    -- This prevents race conditions by locking before checking availability
    SELECT inventory_id INTO v_inventory_id
    FROM inventory
    WHERE lead_id = p_lead_id
      AND age_bucket = p_age_bucket
    FOR UPDATE NOWAIT;  -- Fail fast if locked by another transaction

    -- Check if inventory record exists
    IF v_inventory_id IS NULL THEN
        RETURN json_build_object(
            'success', false,
            'error', 'INVENTORY_NOT_FOUND',
            'message', 'Lead is not available in this age bucket'
        );
    END IF;

    -- 3. Update inventory if still available
    UPDATE inventory
    SET sold_at_utc = p_sold_at
    WHERE inventory_id = v_inventory_id
      AND sold_at_utc IS NULL;  -- Only if still available

    GET DIAGNOSTICS v_inventory_rows_updated = ROW_COUNT;

    IF v_inventory_rows_updated = 0 THEN
        -- Inventory exists but is already sold
        RETURN json_build_object(
            'success', false,
            'error', 'ALREADY_SOLD',
            'message', 'This lead has already been sold in the specified age bucket'
        );
    END IF;

    -- 4. Record sale
    v_sale_id := gen_random_uuid();
    INSERT INTO sales (sale_id, lead_id, client_id, age_bucket, sold_at_utc, purchase_price, payment_status)
    VALUES (v_sale_id, p_lead_id, p_client_id, p_age_bucket, p_sold_at, p_purchase_price, 'completed');

    -- 5. Return success
    RETURN json_build_object(
        'success', true,
        'sale_id', v_sale_id,
        'message', 'Lead purchased successfully'
    );

EXCEPTION
    WHEN lock_not_available THEN
        -- Another transaction is processing this inventory
        RETURN json_build_object(
            'success', false,
            'error', 'LOCK_TIMEOUT',
            'message', 'Another purchase is in progress for this lead. Please try again.'
        );
    WHEN foreign_key_violation THEN
        RETURN json_build_object(
            'success', false,
            'error', 'INVALID_REFERENCE',
            'message', 'Invalid lead_id, client_id, or age_bucket'
        );
    WHEN OTHERS THEN
        RETURN json_build_object(
            'success', false,
            'error', 'DATABASE_ERROR',
            'message', 'Database error: ' || SQLERRM
        );
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION execute_sale_atomic IS 'Atomically execute a sale with row-level locking to prevent race conditions. Verifies client status, checks inventory availability, and creates sale record in a single transaction.';
