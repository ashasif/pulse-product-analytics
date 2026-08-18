CREATE OR REPLACE VIEW reporting.vw_installation_lifecycle AS
WITH user_rollup AS (
    SELECT
        installation_key,
        COUNT(*)::bigint AS registered_user_count,
        MIN(signed_up_at) AS first_signed_up_at,

        COUNT(*) FILTER (
            WHERE onboarding_started_at IS NOT NULL
        )::bigint AS onboarding_started_user_count,

        MIN(onboarding_started_at) AS first_onboarding_started_at,

        COUNT(*) FILTER (
            WHERE onboarding_completed_at IS NOT NULL
        )::bigint AS onboarding_completed_user_count,

        MIN(onboarding_completed_at) AS first_onboarding_completed_at

    FROM analytics.dim_user
    GROUP BY installation_key
)
SELECT
    i.ingestion_batch_id,
    i.analytics_build_run_id,
    i.installation_key,
    i.installation_id,
    i.installed_date_key,
    d.full_date AS installed_date,
    i.installed_at,
    i.platform,
    i.acquisition_channel,
    i.country_code,

    COALESCE(u.registered_user_count, 0)::bigint
        AS registered_user_count,

    COALESCE(u.registered_user_count, 0) > 0
        AS has_signup,

    u.first_signed_up_at,

    COALESCE(u.onboarding_started_user_count, 0)::bigint
        AS onboarding_started_user_count,

    COALESCE(u.onboarding_started_user_count, 0) > 0
        AS has_onboarding_started,

    u.first_onboarding_started_at,

    COALESCE(u.onboarding_completed_user_count, 0)::bigint
        AS onboarding_completed_user_count,

    COALESCE(u.onboarding_completed_user_count, 0) > 0
        AS has_onboarding_completed,

    u.first_onboarding_completed_at

FROM analytics.dim_installation i
JOIN analytics.dim_date d
  ON d.date_key = i.installed_date_key
LEFT JOIN user_rollup u
  ON u.installation_key = i.installation_key;


COMMENT ON VIEW reporting.vw_installation_lifecycle IS
    'One row per installation per analytics build, with downstream registration and onboarding lifecycle summarized without assuming a one-to-one installation-to-user relationship.';


