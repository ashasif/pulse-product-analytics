CREATE OR REPLACE VIEW reporting.vw_experiment_assignment_outcomes AS
WITH assignment_base AS (
    SELECT
        a.ingestion_batch_id,
        a.analytics_build_run_id,
        a.experiment_assignment_key,
        a.assignment_id,
        a.experiment_key,
        e.experiment_id,
        e.experiment_name,
        e.primary_metric,
        e.secondary_metric,
        e.commercial_metric,
        e.guardrail_metric,
        e.analysis_window_days,

        a.user_key,
        a.installation_key,
        a.variant,
        a.allocation_probability,
        a.assignment_at,
        a.exposed_at,

        (a.exposed_at IS NOT NULL) AS is_exposed,

        CASE
            WHEN a.exposed_at IS NULL
                THEN NULL
            ELSE
                EXTRACT(
                    EPOCH FROM (
                        a.exposed_at - a.assignment_at
                    )
                )
        END AS exposure_delay_seconds,

        u.signed_up_at,
        u.onboarding_completed_at,

        i.platform,
        i.acquisition_channel,
        i.country_code,

        c.observation_cutoff_at,

        (
            a.assignment_at
            + make_interval(days => e.analysis_window_days)
            <= c.observation_cutoff_at
        ) AS analysis_window_mature

    FROM analytics.fact_experiment_assignment a

    JOIN analytics.dim_experiment e
      ON e.experiment_key = a.experiment_key

    JOIN analytics.dim_user u
      ON u.user_key = a.user_key

    JOIN analytics.dim_installation i
      ON i.installation_key = a.installation_key

    JOIN reporting.vw_observation_cutoff c
      ON c.ingestion_batch_id = a.ingestion_batch_id
     AND c.analytics_build_run_id = a.analytics_build_run_id
),
event_outcomes AS (
    SELECT
        b.experiment_assignment_key,

        COUNT(*) FILTER (
            WHERE p.event_name = 'session_started'
              AND p.occurred_at <
                  b.assignment_at + INTERVAL '7 days'
        )::bigint AS session_count_7d,

        COUNT(*) FILTER (
            WHERE p.event_name = 'feature_used'
              AND p.occurred_at <
                  b.assignment_at + INTERVAL '7 days'
        )::bigint AS feature_use_event_count_7d,

        COUNT(*) FILTER (
            WHERE p.event_name = 'paywall_viewed'
              AND p.occurred_at <
                  b.assignment_at + INTERVAL '7 days'
        )::bigint AS paywall_view_count_7d,

        COUNT(*) FILTER (
            WHERE p.event_name = 'trial_started'
              AND p.occurred_at <
                  b.assignment_at + INTERVAL '7 days'
        ) > 0 AS trial_started_7d,

        COUNT(*) FILTER (
            WHERE p.event_name = 'trial_started'
              AND p.occurred_at <
                  b.assignment_at + INTERVAL '14 days'
        ) > 0 AS trial_started_14d,

        COUNT(*) FILTER (
            WHERE p.event_name = 'subscription_started'
              AND p.occurred_at <
                  b.assignment_at + INTERVAL '14 days'
        ) > 0 AS paid_started_14d,

        COUNT(*) FILTER (
            WHERE p.event_name = 'subscription_started'
              AND p.occurred_at <
                  b.assignment_at + INTERVAL '30 days'
        ) > 0 AS paid_started_30d,

        COUNT(*) FILTER (
            WHERE p.event_name IN (
                'cancellation_requested',
                'subscription_expired'
            )
              AND p.occurred_at <
                  b.assignment_at + INTERVAL '30 days'
        ) > 0 AS cancellation_or_expiry_30d,

        COUNT(*) FILTER (
            WHERE p.event_name = 'trial_started'
              AND p.occurred_at <
                  b.assignment_at
                  + make_interval(
                      days => b.analysis_window_days
                  )
        ) > 0 AS trial_started_analysis_window,

        COUNT(*) FILTER (
            WHERE p.event_name = 'subscription_started'
              AND p.occurred_at <
                  b.assignment_at
                  + make_interval(
                      days => b.analysis_window_days
                  )
        ) > 0 AS paid_started_analysis_window

    FROM assignment_base b

    LEFT JOIN analytics.fact_product_event p
      ON p.ingestion_batch_id = b.ingestion_batch_id
     AND p.analytics_build_run_id = b.analytics_build_run_id
     AND p.user_key = b.user_key
     AND p.occurred_at >= b.assignment_at
     AND p.occurred_at <
         b.assignment_at + INTERVAL '30 days'

    GROUP BY
        b.experiment_assignment_key
),
revenue_outcomes AS (
    SELECT
        b.experiment_assignment_key,

        COALESCE(
            SUM(t.amount_gbp) FILTER (
                WHERE t.payment_status = 'succeeded'
                  AND t.attempted_at <
                      b.assignment_at + INTERVAL '30 days'
            ),
            0
        ) AS successful_revenue_gbp_30d,

        COALESCE(
            SUM(t.amount_gbp) FILTER (
                WHERE t.payment_status = 'succeeded'
                  AND t.attempted_at <
                      b.assignment_at
                      + make_interval(
                          days => b.analysis_window_days
                      )
            ),
            0
        ) AS successful_revenue_gbp_analysis_window

    FROM assignment_base b

    LEFT JOIN analytics.fact_subscription_transaction t
      ON t.ingestion_batch_id = b.ingestion_batch_id
     AND t.analytics_build_run_id = b.analytics_build_run_id
     AND t.user_key = b.user_key
     AND t.attempted_at >= b.assignment_at
     AND t.attempted_at <
         b.assignment_at + INTERVAL '30 days'

    GROUP BY
        b.experiment_assignment_key
)
SELECT
    b.*,

    (
        b.onboarding_completed_at IS NOT NULL
        AND b.onboarding_completed_at >= b.assignment_at
        AND b.onboarding_completed_at <
            b.assignment_at + INTERVAL '48 hours'
    ) AS onboarding_completed_48h,

    COALESCE(e.session_count_7d, 0)::bigint
        AS session_count_7d,

    COALESCE(e.feature_use_event_count_7d, 0)::bigint
        AS feature_use_event_count_7d,

    COALESCE(e.feature_use_event_count_7d, 0) > 0
        AS feature_used_7d,

    COALESCE(e.paywall_view_count_7d, 0)::bigint
        AS paywall_view_count_7d,

    COALESCE(e.trial_started_7d, false)
        AS trial_started_7d,

    COALESCE(e.trial_started_14d, false)
        AS trial_started_14d,

    COALESCE(e.paid_started_14d, false)
        AS paid_started_14d,

    COALESCE(e.paid_started_30d, false)
        AS paid_started_30d,

    COALESCE(
        e.cancellation_or_expiry_30d,
        false
    ) AS cancellation_or_expiry_30d,

    COALESCE(
        e.trial_started_analysis_window,
        false
    ) AS trial_started_analysis_window,

    COALESCE(
        e.paid_started_analysis_window,
        false
    ) AS paid_started_analysis_window,

    COALESCE(
        r.successful_revenue_gbp_30d,
        0
    )::numeric AS successful_revenue_gbp_30d,

    COALESCE(
        r.successful_revenue_gbp_analysis_window,
        0
    )::numeric AS successful_revenue_gbp_analysis_window

