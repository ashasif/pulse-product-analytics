-- Pulse
-- Phase 3, Step 3
-- Use actual wall-clock time for ingestion batch start metadata.

BEGIN;

ALTER TABLE raw.ingestion_batches
    ALTER COLUMN started_at
    SET DEFAULT clock_timestamp();

COMMIT;