CREATE OR REPLACE VIEW reporting.vw_daily_product_kpis AS
WITH successful_builds AS (
    SELECT
        ingestion_batch_id,
        analytics_build_run_id
    FROM analytics.build_runs
    WHERE status = 'succeeded'
),
install_daily AS (
    SELECT
        ingestion_batch_id,
        analytics_build_run_id,
        installed_date_key AS date_key,
        COUNT(*)::bigint AS installation_count
    FROM analytics.dim_installation
    GROUP BY
        ingestion_batch_id,
        analytics_build_run_id,
        installed_date_key
),
signup_daily AS (
    SELECT
        ingestion_batch_id,
        analytics_build_run_id,
        signed_up_date_key AS date_key,
        COUNT(*)::bigint AS signup_count
    FROM analytics.dim_user
    GROUP BY
        ingestion_batch_id,
        analytics_build_run_id,
        signed_up_date_key
),
event_daily AS (
    SELECT
        ingestion_batch_id,
        analytics_build_run_id,
        occurred_date_key AS date_key,

        COUNT(*) FILTER (
            WHERE event_name = 'session_started'
        )::bigint AS session_count,

        COUNT(DISTINCT installation_key) FILTER (
            WHERE event_name = 'session_started'
        )::bigint AS active_installation_count,

        COUNT(DISTINCT user_key) FILTER (
            WHERE event_name = 'session_started'
              AND user_key IS NOT NULL
        )::bigint AS registered_dau,

        COUNT(*) FILTER (
            WHERE event_name = 'feature_used'
        )::bigint AS feature_use_event_count,

        COUNT(DISTINCT user_key) FILTER (
            WHERE event_name = 'feature_used'
              AND user_key IS NOT NULL
        )::bigint AS feature_user_count,

        COUNT(*) FILTER (
            WHERE event_name = 'paywall_viewed'
        )::bigint AS paywall_view_count,

        COUNT(DISTINCT user_key) FILTER (
            WHERE event_name = 'paywall_viewed'
              AND user_key IS NOT NULL
        )::bigint AS paywall_view_user_count,

        COUNT(*) FILTER (
            WHERE event_name = 'onboarding_started'
        )::bigint AS onboarding_started_count,

        COUNT(*) FILTER (
            WHERE event_name = 'onboarding_completed'
        )::bigint AS onboarding_completed_count,

        COUNT(*) FILTER (
            WHERE event_name = 'trial_started'
        )::bigint AS trial_start_count,

        COUNT(*) FILTER (
            WHERE event_name = 'subscription_started'
        )::bigint AS paid_subscription_start_count,

        COUNT(*) FILTER (
            WHERE event_name = 'cancellation_requested'
        )::bigint AS cancellation_requested_count,

        COUNT(*) FILTER (
            WHERE event_name = 'subscription_expired'
        )::bigint AS subscription_expired_count,

        COUNT(*) FILTER (
            WHERE event_name = 'payment_failed'
        )::bigint AS payment_failed_event_count

    FROM analytics.fact_product_event
    GROUP BY
        ingestion_batch_id,
        analytics_build_run_id,
        occurred_date_key
)
SELECT
    d.date_key,
    d.full_date,
    d.calendar_year,
    d.calendar_quarter,
    d.month_number,
    d.month_name,
    d.iso_week,
    d.day_of_week,
    d.day_name,
    d.is_weekend,

    COALESCE(i.installation_count, 0)::bigint
        AS installation_count,

    COALESCE(s.signup_count, 0)::bigint
        AS signup_count,

    COALESCE(e.session_count, 0)::bigint
        AS session_count,

    COALESCE(e.active_installation_count, 0)::bigint
        AS active_installation_count,

    COALESCE(e.registered_dau, 0)::bigint
        AS registered_dau,

    COALESCE(e.feature_use_event_count, 0)::bigint
        AS feature_use_event_count,

    COALESCE(e.feature_user_count, 0)::bigint
        AS feature_user_count,

    COALESCE(e.paywall_view_count, 0)::bigint
        AS paywall_view_count,

    COALESCE(e.paywall_view_user_count, 0)::bigint
        AS paywall_view_user_count,

    COALESCE(e.onboarding_started_count, 0)::bigint
        AS onboarding_started_count,

    COALESCE(e.onboarding_completed_count, 0)::bigint
        AS onboarding_completed_count,

    COALESCE(e.trial_start_count, 0)::bigint
        AS trial_start_count,

    COALESCE(e.paid_subscription_start_count, 0)::bigint
        AS paid_subscription_start_count,

    COALESCE(e.cancellation_requested_count, 0)::bigint
        AS cancellation_requested_count,

    COALESCE(e.subscription_expired_count, 0)::bigint
        AS subscription_expired_count,

    COALESCE(e.payment_failed_event_count, 0)::bigint
        AS payment_failed_event_count,

    b.ingestion_batch_id,
    b.analytics_build_run_id

FROM successful_builds b
CROSS JOIN analytics.dim_date d

LEFT JOIN install_daily i
  ON i.ingestion_batch_id = b.ingestion_batch_id
 AND i.analytics_build_run_id = b.analytics_build_run_id
 AND i.date_key = d.date_key

LEFT JOIN signup_daily s
  ON s.ingestion_batch_id = b.ingestion_batch_id
 AND s.analytics_build_run_id = b.analytics_build_run_id
 AND s.date_key = d.date_key

LEFT JOIN event_daily e
  ON e.ingestion_batch_id = b.ingestion_batch_id
 AND e.analytics_build_run_id = b.analytics_build_run_id
 AND e.date_key = d.date_key;


COMMENT ON VIEW reporting.vw_daily_product_kpis IS
    'One row per successful analytics build and calendar date containing occurrence-based product and engagement KPIs. Build lineage is explicit and cohort conversion rates are intentionally excluded.';


