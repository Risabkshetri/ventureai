-- 016_meeting_requests.sql
-- Tracks meeting requests between investors and founders.

CREATE TABLE IF NOT EXISTS meeting_requests (
    id              UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    investor_id     UUID           NOT NULL REFERENCES users (id),
    startup_id      UUID           NOT NULL REFERENCES startups (id),
    founder_id      UUID           NOT NULL REFERENCES users (id),
    status          TEXT           NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'declined')),
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT uq_meeting_requests_investor_startup UNIQUE (investor_id, startup_id)
);

-- ── Indexes ─────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_meeting_requests_investor_id ON meeting_requests (investor_id);
CREATE INDEX IF NOT EXISTS idx_meeting_requests_startup_id ON meeting_requests (startup_id);
CREATE INDEX IF NOT EXISTS idx_meeting_requests_founder_id ON meeting_requests (founder_id);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE meeting_requests ENABLE ROW LEVEL SECURITY;

-- Founders can see requests for their startups
CREATE POLICY "Founders can view meeting requests for their startups" 
ON meeting_requests FOR SELECT 
USING (auth.uid() = founder_id);

-- Founders can update status of requests for their startups
CREATE POLICY "Founders can update meeting requests for their startups" 
ON meeting_requests FOR UPDATE 
USING (auth.uid() = founder_id);

-- Investors can see their own requests
CREATE POLICY "Investors can view their own meeting requests" 
ON meeting_requests FOR SELECT 
USING (auth.uid() = investor_id);

-- Investors can create meeting requests
CREATE POLICY "Investors can create meeting requests" 
ON meeting_requests FOR INSERT 
WITH CHECK (auth.uid() = investor_id);
