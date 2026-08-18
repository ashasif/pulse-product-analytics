CREATE OR REPLACE VIEW reporting.vw_installation_cohort_funnel AS
SELECT
    ingestion_batch_id,
    analytics_build_run_id,
    installed_date_key,
    installed_date,
    platform,
    acquisition_channel,
    country_code,

    COUNT(*)::bigint AS installation_count,

    COUNT(*) FILTER (
        WHERE has_signup
    )::bigint AS installations_with_signup,

    CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE
            COUNT(*) FILTER (
                WHERE has_signup
            )::numeric
            / COUNT(*)::numeric
    END AS install_to_signup_rate

FROM reporting.vw_installation_lifecycle
GROUP BY
    ingestion_batch_id,
    analytics_build_run_id,
    installed_date_key,
    installed_date,
    platform,
    acquisition_channel,
    country_code;


COMMENT ON VIEW reporting.vw_installation_cohort_funnel IS
    'Installation-cohort funnel at build, install date, platform, acquisition channel and country grain. Signup conversion is cohort aligned to installation date.';


CREATE OR REPLACE VIEW reporting.vw_signup_cohort_funnel AS
SELECT
    u.ingestion_batch_id,
    u.analytics_build_run_id,
    u.signed_up_date_key,
    d.full_date AS signed_up_date,

    i.platform,
    i.acquisition_channel,
    i.country_code,

    COUNT(*)::bigint AS registered_user_count,

    COUNT(*) FILTER (
        WHERE u.onboarding_started_at IS NOT NULL
    )::bigint AS onboarding_started_user_count,

    COUNT(*) FILTER (
        WHERE u.onboarding_completed_at IS NOT NULL
    )::bigint AS onboarding_completed_user_count,

    CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE
            COUNT(*) FILTER (
                WHERE u.onboarding_started_at IS NOT NULL
            )::numeric
            / COUNT(*)::numeric
    END AS onboarding_start_rate,

    CASE
        WHEN COUNT(*) = 0 THEN NULL
        ELSE
            COUNT(*) FILTER (
                WHERE u.onboarding_completed_at IS NOT NULL
            )::numeric
            / COUNT(*)::numeric
    END AS onboarding_completion_rate

FROM analytics.dim_user u

JOIN analytics.dim_installation i
  ON i.installation_key = u.installation_key

JOIN analytics.dim_date d
  ON d.date_key = u.signed_up_date_key

GROUP BY
    u.ingestion_batch_id,
    u.analytics_build_run_id,
    u.signed_up_date_key,
    d.full_date,
    i.platform,
    i.acquisition_channel,
    i.country_code;


COMMENT ON VIEW reporting.vw_signup_cohort_funnel IS
    'Registered-user cohort funnel at build, signup date, platform, acquisition channel and country grain. Onboarding rates use registered users as the denominator.';


CREATE OR REPLACE VIEW reporting.vw_weekly_acquisition_performance AS
WITH installation_daily AS (
    SELECT
        ingestion_batch_id,
        analytics_build_run_id,
        installed_date,
        acquisition_channel,

        COUNT(*)::bigint AS installation_count,

        COUNT(*) FILTER (
            WHERE has_signup
        )::bigint AS installations_with_signup

    FROM reporting.vw_installation_lifecycle

    GROUP BY
        ingestion_batch_id,
        analytics_build_run_id,
        installed_date,
        acquisition_channel
)
SELECT
    m.ingestion_batch_id,
    m.analytics_build_run_id,
    m.marketing_spend_key,
    m.marketing_spend_id,
    m.period_start,
    m.period_end,
    m.acquisition_channel,
    m.spend_type,
    m.campaign_type,
    m.currency,

    m.spend AS marketing_spend_gbp,
    m.impressions,
    m.clicks,

    COALESCE(
        SUM(i.installation_count),
        0
    )::bigint AS installation_count,

    COALESCE(
        SUM(i.installations_with_signup),
        0
    )::bigint AS installations_with_signup,

    CASE
        WHEN COALESCE(SUM(i.installation_count), 0) = 0
            THEN NULL
        ELSE
            COALESCE(
                SUM(i.installations_with_signup),
                0
            )::numeric
            / NULLIF(
                SUM(i.installation_count),
                0
            )
    END AS install_to_signup_rate,

    CASE
        WHEN m.impressions IS NULL
          OR m.impressions = 0
            THEN NULL
        ELSE
            m.clicks::numeric
            / m.impressions::numeric
    END AS click_through_rate,

    CASE
        WHEN m.clicks IS NULL
          OR m.clicks = 0
            THEN NULL
        ELSE
            m.spend
            / m.clicks::numeric
    END AS cost_per_click_gbp,

    CASE
        WHEN COALESCE(SUM(i.installation_count), 0) = 0
            THEN NULL
        ELSE
            m.spend
            / NULLIF(
                SUM(i.installation_count),
                0
            )::numeric
    END AS cost_per_install_gbp

FROM analytics.fact_marketing_spend m

LEFT JOIN installation_daily i
  ON i.ingestion_batch_id = m.ingestion_batch_id
 AND i.analytics_build_run_id = m.analytics_build_run_id
 AND i.acquisition_channel = m.acquisition_channel
 AND i.installed_date BETWEEN m.period_start AND m.period_end

GROUP BY
    m.ingestion_batch_id,
    m.analytics_build_run_id,
    m.marketing_spend_key,
    m.marketing_spend_id,
    m.period_start,
    m.period_end,
    m.acquisition_channel,
    m.spend_type,
    m.campaign_type,
    m.currency,
    m.spend,
    m.impressions,
    m.clicks;


COMMENT ON VIEW reporting.vw_weekly_acquisition_performance IS
    'One row per marketing-spend record with channel-period acquisition efficiency. Cost per install is channel-level and must not be interpreted as campaign-attributed CAC.';


CREATE OR REPLACE VIEW reporting.vw_daily_feature_engagement AS
SELECT
    e.ingestion_batch_id,
    e.analytics_build_run_id,
    e.occurred_date_key AS date_key,
    d.full_date,
    e.feature_name,

    COUNT(*)::bigint AS feature_use_event_count,

    COUNT(DISTINCT e.installation_key)::bigint
        AS feature_installation_count,

    COUNT(DISTINCT e.user_key) FILTER (
        WHERE e.user_key IS NOT NULL
    )::bigint AS feature_user_count,

    COUNT(DISTINCT e.session_id) FILTER (
        WHERE e.session_id IS NOT NULL
    )::bigint AS feature_session_count

FROM analytics.fact_product_event e

JOIN analytics.dim_date d
  ON d.date_key = e.occurred_date_key

WHERE e.event_name = 'feature_used'
  AND e.feature_name IS NOT NULL

GROUP BY
    e.ingestion_batch_id,
    e.analytics_build_run_id,
    e.occurred_date_key,
    d.full_date,
    e.feature_name;


COMMENT ON VIEW reporting.vw_daily_feature_engagement IS
    'Daily feature-level engagement at analytics build, date and feature_name grain.';