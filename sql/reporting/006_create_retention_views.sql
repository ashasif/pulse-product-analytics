CREATE OR REPLACE VIEW reporting.vw_observation_cutoff AS
SELECT
    b.ingestion_batch_id,
    b.analytics_build_run_id,
    MAX(e.occurred_at) AS observation_cutoff_at

FROM analytics.build_runs b

JOIN analytics.fact_product_event e
  ON e.ingestion_batch_id = b.ingestion_batch_id
 AND e.analytics_build_run_id = b.analytics_build_run_id

WHERE b.status = 'succeeded'

GROUP BY
    b.ingestion_batch_id,
    b.analytics_build_run_id;


COMMENT ON VIEW reporting.vw_observation_cutoff IS
    'Latest observed product-event timestamp for each successful analytics build. Used to prevent immature cohorts from entering retention and conversion denominators.';


CREATE OR REPLACE VIEW reporting.vw_trial_conversion_cohorts AS
WITH trial_base AS (
    SELECT
        s.ingestion_batch_id,
        s.analytics_build_run_id,

        date_trunc(
            'month',
            s.trial_started_at
        )::date AS trial_cohort_month,

        s.billing_period,

        i.platform,
        i.acquisition_channel,

        s.subscription_key,
        s.trial_started_at,
        s.trial_ends_at,
        s.subscription_started_at,

        c.observation_cutoff_at,

        (
            s.trial_ends_at <= c.observation_cutoff_at
        ) AS is_mature_trial,

        (
            s.subscription_started_at IS NOT NULL
            AND
            s.subscription_started_at <= c.observation_cutoff_at
        ) AS converted_to_paid

    FROM analytics.fact_subscription s

    JOIN analytics.dim_installation i
      ON i.installation_key = s.installation_key

    JOIN reporting.vw_observation_cutoff c
      ON c.ingestion_batch_id = s.ingestion_batch_id
     AND c.analytics_build_run_id = s.analytics_build_run_id
)
SELECT
    ingestion_batch_id,
    analytics_build_run_id,
    trial_cohort_month,
    billing_period,
    platform,
    acquisition_channel,

    COUNT(*)::bigint AS trial_count,

    COUNT(*) FILTER (
        WHERE is_mature_trial
    )::bigint AS mature_trial_count,

    COUNT(*) FILTER (
        WHERE NOT is_mature_trial
    )::bigint AS immature_trial_count,

    COUNT(*) FILTER (
        WHERE is_mature_trial
          AND converted_to_paid
    )::bigint AS mature_trial_paid_conversion_count,

    CASE
        WHEN COUNT(*) FILTER (
            WHERE is_mature_trial
        ) = 0
            THEN NULL
        ELSE
            COUNT(*) FILTER (
                WHERE is_mature_trial
                  AND converted_to_paid
            )::numeric
            /
            COUNT(*) FILTER (
                WHERE is_mature_trial
            )::numeric
    END AS trial_to_paid_conversion_rate

FROM trial_base

GROUP BY
    ingestion_batch_id,
    analytics_build_run_id,
    trial_cohort_month,
    billing_period,
    platform,
    acquisition_channel;


COMMENT ON VIEW reporting.vw_trial_conversion_cohorts IS
    'Monthly trial cohorts with mature-trial denominator control. Immature trials are excluded from trial-to-paid conversion rates.';


CREATE OR REPLACE VIEW reporting.vw_paid_subscription_retention_base AS
SELECT
    s.ingestion_batch_id,
    s.analytics_build_run_id,
    s.subscription_key,
    s.subscription_id,
    s.user_key,
    s.installation_key,

    date_trunc(
        'month',
        s.subscription_started_at
    )::date AS paid_cohort_month,

    s.subscription_started_at,
    s.billing_period,
    s.price_gbp,
    s.status,
    s.expired_at,
    s.end_reason,

    i.platform,
    i.acquisition_channel,

    c.observation_cutoff_at,

    (
        s.subscription_started_at + INTERVAL '30 days'
        <= c.observation_cutoff_at
    ) AS eligible_d30,

    (
        s.subscription_started_at + INTERVAL '30 days'
        <= c.observation_cutoff_at
        AND (
            s.expired_at IS NULL
            OR s.expired_at >
               s.subscription_started_at + INTERVAL '30 days'
        )
    ) AS retained_d30,

    (
        s.subscription_started_at + INTERVAL '90 days'
        <= c.observation_cutoff_at
    ) AS eligible_d90,

    (
        s.subscription_started_at + INTERVAL '90 days'
        <= c.observation_cutoff_at
        AND (
            s.expired_at IS NULL
            OR s.expired_at >
               s.subscription_started_at + INTERVAL '90 days'
        )
    ) AS retained_d90,

    (
        s.subscription_started_at + INTERVAL '180 days'
        <= c.observation_cutoff_at
    ) AS eligible_d180,

    (
        s.subscription_started_at + INTERVAL '180 days'
        <= c.observation_cutoff_at
        AND (
            s.expired_at IS NULL
            OR s.expired_at >
               s.subscription_started_at + INTERVAL '180 days'
        )
    ) AS retained_d180,

    (
        s.subscription_started_at + INTERVAL '365 days'
        <= c.observation_cutoff_at
    ) AS eligible_d365,

    (
        s.subscription_started_at + INTERVAL '365 days'
        <= c.observation_cutoff_at
        AND (
            s.expired_at IS NULL
            OR s.expired_at >
               s.subscription_started_at + INTERVAL '365 days'
        )
    ) AS retained_d365

