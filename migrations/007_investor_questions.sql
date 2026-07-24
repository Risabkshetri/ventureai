-- 007_investor_questions.sql
-- Normalized one-row-per-question for easy filtering by category.

CREATE TABLE IF NOT EXISTS investor_questions (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id   UUID    NOT NULL REFERENCES evaluations (id) ON DELETE CASCADE,
    category        TEXT    NOT NULL,
    question        TEXT    NOT NULL
);

-- ── Index ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_investor_questions_evaluation_id ON investor_questions (evaluation_id);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE investor_questions ENABLE ROW LEVEL SECURITY;
