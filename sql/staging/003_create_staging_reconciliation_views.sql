-- Pulse
-- Phase 3, Step 4
-- Raw-to-staging reconciliation views.
--
-- These views provide deterministic row-count reconciliation for each
-- ingestion batch and dataset.
--
-- No raw or staging data is mutated.

BEGIN;


CREATE OR REPLACE VIEW
validation.staging_dataset_counts AS

SELECT
    ingestion_batch_id,
    'installations'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS staging_row_count
FROM staging.installations
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'users'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS staging_row_count
FROM staging.users
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'product_events'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS staging_row_count
FROM staging.product_events
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'subscriptions'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS staging_row_count
FROM staging.subscriptions
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'subscription_transactions'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS staging_row_count
FROM staging.subscription_transactions
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'experiment_assignments'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS staging_row_count
FROM staging.experiment_assignments
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'marketing_spend'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS staging_row_count
FROM staging.marketing_spend
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'app_releases'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS staging_row_count
FROM staging.app_releases
GROUP BY ingestion_batch_id
;


CREATE OR REPLACE VIEW
validation.staging_reconciliation AS

SELECT
    r.ingestion_batch_id,
    r.dataset_name,

    r.actual_row_count::BIGINT
        AS raw_row_count,

    COALESCE(
        s.staging_row_count,
        0
    )::BIGINT AS staging_row_count,

    (
        r.actual_row_count
        - COALESCE(
            s.staging_row_count,
            0
        )
    )::BIGINT AS row_count_delta,

    (
        r.actual_row_count
        = COALESCE(
            s.staging_row_count,
            0
        )
    ) AS reconciled

FROM validation.raw_dataset_counts AS r

LEFT JOIN validation.staging_dataset_counts AS s
    ON s.ingestion_batch_id
        = r.ingestion_batch_id
    AND s.dataset_name
        = r.dataset_name
;


COMMIT;