CREATE OR REPLACE VIEW reporting.vw_daily_subscription_revenue AS
WITH successful_builds AS (
    SELECT
        ingestion_batch_id,
        analytics_build_run_id
    FROM analytics.build_runs
    WHERE status = 'succeeded'
),
transaction_daily AS (
    SELECT
        ingestion_batch_id,
        analytics_build_run_id,
        attempted_date_key AS date_key,

        COUNT(*)::bigint AS payment_attempt_count,

        COUNT(*) FILTER (
            WHERE payment_status = 'succeeded'
        )::bigint AS successful_payment_count,

        COUNT(*) FILTER (
            WHERE payment_status = 'failed'
        )::bigint AS failed_payment_count,

        COALESCE(
            SUM(amount_gbp) FILTER (
                WHERE payment_status = 'succeeded'
            ),
            0
        ) AS successful_payment_revenue_gbp,

        COUNT(*) FILTER (
            WHERE transaction_type = 'initial_charge'
        )::bigint AS initial_charge_attempt_count,

        COUNT(*) FILTER (
            WHERE transaction_type = 'initial_charge'
              AND payment_status = 'succeeded'
        )::bigint AS successful_initial_charge_count,

        COALESCE(
            SUM(amount_gbp) FILTER (
                WHERE transaction_type = 'initial_charge'
                  AND payment_status = 'succeeded'
            ),
            0
        ) AS initial_charge_revenue_gbp,

        COUNT(*) FILTER (
            WHERE transaction_type = 'renewal'
        )::bigint AS renewal_attempt_count,

        COUNT(*) FILTER (
            WHERE transaction_type = 'renewal'
              AND payment_status = 'succeeded'
        )::bigint AS successful_renewal_count,

        COUNT(*) FILTER (
            WHERE transaction_type = 'renewal'
              AND payment_status = 'failed'
        )::bigint AS failed_renewal_count,

        COALESCE(
            SUM(amount_gbp) FILTER (
                WHERE transaction_type = 'renewal'
                  AND payment_status = 'succeeded'
            ),
            0
        ) AS renewal_revenue_gbp

    FROM analytics.fact_subscription_transaction
    GROUP BY
        ingestion_batch_id,
        analytics_build_run_id,
        attempted_date_key
)
SELECT
    d.date_key,
    d.full_date,
    d.calendar_year,
    d.calendar_quarter,
    d.month_number,
    d.month_name,
    d.iso_week,

    COALESCE(t.payment_attempt_count, 0)::bigint
        AS payment_attempt_count,

    COALESCE(t.successful_payment_count, 0)::bigint
        AS successful_payment_count,

    COALESCE(t.failed_payment_count, 0)::bigint
        AS failed_payment_count,

    CASE
        WHEN COALESCE(t.payment_attempt_count, 0) = 0
            THEN NULL
        ELSE
            t.failed_payment_count::numeric
            / NULLIF(t.payment_attempt_count, 0)
    END AS payment_failure_rate,

    COALESCE(t.successful_payment_revenue_gbp, 0)::numeric
        AS successful_payment_revenue_gbp,

    COALESCE(t.initial_charge_attempt_count, 0)::bigint
        AS initial_charge_attempt_count,

    COALESCE(t.successful_initial_charge_count, 0)::bigint
        AS successful_initial_charge_count,

    COALESCE(t.initial_charge_revenue_gbp, 0)::numeric
        AS initial_charge_revenue_gbp,

    COALESCE(t.renewal_attempt_count, 0)::bigint
        AS renewal_attempt_count,

    COALESCE(t.successful_renewal_count, 0)::bigint
        AS successful_renewal_count,

    COALESCE(t.failed_renewal_count, 0)::bigint
        AS failed_renewal_count,

    CASE
        WHEN COALESCE(t.renewal_attempt_count, 0) = 0
            THEN NULL
        ELSE
            t.successful_renewal_count::numeric
            / NULLIF(t.renewal_attempt_count, 0)
    END AS renewal_success_rate,

    COALESCE(t.renewal_revenue_gbp, 0)::numeric
        AS renewal_revenue_gbp,

    b.ingestion_batch_id,
    b.analytics_build_run_id

FROM successful_builds b
CROSS JOIN analytics.dim_date d

LEFT JOIN transaction_daily t
  ON t.ingestion_batch_id = b.ingestion_batch_id
 AND t.analytics_build_run_id = b.analytics_build_run_id
 AND t.date_key = d.date_key;


COMMENT ON VIEW reporting.vw_daily_subscription_revenue IS
    'One row per successful analytics build and calendar date containing payment attempts, successful cash collection, failures and renewal metrics. Revenue includes succeeded transactions only.';