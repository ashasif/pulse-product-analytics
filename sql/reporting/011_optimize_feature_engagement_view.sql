BEGIN;

CREATE OR REPLACE VIEW reporting.vw_daily_feature_engagement AS
WITH feature_daily AS (
    SELECT
        e.ingestion_batch_id,
        e.analytics_build_run_id,
        e.occurred_date_key AS date_key,
        e.feature_name,

        COUNT(*) AS feature_use_event_count,

        COUNT(
            DISTINCT e.installation_key
        ) AS feature_installation_count,

        COUNT(
            DISTINCT e.user_key
        ) FILTER (
            WHERE e.user_key IS NOT NULL
        ) AS feature_user_count,

        COUNT(
            DISTINCT e.session_id
        ) FILTER (
            WHERE e.session_id IS NOT NULL
        ) AS feature_session_count

    FROM analytics.fact_product_event e

    WHERE e.event_name = 'feature_used'
      AND e.feature_name IS NOT NULL

    GROUP BY
        e.ingestion_batch_id,
        e.analytics_build_run_id,
        e.occurred_date_key,
        e.feature_name
)

SELECT
    f.ingestion_batch_id,
    f.analytics_build_run_id,
    f.date_key,
    d.full_date,
    f.feature_name,
    f.feature_use_event_count,
    f.feature_installation_count,
    f.feature_user_count,
    f.feature_session_count

FROM feature_daily f

JOIN analytics.dim_date d
  ON d.date_key = f.date_key;


COMMENT ON VIEW reporting.vw_daily_feature_engagement IS
    'Daily feature-use engagement at ingestion batch, analytics build, date and feature grain. Aggregates feature events before joining the date dimension and is supported by the Step 7 partial covering reporting index.';

COMMIT;