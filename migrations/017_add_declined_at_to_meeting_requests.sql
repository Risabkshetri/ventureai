-- 017_add_declined_at_to_meeting_requests.sql
-- Adds declined_at to meeting_requests to track when a request was declined for cooldown purposes.

ALTER TABLE meeting_requests ADD COLUMN IF NOT EXISTS declined_at TIMESTAMPTZ;
