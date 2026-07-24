-- 014_add_professional_profile_fields.sql
-- Add professional founder and startup profile fields to users and startups tables.

-- 1. Alter Users Table
ALTER TABLE users 
ADD COLUMN IF NOT EXISTS headline TEXT,
ADD COLUMN IF NOT EXISTS profile_photo_url TEXT,
ADD COLUMN IF NOT EXISTS linkedin_url TEXT;

-- 2. Alter Startups Table
ALTER TABLE startups 
ADD COLUMN IF NOT EXISTS logo_url TEXT,
ADD COLUMN IF NOT EXISTS tagline TEXT,
ADD COLUMN IF NOT EXISTS team_size TEXT,
ADD COLUMN IF NOT EXISTS funding_raised TEXT,
ADD COLUMN IF NOT EXISTS linkedin_url TEXT;