FROM analytics.fact_subscription s

JOIN analytics.dim_installation i
  ON i.installation_key = s.installation_key

JOIN reporting.vw_observation_cutoff c
  ON c.ingestion_batch_id = s.ingestion_batch_id
 AND c.analytics_build_run_id = s.analytics_build_run_id

WHERE s.subscription_started_at IS NOT NULL;


COMMENT ON VIEW reporting.vw_paid_subscription_retention_base IS
    'One row per paid subscription containing maturity-controlled D30, D90, D180 and D365 retention flags.';


CREATE OR REPLACE VIEW reporting.vw_paid_retention_cohorts AS
SELECT
    ingestion_batch_id,
    analytics_build_run_id,
    paid_cohort_month,
    billing_period,
    platform,
    acquisition_channel,

    COUNT(*)::bigint AS paid_subscription_count,

    COUNT(*) FILTER (
        WHERE eligible_d30
    )::bigint AS mature_d30_count,

    COUNT(*) FILTER (
        WHERE retained_d30
    )::bigint AS retained_d30_count,

    CASE
        WHEN COUNT(*) FILTER (
            WHERE eligible_d30
        ) = 0
            THEN NULL
        ELSE
            COUNT(*) FILTER (
                WHERE retained_d30
            )::numeric
            /
            COUNT(*) FILTER (
                WHERE eligible_d30
            )::numeric
    END AS paid_retention_d30,

    COUNT(*) FILTER (
        WHERE eligible_d90
    )::bigint AS mature_d90_count,

    COUNT(*) FILTER (
        WHERE retained_d90
    )::bigint AS retained_d90_count,

    CASE
        WHEN COUNT(*) FILTER (
            WHERE eligible_d90
        ) = 0
            THEN NULL
        ELSE
            COUNT(*) FILTER (
                WHERE retained_d90
            )::numeric
            /
            COUNT(*) FILTER (
                WHERE eligible_d90
            )::numeric
    END AS paid_retention_d90,

    COUNT(*) FILTER (
        WHERE eligible_d180
    )::bigint AS mature_d180_count,

    COUNT(*) FILTER (
        WHERE retained_d180
    )::bigint AS retained_d180_count,

    CASE
        WHEN COUNT(*) FILTER (
            WHERE eligible_d180
        ) = 0
            THEN NULL
        ELSE
            COUNT(*) FILTER (
                WHERE retained_d180
            )::numeric
            /
            COUNT(*) FILTER (
                WHERE eligible_d180
            )::numeric
    END AS paid_retention_d180,

    COUNT(*) FILTER (
        WHERE eligible_d365
    )::bigint AS mature_d365_count,

    COUNT(*) FILTER (
        WHERE retained_d365
    )::bigint AS retained_d365_count,

    CASE
        WHEN COUNT(*) FILTER (
            WHERE eligible_d365
        ) = 0
            THEN NULL
        ELSE
            COUNT(*) FILTER (
                WHERE retained_d365
            )::numeric
            /
            COUNT(*) FILTER (
                WHERE eligible_d365
            )::numeric
    END AS paid_retention_d365

FROM reporting.vw_paid_subscription_retention_base

GROUP BY
    ingestion_batch_id,
    analytics_build_run_id,
    paid_cohort_month,
    billing_period,
    platform,
    acquisition_channel;


COMMENT ON VIEW reporting.vw_paid_retention_cohorts IS
    'Monthly paid subscription cohorts with explicit observation maturity controls for D30, D90, D180 and D365 retention.';