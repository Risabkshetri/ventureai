-- 000_extensions.sql
-- Enable required PostgreSQL extensions for UUID generation.
-- gen_random_uuid() is available natively in PostgreSQL 13+, but enabling
-- pgcrypto ensures compatibility and adds other crypto functions.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
