-- Run this in Supabase SQL Editor to check your table schemas

-- Check inventory table structure
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'inventory'
ORDER BY ordinal_position;

-- Check all tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public';
