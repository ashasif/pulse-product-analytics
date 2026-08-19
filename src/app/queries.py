"""Approved reporting-layer queries for the Pulse application.

Business-facing database access must remain inside reporting.*.

Canonical rates are recomputed from canonical numerators and denominators
when aggregating across reporting grains. Precomputed rate fields must not
be averaged across cohorts or segments.
"""

from __future__ import annotations


REPORTING_CONTEXT_SQL = """
SELECT
    ingestion_batch_id,
    analytics_build_run_id,
    observation_cutoff_at
FROM reporting.vw_observation_cutoff
ORDER BY analytics_build_run_id DESC
LIMIT 1
"""


SUPPORTED_METRICS_SQL = """
SELECT
    metric_key,
    metric_name,
    metric_domain,
    metric_grain,
    metric_unit,
    support_status,
    definition,
    denominator_definition,
    caveat
FROM reporting.metric_definitions
WHERE support_status = 'supported'
ORDER BY metric_domain, metric_name
"""


OVERVIEW_PRODUCT_SQL = """
SELECT
    SUM(installation_count)::bigint AS installation_count,
    SUM(signup_count)::bigint AS signup_count,
    SUM(session_count)::bigint AS session_count,
    SUM(feature_use_event_count)::bigint AS feature_use_event_count,
    SUM(trial_start_count)::bigint AS trial_start_count,
    SUM(paid_subscription_start_count)::bigint
        AS paid_subscription_start_count
FROM reporting.vw_daily_product_kpis
WHERE analytics_build_run_id = %(analytics_build_run_id)s
"""


OVERVIEW_FUNNEL_SQL = """
WITH installation AS (
    SELECT
        SUM(installation_count)::bigint AS installation_count,
        SUM(installations_with_signup)::bigint
            AS installations_with_signup
    FROM reporting.vw_installation_cohort_funnel
    WHERE analytics_build_run_id = %(analytics_build_run_id)s
),
signup AS (
    SELECT
        SUM(registered_user_count)::bigint
            AS registered_user_count,
        SUM(onboarding_started_user_count)::bigint
            AS onboarding_started_user_count,
        SUM(onboarding_completed_user_count)::bigint
            AS onboarding_completed_user_count
    FROM reporting.vw_signup_cohort_funnel
    WHERE analytics_build_run_id = %(analytics_build_run_id)s
),
trial AS (
    SELECT
        SUM(mature_trial_count)::bigint
            AS mature_trial_count,
        SUM(mature_trial_paid_conversion_count)::bigint
            AS mature_trial_paid_conversion_count
    FROM reporting.vw_trial_conversion_cohorts
    WHERE analytics_build_run_id = %(analytics_build_run_id)s
)
SELECT
    installation.installation_count,
    installation.installations_with_signup,
    installation.installations_with_signup::numeric
        / NULLIF(installation.installation_count, 0)
        AS install_to_signup_rate,

    signup.registered_user_count,
    signup.onboarding_started_user_count,
    signup.onboarding_completed_user_count,

    signup.onboarding_started_user_count::numeric
        / NULLIF(signup.registered_user_count, 0)
        AS onboarding_start_rate,

    signup.onboarding_completed_user_count::numeric
        / NULLIF(signup.registered_user_count, 0)
        AS onboarding_completion_rate,

    trial.mature_trial_count,
    trial.mature_trial_paid_conversion_count,

    trial.mature_trial_paid_conversion_count::numeric
        / NULLIF(trial.mature_trial_count, 0)
        AS trial_to_paid_conversion_rate

FROM installation
CROSS JOIN signup
CROSS JOIN trial
"""


OVERVIEW_REVENUE_SQL = """
SELECT
    SUM(payment_attempt_count)::bigint
        AS payment_attempt_count,

    SUM(successful_payment_count)::bigint
        AS successful_payment_count,

    SUM(failed_payment_count)::bigint
        AS failed_payment_count,

    SUM(failed_payment_count)::numeric
        / NULLIF(SUM(payment_attempt_count), 0)
        AS payment_failure_rate,

    SUM(successful_payment_revenue_gbp)::numeric
        AS successful_payment_revenue_gbp,

    SUM(renewal_attempt_count)::bigint
        AS renewal_attempt_count,

    SUM(successful_renewal_count)::bigint
        AS successful_renewal_count,

    SUM(successful_renewal_count)::numeric
        / NULLIF(SUM(renewal_attempt_count), 0)
        AS renewal_success_rate

FROM reporting.vw_daily_subscription_revenue
WHERE analytics_build_run_id = %(analytics_build_run_id)s
"""


