-- 001_users.sql
-- Create the user_role enum and users table.

-- ── Enum ────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('founder', 'investor', 'admin');
    END IF;
END
$$;

-- ── Table ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id             UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    name           TEXT,
    email          TEXT           UNIQUE NOT NULL,
    password_hash  TEXT           NOT NULL,
    role           user_role,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- ── Row Level Security ─────────────────────────────────────────────────────
-- RLS is enabled but no policies are defined yet.
-- This means NO access by default (except for service_role / postgres).
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
