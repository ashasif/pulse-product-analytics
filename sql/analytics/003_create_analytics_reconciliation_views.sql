-- Pulse
-- Phase 3, Step 5
-- Staging-to-analytics reconciliation controls.

BEGIN;

CREATE OR REPLACE VIEW validation.analytics_dataset_counts AS

SELECT
    ingestion_batch_id,
    'installations'::TEXT AS dataset_name,
    COUNT(*)::BIGINT AS analytics_row_count
FROM analytics.dim_installation
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'users',
    COUNT(*)::BIGINT
FROM analytics.dim_user
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'product_events',
    COUNT(*)::BIGINT
FROM analytics.fact_product_event
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'subscriptions',
    COUNT(*)::BIGINT
FROM analytics.fact_subscription
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'subscription_transactions',
    COUNT(*)::BIGINT
FROM analytics.fact_subscription_transaction
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'experiment_assignments',
    COUNT(*)::BIGINT
FROM analytics.fact_experiment_assignment
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'marketing_spend',
    COUNT(*)::BIGINT
FROM analytics.fact_marketing_spend
GROUP BY ingestion_batch_id

UNION ALL

SELECT
    ingestion_batch_id,
    'app_releases',
    COUNT(*)::BIGINT
FROM analytics.dim_app_release
GROUP BY ingestion_batch_id;


CREATE OR REPLACE VIEW validation.analytics_reconciliation AS
SELECT
    s.ingestion_batch_id,
    s.dataset_name,
    s.staging_row_count,
    COALESCE(
        a.analytics_row_count,
        0
    )::BIGINT AS analytics_row_count,
    (
        COALESCE(a.analytics_row_count, 0)
        - s.staging_row_count
    )::BIGINT AS row_count_delta,
    (
        COALESCE(a.analytics_row_count, 0)
        = s.staging_row_count
    ) AS reconciled
FROM validation.staging_dataset_counts AS s
LEFT JOIN validation.analytics_dataset_counts AS a
  ON a.ingestion_batch_id = s.ingestion_batch_id
 AND a.dataset_name = s.dataset_name;

COMMIT;
