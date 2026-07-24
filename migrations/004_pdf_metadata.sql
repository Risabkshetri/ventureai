-- 004_pdf_metadata.sql
-- Stores metadata about uploaded pitch-deck PDFs for each evaluation.

CREATE TABLE IF NOT EXISTS pdf_metadata (
    id                  UUID           PRIMARY KEY DEFAULT gen_random_uuid(),
    evaluation_id       UUID           NOT NULL REFERENCES evaluations (id) ON DELETE CASCADE,
    file_name           TEXT,
    file_size_kb        INT,
    page_count          INT,
    uploaded_at         TIMESTAMPTZ    NOT NULL DEFAULT now(),
    extraction_status   TEXT
);

-- ── Index ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_pdf_metadata_evaluation_id ON pdf_metadata (evaluation_id);

-- ── Row Level Security ─────────────────────────────────────────────────────
ALTER TABLE pdf_metadata ENABLE ROW LEVEL SECURITY;
