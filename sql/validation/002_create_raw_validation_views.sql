-- Pulse
-- Phase 3, Step 4
-- Raw-layer validation support views.
--
-- These views expose deterministic row-count reconciliation between the
-- succeeded raw ingestion metadata and the persisted raw tables.
--
-- No raw data is mutated.

BEGIN;


CREATE OR REPLACE VIEW validation.raw_dataset_counts AS

SELECT
    ingestion_batch_id,
    'installations'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS actual_row_count
FROM raw.installations
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'users'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS actual_row_count
FROM raw.users
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'product_events'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS actual_row_count
FROM raw.product_events
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'subscriptions'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS actual_row_count
FROM raw.subscriptions
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'subscription_transactions'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS actual_row_count
FROM raw.subscription_transactions
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'experiment_assignments'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS actual_row_count
FROM raw.experiment_assignments
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'marketing_spend'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS actual_row_count
FROM raw.marketing_spend
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'app_releases'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS actual_row_count
FROM raw.app_releases
GROUP BY ingestion_batch_id
;


CREATE OR REPLACE VIEW validation.raw_reconciliation AS
SELECT
    f.ingestion_batch_id,
    f.dataset_name,
    f.source_file,
    f.status AS ingestion_file_status,
    f.expected_row_count,
    f.accepted_row_count,
    f.rejected_row_count,
    COALESCE(
        c.actual_row_count,
        0
    )::BIGINT AS actual_row_count,

    (
        f.accepted_row_count
        - COALESCE(c.actual_row_count, 0)
    )::BIGINT AS accepted_vs_actual_delta,

    (
        f.expected_row_count
        - (
            f.accepted_row_count
            + f.rejected_row_count
        )
    )::BIGINT AS expected_vs_processed_delta,

    (
        f.status = 'loaded'
        AND f.accepted_row_count
            = COALESCE(c.actual_row_count, 0)
        AND f.expected_row_count
            = (
                f.accepted_row_count
                + f.rejected_row_count
            )
    ) AS reconciled

FROM raw.ingestion_files AS f

LEFT JOIN validation.raw_dataset_counts AS c
    ON c.ingestion_batch_id
        = f.ingestion_batch_id
    AND c.dataset_name
        = f.dataset_name
;


COMMIT;
