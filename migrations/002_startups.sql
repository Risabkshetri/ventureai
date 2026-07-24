-- 002_startups.sql
-- Create the startups table with a foreign key to users.

CREATE TABLE IF NOT EXISTS startups (
    id             UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    founder_id     UUID           NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    startup_name   TEXT           NOT NULL,
    industry       TEXT,
    stage          TEXT,
    website        TEXT,
    description    TEXT,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- ── Index ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_startups_founder_id ON startups (founder_id);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE startups ENABLE ROW LEVEL SECURITY;
