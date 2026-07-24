-- 008_scores.sql
-- Stores numeric scoring dimensions and a JSONB blob for detailed reasoning.

CREATE TABLE IF NOT EXISTS scores (
    id                      UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id           UUID    NOT NULL REFERENCES evaluations (id) ON DELETE CASCADE,
    market_opportunity      INT,
    product_innovation      INT,
    team_strength           INT,
    business_model_score    INT,
    competitive_advantage   INT,
    traction_score          INT,
    scalability             INT,
    startup_score           INT,
    score_reasoning         JSONB
);

-- ── Index ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_scores_evaluation_id ON scores (evaluation_id);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE scores ENABLE ROW LEVEL SECURITY;
