-- Lead Sales Platform Database Schema
--
-- This schema defines the leads table with all CSV columns as individual fields.
-- Run this in Supabase SQL Editor to create/update the table structure.

-- Drop existing table to recreate with new schema
DROP TABLE IF EXISTS leads CASCADE;

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
