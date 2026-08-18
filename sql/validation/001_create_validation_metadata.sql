-- Pulse
-- Phase 3, Step 4
-- Validation-run and validation-result metadata.
--
-- Validation is evaluated against an already-succeeded raw ingestion batch.
-- Each run records its checks and whether the snapshot is eligible for
-- promotion into staging.
--
-- Operational timestamps deliberately use clock_timestamp().

BEGIN;

CREATE TABLE IF NOT EXISTS validation.validation_runs (
    validation_run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,

    status TEXT NOT NULL DEFAULT 'running',

    expected_check_count INTEGER NOT NULL,
    completed_check_count INTEGER NOT NULL DEFAULT 0,
    passed_check_count INTEGER NOT NULL DEFAULT 0,
    failed_check_count INTEGER NOT NULL DEFAULT 0,

    started_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    completed_at TIMESTAMPTZ,

    error_message TEXT,

    CONSTRAINT validation_runs_batch_fk
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batches (ingestion_batch_id)
        ON DELETE RESTRICT,

    CONSTRAINT validation_runs_status_chk
        CHECK (
            status IN (
                'running',
                'succeeded',
                'failed'
            )
        ),

    CONSTRAINT validation_runs_expected_check_count_chk
        CHECK (
            expected_check_count > 0
        ),

    CONSTRAINT validation_runs_check_counts_chk
        CHECK (
            completed_check_count >= 0
            AND passed_check_count >= 0
            AND failed_check_count >= 0
            AND completed_check_count
                = passed_check_count + failed_check_count
            AND completed_check_count
                <= expected_check_count
        ),

    CONSTRAINT validation_runs_success_reconciliation_chk
        CHECK (
            status <> 'succeeded'
            OR (
                completed_check_count = expected_check_count
                AND failed_check_count = 0
            )
        ),

    CONSTRAINT validation_runs_completion_state_chk
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

    CONSTRAINT uq_validation_runs_run_batch
        UNIQUE (
            validation_run_id,
            ingestion_batch_id
        )
);


CREATE UNIQUE INDEX IF NOT EXISTS
    uq_validation_runs_successful_batch
ON validation.validation_runs (ingestion_batch_id)
WHERE status = 'succeeded';


CREATE INDEX IF NOT EXISTS
    ix_validation_runs_batch_id
ON validation.validation_runs (ingestion_batch_id);


CREATE INDEX IF NOT EXISTS
    ix_validation_runs_status
ON validation.validation_runs (status);


CREATE TABLE IF NOT EXISTS validation.check_results (
    validation_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    validation_run_id BIGINT NOT NULL,

    check_name TEXT NOT NULL,
    check_category TEXT NOT NULL,
    dataset_name TEXT,

    severity TEXT NOT NULL DEFAULT 'error',
    status TEXT NOT NULL,

    violation_count BIGINT NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    checked_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT validation_check_results_run_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT validation_check_results_name_chk
        CHECK (
            length(trim(check_name)) > 0
        ),

    CONSTRAINT validation_check_results_category_chk
        CHECK (
            check_category IN (
                'reconciliation',
                'uniqueness',
                'referential_integrity',
                'chronology',
                'domain',
                'nullability'
            )
        ),

    CONSTRAINT validation_check_results_dataset_chk
        CHECK (
            dataset_name IS NULL
            OR length(trim(dataset_name)) > 0
        ),

    CONSTRAINT validation_check_results_severity_chk
        CHECK (
            severity IN (
                'error',
                'warning'
            )
        ),

    CONSTRAINT validation_check_results_status_chk
        CHECK (
            status IN (
                'passed',
                'failed'
            )
        ),

    CONSTRAINT validation_check_results_violation_count_chk
        CHECK (
            violation_count >= 0
        ),

    CONSTRAINT validation_check_results_passed_chk
        CHECK (
            status <> 'passed'
            OR violation_count = 0
        ),

    CONSTRAINT validation_check_results_failed_chk
        CHECK (
            status <> 'failed'
            OR violation_count > 0
        ),

    CONSTRAINT uq_validation_check_results_run_check
        UNIQUE (
            validation_run_id,
            check_name
        )
);


CREATE INDEX IF NOT EXISTS
    ix_validation_check_results_run_id
ON validation.check_results (validation_run_id);


CREATE INDEX IF NOT EXISTS
    ix_validation_check_results_status
ON validation.check_results (status);


CREATE INDEX IF NOT EXISTS
    ix_validation_check_results_dataset
ON validation.check_results (dataset_name);


COMMIT;
