-- Pulse
-- Phase 3, Step 4
-- Staging promotion metadata.
--
-- A successful validation run authorises one transactional promotion
-- of its raw ingestion batch into staging.
--
-- Operational timestamps use clock_timestamp().

BEGIN;


CREATE TABLE IF NOT EXISTS staging.promotion_runs (
    promotion_run_id BIGINT
        GENERATED ALWAYS AS IDENTITY
        PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    validation_run_id BIGINT NOT NULL,

    status TEXT NOT NULL DEFAULT 'running',

    expected_dataset_count INTEGER NOT NULL,
    promoted_dataset_count INTEGER NOT NULL DEFAULT 0,

    expected_row_count BIGINT NOT NULL,
    promoted_row_count BIGINT NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ NOT NULL
        DEFAULT clock_timestamp(),

    completed_at TIMESTAMPTZ,

    error_message TEXT,

    CONSTRAINT promotion_runs_batch_fk
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batches (
            ingestion_batch_id
        )
        ON DELETE RESTRICT,

    CONSTRAINT promotion_runs_validation_fk
        FOREIGN KEY (
            validation_run_id,
            ingestion_batch_id
        )
        REFERENCES validation.validation_runs (
            validation_run_id,
            ingestion_batch_id
        )
        ON DELETE RESTRICT,

    CONSTRAINT promotion_runs_status_chk
        CHECK (
            status IN (
                'running',
                'succeeded',
                'failed'
            )
        ),

    CONSTRAINT promotion_runs_dataset_counts_chk
        CHECK (
            expected_dataset_count > 0
            AND promoted_dataset_count >= 0
            AND promoted_dataset_count
                <= expected_dataset_count
        ),

    CONSTRAINT promotion_runs_row_counts_chk
        CHECK (
            expected_row_count >= 0
            AND promoted_row_count >= 0
            AND promoted_row_count
                <= expected_row_count
        ),

    CONSTRAINT promotion_runs_success_reconciliation_chk
        CHECK (
            status <> 'succeeded'
            OR (
                promoted_dataset_count
                    = expected_dataset_count
                AND promoted_row_count
                    = expected_row_count
            )
        ),

    CONSTRAINT promotion_runs_completion_state_chk
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

    CONSTRAINT promotion_runs_failure_message_chk
        CHECK (
            status <> 'failed'
            OR error_message IS NOT NULL
        )
);


CREATE UNIQUE INDEX IF NOT EXISTS
    uq_promotion_runs_successful_batch
ON staging.promotion_runs (
    ingestion_batch_id
)
WHERE status = 'succeeded';


CREATE INDEX IF NOT EXISTS
    ix_promotion_runs_validation_run
ON staging.promotion_runs (
    validation_run_id
);


CREATE INDEX IF NOT EXISTS
    ix_promotion_runs_status
ON staging.promotion_runs (
    status
);


COMMIT;