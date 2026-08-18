BEGIN;

CREATE OR REPLACE VIEW reporting.vw_observation_cutoff AS
SELECT
    b.ingestion_batch_id,
    b.analytics_build_run_id,
    cutoff.observation_cutoff_at
FROM analytics.build_runs b

CROSS JOIN LATERAL (
    SELECT
        e.occurred_at AS observation_cutoff_at
    FROM analytics.fact_product_event e
    WHERE e.ingestion_batch_id = b.ingestion_batch_id
      AND e.analytics_build_run_id = b.analytics_build_run_id
    ORDER BY e.occurred_at DESC
    LIMIT 1
) cutoff

WHERE b.status = 'succeeded';


COMMENT ON VIEW reporting.vw_observation_cutoff IS
    'One row per successful analytics build containing the latest observed product-event timestamp. Used as the canonical reporting observation cutoff for cohort maturity and experiment analysis-window eligibility. Implemented using an indexed latest-event lookup rather than a full fact-table aggregate.';

COMMIT;
