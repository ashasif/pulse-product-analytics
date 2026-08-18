BEGIN;

CREATE INDEX IF NOT EXISTS ix_fact_product_event_daily_reporting
ON analytics.fact_product_event (
    ingestion_batch_id,
    analytics_build_run_id,
    occurred_date_key,
    user_key
)
INCLUDE (
    event_name,
    installation_key
);


COMMENT ON INDEX analytics.ix_fact_product_event_daily_reporting IS
    'Reporting-support covering index for daily product KPI aggregation. Evidence-backed in Phase 3 Step 7: removes the full-history external sort and enables an index-only aggregation path.';


CREATE INDEX IF NOT EXISTS ix_fact_product_event_feature_reporting
ON analytics.fact_product_event (
    ingestion_batch_id,
    analytics_build_run_id,
    occurred_date_key,
    feature_name,
    installation_key
)
INCLUDE (
    user_key,
    session_id
)
WHERE event_name = 'feature_used'
  AND feature_name IS NOT NULL;


COMMENT ON INDEX analytics.ix_fact_product_event_feature_reporting IS
    'Partial covering index for feature-engagement reporting. Contains only feature_used rows with a feature name and supports index-only daily feature aggregation.';

COMMIT;