-- Pulse
-- Phase 3, Step 3
-- Raw-layer ingestion metadata.
--
-- These tables record one warehouse ingestion attempt per batch and one
-- metadata record per source file belonging to that batch.
--
-- The source snapshot is identified by the deterministic snapshot_id
-- produced by Phase 3 Step 1.

BEGIN;

CREATE TABLE IF NOT EXISTS raw.ingestion_batches (
    ingestion_batch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    snapshot_id TEXT NOT NULL,

    status TEXT NOT NULL DEFAULT 'running',

    expected_file_count INTEGER NOT NULL,
    expected_row_count BIGINT NOT NULL,

    accepted_row_count BIGINT NOT NULL DEFAULT 0,
    rejected_row_count BIGINT NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,

    error_message TEXT,

    CONSTRAINT ingestion_batches_snapshot_id_format_chk
        CHECK (
            snapshot_id ~ '^raw_[0-9a-f]{64}$'
        ),

    CONSTRAINT ingestion_batches_status_chk
        CHECK (
            status IN (
                'running',
                'succeeded',
                'failed'
            )
        ),

    CONSTRAINT ingestion_batches_expected_file_count_chk
        CHECK (
            expected_file_count > 0
        ),

    CONSTRAINT ingestion_batches_row_counts_chk
        CHECK (
            expected_row_count >= 0
            AND accepted_row_count >= 0
            AND rejected_row_count >= 0
            AND accepted_row_count + rejected_row_count
                <= expected_row_count
        ),

    CONSTRAINT ingestion_batches_success_reconciliation_chk
        CHECK (
            status <> 'succeeded'
            OR accepted_row_count + rejected_row_count
                = expected_row_count
        ),

    CONSTRAINT ingestion_batches_completion_state_chk
        CHECK (
            (
                status = 'running'
                AND completed_at IS NULL
            )
            OR
            (
                status IN ('succeeded', 'failed')
                AND completed_at IS NOT NULL
            )
        ),

    CONSTRAINT ingestion_batches_failure_message_chk
        CHECK (
            status <> 'failed'
            OR error_message IS NOT NULL
        )
);


-- Database-level idempotency protection:
-- only one successful load may exist for a deterministic snapshot.
--
-- Failed attempts remain auditable and may be retried.
CREATE UNIQUE INDEX IF NOT EXISTS
    uq_ingestion_batches_successful_snapshot
ON raw.ingestion_batches (snapshot_id)
WHERE status = 'succeeded';


CREATE INDEX IF NOT EXISTS
    ix_ingestion_batches_started_at
ON raw.ingestion_batches (started_at);


CREATE INDEX IF NOT EXISTS
    ix_ingestion_batches_status
ON raw.ingestion_batches (status);


CREATE TABLE IF NOT EXISTS raw.ingestion_files (
    ingestion_file_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,

    dataset_name TEXT NOT NULL,
    source_file TEXT NOT NULL,

    file_sha256 TEXT NOT NULL,

    expected_row_count BIGINT NOT NULL,
    accepted_row_count BIGINT NOT NULL DEFAULT 0,
    rejected_row_count BIGINT NOT NULL DEFAULT 0,

    status TEXT NOT NULL DEFAULT 'pending',

    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    error_message TEXT,

    CONSTRAINT ingestion_files_batch_fk
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batches (ingestion_batch_id)
        ON DELETE RESTRICT,

    CONSTRAINT ingestion_files_dataset_name_chk
        CHECK (
            length(trim(dataset_name)) > 0
        ),

    CONSTRAINT ingestion_files_source_file_chk
        CHECK (
            length(trim(source_file)) > 0
        ),

    CONSTRAINT ingestion_files_sha256_chk
        CHECK (
            length(file_sha256) = 64
            AND file_sha256 ~ '^[0-9a-f]{64}$'
        ),

    CONSTRAINT ingestion_files_status_chk
        CHECK (
            status IN (
                'pending',
                'loading',
                'loaded',
                'failed',
                'rolled_back'
            )
        ),

    CONSTRAINT ingestion_files_row_counts_chk
        CHECK (
            expected_row_count >= 0
            AND accepted_row_count >= 0
            AND rejected_row_count >= 0
            AND accepted_row_count + rejected_row_count
                <= expected_row_count
        ),

    CONSTRAINT ingestion_files_loaded_reconciliation_chk
        CHECK (
            status <> 'loaded'
            OR accepted_row_count + rejected_row_count
                = expected_row_count
        ),

    CONSTRAINT ingestion_files_timing_state_chk
        CHECK (
            (
                status = 'pending'
                AND started_at IS NULL
                AND completed_at IS NULL
            )
            OR
            (
                status = 'loading'
                AND started_at IS NOT NULL
                AND completed_at IS NULL
            )
            OR
            (
                status IN ('loaded', 'failed', 'rolled_back')
                AND started_at IS NOT NULL
                AND completed_at IS NOT NULL
            )
        ),

    CONSTRAINT ingestion_files_failure_message_chk
        CHECK (
            status <> 'failed'
            OR error_message IS NOT NULL
        ),

    CONSTRAINT uq_ingestion_files_batch_dataset
        UNIQUE (
            ingestion_batch_id,
            dataset_name
        ),

    CONSTRAINT uq_ingestion_files_batch_source
        UNIQUE (
            ingestion_batch_id,
            source_file
        )
);


CREATE INDEX IF NOT EXISTS
    ix_ingestion_files_batch_id
ON raw.ingestion_files (ingestion_batch_id);


CREATE INDEX IF NOT EXISTS
    ix_ingestion_files_status
ON raw.ingestion_files (status);


COMMIT;