RETENTION_SUMMARY_SQL = """
SELECT
    SUM(paid_subscription_count)::bigint
        AS paid_subscription_count,

    SUM(mature_d30_count)::bigint AS mature_d30_count,
    SUM(retained_d30_count)::bigint AS retained_d30_count,
    SUM(retained_d30_count)::numeric
        / NULLIF(SUM(mature_d30_count), 0)
        AS paid_retention_d30,

    SUM(mature_d90_count)::bigint AS mature_d90_count,
    SUM(retained_d90_count)::bigint AS retained_d90_count,
    SUM(retained_d90_count)::numeric
        / NULLIF(SUM(mature_d90_count), 0)
        AS paid_retention_d90,

    SUM(mature_d180_count)::bigint AS mature_d180_count,
    SUM(retained_d180_count)::bigint AS retained_d180_count,
    SUM(retained_d180_count)::numeric
        / NULLIF(SUM(mature_d180_count), 0)
        AS paid_retention_d180,

    SUM(mature_d365_count)::bigint AS mature_d365_count,
    SUM(retained_d365_count)::bigint AS retained_d365_count,
    SUM(retained_d365_count)::numeric
        / NULLIF(SUM(mature_d365_count), 0)
        AS paid_retention_d365

FROM reporting.vw_paid_retention_cohorts
WHERE analytics_build_run_id = %(analytics_build_run_id)s
"""


MONTHLY_PRODUCT_TREND_SQL = """
SELECT
    date_trunc('month', full_date)::date AS month,

    SUM(installation_count)::bigint
        AS installation_count,

    SUM(signup_count)::bigint
        AS signup_count,

    SUM(session_count)::bigint
        AS session_count,

    SUM(feature_use_event_count)::bigint
        AS feature_use_event_count,

    SUM(trial_start_count)::bigint
        AS trial_start_count,

    SUM(paid_subscription_start_count)::bigint
        AS paid_subscription_start_count

FROM reporting.vw_daily_product_kpis

WHERE analytics_build_run_id = %(analytics_build_run_id)s

GROUP BY
    date_trunc('month', full_date)::date

ORDER BY month
"""


ACQUISITION_CHANNEL_SQL = """
SELECT
    acquisition_channel,

    SUM(marketing_spend_gbp)::numeric
        AS marketing_spend_gbp,

    COALESCE(SUM(impressions), 0)::bigint
        AS impressions,

    COALESCE(SUM(clicks), 0)::bigint
        AS clicks,

    SUM(installation_count)::bigint
        AS installation_count,

    SUM(installations_with_signup)::bigint
        AS installations_with_signup,

    SUM(installations_with_signup)::numeric
        / NULLIF(SUM(installation_count), 0)
        AS install_to_signup_rate,

    SUM(clicks)::numeric
        / NULLIF(SUM(impressions), 0)
        AS click_through_rate,

    SUM(marketing_spend_gbp)::numeric
        / NULLIF(SUM(clicks), 0)
        AS cost_per_click_gbp,

    SUM(marketing_spend_gbp)::numeric
        / NULLIF(SUM(installation_count), 0)
        AS cost_per_install_gbp

FROM reporting.vw_weekly_acquisition_performance

WHERE analytics_build_run_id = %(analytics_build_run_id)s

GROUP BY acquisition_channel

ORDER BY installation_count DESC, acquisition_channel
"""


PLATFORM_FUNNEL_SQL = """
WITH install AS (
    SELECT
        platform,
        SUM(installation_count)::bigint
            AS installation_count,
        SUM(installations_with_signup)::bigint
            AS installations_with_signup
    FROM reporting.vw_installation_cohort_funnel
    WHERE analytics_build_run_id = %(analytics_build_run_id)s
    GROUP BY platform
),
signup AS (
    SELECT
        platform,
        SUM(registered_user_count)::bigint
            AS registered_user_count,
        SUM(onboarding_started_user_count)::bigint
            AS onboarding_started_user_count,
        SUM(onboarding_completed_user_count)::bigint
            AS onboarding_completed_user_count
    FROM reporting.vw_signup_cohort_funnel
    WHERE analytics_build_run_id = %(analytics_build_run_id)s
    GROUP BY platform
)
SELECT
    install.platform,
    install.installation_count,
    install.installations_with_signup,

    install.installations_with_signup::numeric
        / NULLIF(install.installation_count, 0)
        AS install_to_signup_rate,

    signup.registered_user_count,
    signup.onboarding_started_user_count,
    signup.onboarding_completed_user_count,

    signup.onboarding_started_user_count::numeric
        / NULLIF(signup.registered_user_count, 0)
        AS onboarding_start_rate,

    signup.onboarding_completed_user_count::numeric
        / NULLIF(signup.registered_user_count, 0)
        AS onboarding_completion_rate

FROM install

JOIN signup
  ON signup.platform = install.platform

ORDER BY install.platform
"""


FEATURE_SUMMARY_SQL = """
SELECT
    feature_name,

    SUM(feature_use_event_count)::bigint
        AS feature_use_event_count,

    SUM(feature_installation_count)::bigint
        AS feature_installation_count_days,

    SUM(feature_user_count)::bigint
        AS feature_user_days,

    SUM(feature_session_count)::bigint
        AS feature_session_count,

    SUM(feature_use_event_count)::numeric
        / NULLIF(
            SUM(SUM(feature_use_event_count)) OVER (),
            0
        )
        AS feature_use_share

FROM reporting.vw_daily_feature_engagement

WHERE analytics_build_run_id = %(analytics_build_run_id)s

GROUP BY feature_name

ORDER BY feature_use_event_count DESC, feature_name
"""


