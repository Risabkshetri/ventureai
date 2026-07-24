-- 010_investor_actions.sql
-- Tracks investor interactions with startups (shortlist, interested, meeting_request).
-- UNIQUE(investor_id, startup_id, action) prevents duplicate actions.

CREATE TABLE IF NOT EXISTS investor_actions (
    id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_id     UUID           NOT NULL REFERENCES users (id),
    startup_id      UUID           NOT NULL REFERENCES startups (id),
    action          TEXT           NOT NULL CHECK (action IN ('shortlist', 'interested', 'meeting_request')),
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT uq_investor_actions_investor_startup_action UNIQUE (investor_id, startup_id, action)
);

-- ── Indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_investor_actions_investor_id ON investor_actions (investor_id);
CREATE INDEX IF NOT EXISTS idx_investor_actions_startup_id ON investor_actions (startup_id);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE investor_actions ENABLE ROW LEVEL SECURITY;
