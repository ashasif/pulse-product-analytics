-- Phase 6 predictive analytics:
-- row-level canonical trial-conversion contract.
--
-- This view does not introduce a new KPI. It exposes the same trial-maturity
-- and paid-conversion semantics already used by
-- reporting.vw_trial_conversion_cohorts at subscription grain.
--
-- Post-outcome subscription state is deliberately not exposed. Downstream ML
-- code receives only the canonical label plus information that can be treated
-- as prediction-time context.

CREATE OR REPLACE VIEW reporting.vw_trial_conversion_prediction_base AS
SELECT
    s.ingestion_batch_id,
    s.analytics_build_run_id,
    s.subscription_key,
    s.user_key,
    s.installation_key,
    s.billing_period,
    s.price_gbp,

    i.platform,
    i.acquisition_channel,
    i.country_code,
    i.installed_at,

    u.signed_up_at,
    u.onboarding_started_at,
    u.onboarding_completed_at,

    s.trial_started_at,
    s.trial_ends_at,

    c.observation_cutoff_at,

    (
        s.trial_ends_at
        <= c.observation_cutoff_at
    ) AS is_mature_trial,

    (
        s.subscription_started_at IS NOT NULL
        AND s.subscription_started_at
            <= c.observation_cutoff_at
    ) AS converted_to_paid

FROM analytics.fact_subscription s

JOIN analytics.dim_installation i
    ON i.installation_key = s.installation_key
   AND i.ingestion_batch_id = s.ingestion_batch_id
   AND i.analytics_build_run_id = s.analytics_build_run_id

JOIN analytics.dim_user u
    ON u.user_key = s.user_key
   AND u.ingestion_batch_id = s.ingestion_batch_id
   AND u.analytics_build_run_id = s.analytics_build_run_id

JOIN reporting.vw_observation_cutoff c
    ON c.ingestion_batch_id = s.ingestion_batch_id
   AND c.analytics_build_run_id = s.analytics_build_run_id;


COMMENT ON VIEW reporting.vw_trial_conversion_prediction_base IS
'Phase 6 row-level trial-conversion contract. Trial maturity and converted_to_paid exactly mirror the canonical reporting trial-conversion semantics. The view intentionally excludes subscription status, paid-start timestamps, cancellation state, expiry state, renewal state and payment outcomes from its exposed columns.';