FROM assignment_base b

LEFT JOIN event_outcomes e
  ON e.experiment_assignment_key =
     b.experiment_assignment_key

LEFT JOIN revenue_outcomes r
  ON r.experiment_assignment_key =
     b.experiment_assignment_key;


COMMENT ON VIEW reporting.vw_experiment_assignment_outcomes IS
    'One row per experiment assignment with generic assignment-based outcome primitives. It does not claim statistical significance or causal lift.';


CREATE OR REPLACE VIEW reporting.vw_experiment_variant_summary AS
SELECT
    ingestion_batch_id,
    analytics_build_run_id,
    experiment_key,
    experiment_id,
    experiment_name,
    primary_metric,
    secondary_metric,
    commercial_metric,
    guardrail_metric,
    analysis_window_days,
    variant,

    COUNT(*)::bigint AS assigned_user_count,

    COUNT(*) FILTER (
        WHERE is_exposed
    )::bigint AS exposed_user_count,

    COUNT(*) FILTER (
        WHERE is_exposed
    )::numeric
    / NULLIF(COUNT(*), 0)::numeric
        AS exposure_rate,

    AVG(allocation_probability)
        AS average_allocation_probability,

    COUNT(*) FILTER (
        WHERE onboarding_completed_48h
    )::bigint AS onboarding_completed_48h_count,

    COUNT(*) FILTER (
        WHERE onboarding_completed_48h
    )::numeric
    / NULLIF(COUNT(*), 0)::numeric
        AS onboarding_completion_48h_rate,

    COUNT(*) FILTER (
        WHERE feature_used_7d
    )::bigint AS feature_used_7d_count,

    COUNT(*) FILTER (
        WHERE feature_used_7d
    )::numeric
    / NULLIF(COUNT(*), 0)::numeric
        AS overall_feature_use_7d_rate,

    COUNT(*) FILTER (
        WHERE trial_started_7d
    )::bigint AS trial_started_7d_count,

    COUNT(*) FILTER (
        WHERE trial_started_7d
    )::numeric
    / NULLIF(COUNT(*), 0)::numeric
        AS trial_start_conversion_7d,

    COUNT(*) FILTER (
        WHERE paid_started_14d
    )::bigint AS paid_started_14d_count,

    COUNT(*) FILTER (
        WHERE paid_started_14d
    )::numeric
    / NULLIF(COUNT(*), 0)::numeric
        AS paid_conversion_14d,

    SUM(successful_revenue_gbp_30d)
        AS successful_revenue_gbp_30d,

    SUM(successful_revenue_gbp_30d)
    / NULLIF(COUNT(*), 0)::numeric
        AS revenue_per_assigned_user_30d,

    COUNT(*) FILTER (
        WHERE cancellation_or_expiry_30d
    )::bigint AS cancellation_or_expiry_30d_count,

    COUNT(*) FILTER (
        WHERE cancellation_or_expiry_30d
    )::numeric
    / NULLIF(COUNT(*), 0)::numeric
        AS cancellation_or_expiry_30d_rate,

    AVG(session_count_7d::numeric)
        AS average_session_count_7d,

    AVG(feature_use_event_count_7d::numeric)
        AS average_feature_use_event_count_7d

FROM reporting.vw_experiment_assignment_outcomes

GROUP BY
    ingestion_batch_id,
    analytics_build_run_id,
    experiment_key,
    experiment_id,
    experiment_name,
    primary_metric,
    secondary_metric,
    commercial_metric,
    guardrail_metric,
    analysis_window_days,
    variant;


COMMENT ON VIEW reporting.vw_experiment_variant_summary IS
    'Experiment variant summary built from assignment-based outcome primitives. Provides descriptive comparison only; no statistical-significance or causal-inference claim is made.';