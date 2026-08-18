-- Pulse
-- Phase 3, Step 5
-- Analytics warehouse build metadata.
--
-- One successful analytics build is permitted for each promoted
-- ingestion batch. Failed attempts remain auditable and retryable.

BEGIN;

CREATE TABLE IF NOT EXISTS analytics.build_runs (
    analytics_build_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    validation_run_id BIGINT NOT NULL,
    promotion_run_id BIGINT NOT NULL,

    status TEXT NOT NULL DEFAULT 'running',

    expected_table_count INTEGER NOT NULL,
    completed_table_count INTEGER NOT NULL DEFAULT 0,

    source_staging_row_count BIGINT NOT NULL,
    analytics_row_count BIGINT NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,

    error_message TEXT,

    CONSTRAINT analytics_build_runs_ingestion_batch_fk
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batches (ingestion_batch_id)
        ON DELETE RESTRICT,

    CONSTRAINT analytics_build_runs_validation_run_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT analytics_build_runs_promotion_run_fk
        FOREIGN KEY (promotion_run_id)
        REFERENCES staging.promotion_runs (promotion_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT analytics_build_runs_status_chk
        CHECK (status IN ('running', 'succeeded', 'failed')),

    CONSTRAINT analytics_build_runs_table_counts_chk
        CHECK (
            expected_table_count > 0
            AND completed_table_count >= 0
            AND completed_table_count <= expected_table_count
        ),

    CONSTRAINT analytics_build_runs_row_counts_chk
        CHECK (
            source_staging_row_count >= 0
            AND analytics_row_count >= 0
        ),

    CONSTRAINT analytics_build_runs_completion_state_chk
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

    CONSTRAINT analytics_build_runs_success_chk
        CHECK (
            status <> 'succeeded'
            OR completed_table_count = expected_table_count
        ),

    CONSTRAINT analytics_build_runs_failure_message_chk
        CHECK (
            status <> 'failed'
            OR error_message IS NOT NULL
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS
    uq_analytics_build_runs_successful_batch
ON analytics.build_runs (ingestion_batch_id)
WHERE status = 'succeeded';

CREATE INDEX IF NOT EXISTS
    ix_analytics_build_runs_status
ON analytics.build_runs (status);

CREATE INDEX IF NOT EXISTS
    ix_analytics_build_runs_promotion
ON analytics.build_runs (promotion_run_id);

COMMIT;