MONTHLY_ENGAGEMENT_SQL = """
SELECT
    date_trunc('month', full_date)::date AS month,

    SUM(session_count)::bigint
        AS session_count,

    SUM(feature_use_event_count)::bigint
        AS feature_use_event_count,

    SUM(paywall_view_count)::bigint
        AS paywall_view_count,

    SUM(trial_start_count)::bigint
        AS trial_start_count

FROM reporting.vw_daily_product_kpis

WHERE analytics_build_run_id = %(analytics_build_run_id)s

GROUP BY
    date_trunc('month', full_date)::date

ORDER BY month
"""


MONTHLY_REVENUE_SQL = """
SELECT
    date_trunc('month', full_date)::date AS month,

    SUM(successful_payment_revenue_gbp)::numeric
        AS successful_payment_revenue_gbp,

    SUM(payment_attempt_count)::bigint
        AS payment_attempt_count,

    SUM(failed_payment_count)::bigint
        AS failed_payment_count,

    SUM(failed_payment_count)::numeric
        / NULLIF(SUM(payment_attempt_count), 0)
        AS payment_failure_rate,

    SUM(renewal_attempt_count)::bigint
        AS renewal_attempt_count,

    SUM(successful_renewal_count)::bigint
        AS successful_renewal_count,

    SUM(successful_renewal_count)::numeric
        / NULLIF(SUM(renewal_attempt_count), 0)
        AS renewal_success_rate

FROM reporting.vw_daily_subscription_revenue

WHERE analytics_build_run_id = %(analytics_build_run_id)s

GROUP BY
    date_trunc('month', full_date)::date

ORDER BY month
"""


TRIAL_CONVERSION_CHANNEL_SQL = """
SELECT
    acquisition_channel,

    SUM(trial_count)::bigint
        AS trial_count,

    SUM(mature_trial_count)::bigint
        AS mature_trial_count,

    SUM(immature_trial_count)::bigint
        AS immature_trial_count,

    SUM(mature_trial_paid_conversion_count)::bigint
        AS mature_trial_paid_conversion_count,

    SUM(mature_trial_paid_conversion_count)::numeric
        / NULLIF(SUM(mature_trial_count), 0)
        AS trial_to_paid_conversion_rate

FROM reporting.vw_trial_conversion_cohorts

WHERE analytics_build_run_id = %(analytics_build_run_id)s

GROUP BY acquisition_channel

ORDER BY mature_trial_count DESC, acquisition_channel
"""


RETENTION_CHANNEL_SQL = """
SELECT
    acquisition_channel,

    SUM(paid_subscription_count)::bigint
        AS paid_subscription_count,

    SUM(mature_d30_count)::bigint
        AS mature_d30_count,
    SUM(retained_d30_count)::numeric
        / NULLIF(SUM(mature_d30_count), 0)
        AS paid_retention_d30,

    SUM(mature_d90_count)::bigint
        AS mature_d90_count,
    SUM(retained_d90_count)::numeric
        / NULLIF(SUM(mature_d90_count), 0)
        AS paid_retention_d90,

    SUM(mature_d180_count)::bigint
        AS mature_d180_count,
    SUM(retained_d180_count)::numeric
        / NULLIF(SUM(mature_d180_count), 0)
        AS paid_retention_d180,

    SUM(mature_d365_count)::bigint
        AS mature_d365_count,
    SUM(retained_d365_count)::numeric
        / NULLIF(SUM(mature_d365_count), 0)
        AS paid_retention_d365

FROM reporting.vw_paid_retention_cohorts

WHERE analytics_build_run_id = %(analytics_build_run_id)s

GROUP BY acquisition_channel

ORDER BY paid_subscription_count DESC, acquisition_channel
"""


APP_QUERY_REGISTRY: dict[str, str] = {
    "reporting_context": REPORTING_CONTEXT_SQL,
    "supported_metrics": SUPPORTED_METRICS_SQL,
    "overview_product": OVERVIEW_PRODUCT_SQL,
    "overview_funnel": OVERVIEW_FUNNEL_SQL,
    "overview_revenue": OVERVIEW_REVENUE_SQL,
    "retention_summary": RETENTION_SUMMARY_SQL,
    "monthly_product_trend": MONTHLY_PRODUCT_TREND_SQL,
    "acquisition_channel": ACQUISITION_CHANNEL_SQL,
    "platform_funnel": PLATFORM_FUNNEL_SQL,
    "feature_summary": FEATURE_SUMMARY_SQL,
    "monthly_engagement": MONTHLY_ENGAGEMENT_SQL,
    "monthly_revenue": MONTHLY_REVENUE_SQL,
    "trial_conversion_channel": TRIAL_CONVERSION_CHANNEL_SQL,
    "retention_channel": RETENTION_CHANNEL_SQL,
}