-- 013_add_profile_fields.sql
-- Add bio field to the users table.

ALTER TABLE users 
ADD COLUMN IF NOT EXISTS bio TEXT;
