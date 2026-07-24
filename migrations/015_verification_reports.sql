-- 015_verification_reports.sql
-- Store the results of LangGraph verification agents.

CREATE TABLE IF NOT EXISTS verification_reports (
    id                              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id                   UUID           NOT NULL UNIQUE REFERENCES evaluations (id) ON DELETE CASCADE,
    claim_verification              JSONB,
    founder_research                JSONB,
    manipulation_detection          JSONB,
    created_at                      TIMESTAMPTZ    NOT NULL DEFAULT now()
);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE verification_reports ENABLE ROW LEVEL SECURITY;
