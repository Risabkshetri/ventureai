-- 005_executive_summaries.sql
-- Stores the AI-extracted executive summary sections for each evaluation.

CREATE TABLE IF NOT EXISTS executive_summaries (
    id                  UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id       UUID    NOT NULL REFERENCES evaluations (id) ON DELETE CASCADE,
    problem             TEXT,
    solution            TEXT,
    target_market       TEXT,
    business_model      TEXT,
    traction            TEXT,
    executive_summary   TEXT
);

-- ── Index ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_executive_summaries_evaluation_id ON executive_summaries (evaluation_id);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE executive_summaries ENABLE ROW LEVEL SECURITY;
