-- 003_evaluations.sql
-- Create the evaluation_status enum and evaluations table.

-- ── Enum ────────────────────────────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'evaluation_status') THEN
        CREATE TYPE evaluation_status AS ENUM ('pending', 'processing', 'completed', 'failed');
    END IF;
END
$$;

-- ── Table ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evaluations (
    id             UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    startup_id     UUID                NOT NULL REFERENCES startups (id) ON DELETE CASCADE,
    version        INT                 NOT NULL,
    status         evaluation_status   NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ         NOT NULL DEFAULT now(),

    CONSTRAINT uq_evaluations_startup_version UNIQUE (startup_id, version)
);

-- ── Index ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_evaluations_startup_id ON evaluations (startup_id);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE evaluations ENABLE ROW LEVEL SECURITY;
