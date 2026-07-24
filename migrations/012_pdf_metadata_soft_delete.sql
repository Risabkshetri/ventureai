-- 012_pdf_metadata_soft_delete.sql
-- Adds a deleted_at timestamp to support soft deletion of documents while preserving evaluation history

ALTER TABLE pdf_metadata
ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;

-- Update RLS policies to optionally exclude deleted rows or handle them as needed
-- Note: Queries will explicitly filter out `deleted_at IS NOT NULL` where appropriate
