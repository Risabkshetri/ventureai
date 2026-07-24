-- 006_identified_risks.sql
-- Normalized one-row-per-risk so we can query/filter across startups
-- (e.g. "all high-severity financial risks").

CREATE TABLE IF NOT EXISTS identified_risks (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id   UUID    NOT NULL REFERENCES evaluations (id) ON DELETE CASCADE,
    category        TEXT    NOT NULL,
    risk            TEXT    NOT NULL,
    severity        TEXT    NOT NULL CHECK (severity IN ('low', 'medium', 'high'))
);

-- ── Indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_identified_risks_evaluation_id ON identified_risks (evaluation_id);
CREATE INDEX IF NOT EXISTS idx_identified_risks_severity ON identified_risks (severity);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE identified_risks ENABLE ROW LEVEL SECURITY;
