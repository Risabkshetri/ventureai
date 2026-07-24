-- 009_final_reports.sql
-- One final report per evaluation (unique constraint on evaluation_id).

CREATE TABLE IF NOT EXISTS final_reports (
    id                              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id                   UUID           NOT NULL UNIQUE REFERENCES evaluations (id) ON DELETE CASCADE,
    full_report                     JSONB,
    investment_recommendation       TEXT,
    recommendation_justification    TEXT,
    generated_at                    TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE final_reports ENABLE ROW LEVEL SECURITY;
