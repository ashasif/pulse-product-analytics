-- Pulse
-- Phase 3, Step 5
-- Transactional staging-to-analytics build.
--
-- The build is authorised only by a complete successful:
--
-- raw ingestion -> validation -> staging promotion
--
-- chain.
--
-- All analytical table writes occur inside a PL/pgSQL exception
-- subtransaction. If any transformation or reconciliation fails,
-- analytical rows are rolled back and the failed build metadata
-- remains auditable.

BEGIN;

CREATE OR REPLACE FUNCTION analytics.build_promoted_batch(
    p_ingestion_batch_id BIGINT
)
RETURNS TABLE (
    result_build_run_id BIGINT,
    result_status TEXT,
    result_already_built BOOLEAN,
    result_validation_run_id BIGINT,
    result_promotion_run_id BIGINT,
    result_source_staging_rows BIGINT,
    result_analytics_rows BIGINT,
    result_error_message TEXT
)
LANGUAGE plpgsql
AS $function$
DECLARE
    v_snapshot_id TEXT;

    v_validation_run_id BIGINT;
    v_promotion_run_id BIGINT;

    v_source_staging_rows BIGINT;

    v_build_run_id BIGINT;

    v_existing_status TEXT;

    v_dataset_count INTEGER;
    v_reconciled_count INTEGER;
    v_reconciled_source_rows BIGINT;

    v_source_experiment_count BIGINT;
    v_target_experiment_count BIGINT;

    v_analytics_rows BIGINT;

    v_existing_batch_rows BIGINT;

    v_error_message TEXT;
BEGIN

    IF p_ingestion_batch_id IS NULL
       OR p_ingestion_batch_id <= 0
    THEN
        RAISE EXCEPTION
            'ingestion_batch_id must be greater than zero';
    END IF;


    -- --------------------------------------------------------
    -- Serialize analytics builds for this ingestion batch.
    -- --------------------------------------------------------

    PERFORM pg_advisory_xact_lock(
        hashtextextended(
            'pulse-analytics-build:'
            || p_ingestion_batch_id::TEXT,
            0
        )
    );


    -- --------------------------------------------------------
    -- Require complete successful upstream authorization.
    -- --------------------------------------------------------

    SELECT
        b.snapshot_id,
        p.validation_run_id,
        p.promotion_run_id,
        p.promoted_row_count
    INTO
        v_snapshot_id,
        v_validation_run_id,
        v_promotion_run_id,
        v_source_staging_rows
    FROM raw.ingestion_batches AS b
    JOIN staging.promotion_runs AS p
      ON p.ingestion_batch_id = b.ingestion_batch_id
    JOIN validation.validation_runs AS v
      ON v.validation_run_id = p.validation_run_id
     AND v.ingestion_batch_id = b.ingestion_batch_id
    WHERE b.ingestion_batch_id = p_ingestion_batch_id
      AND b.status = 'succeeded'
      AND v.status = 'succeeded'
      AND p.status = 'succeeded'
      AND p.expected_dataset_count = 8
      AND p.promoted_dataset_count = 8
      AND p.expected_row_count = p.promoted_row_count
    ORDER BY p.promotion_run_id
    LIMIT 1;

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'No complete successful raw/validation/promotion chain exists for ingestion batch %',
            p_ingestion_batch_id;
    END IF;


    -- --------------------------------------------------------
    -- Step 4 staging state must still be exactly reconciled.
    -- --------------------------------------------------------

    SELECT
        COUNT(*)::INTEGER,
        COUNT(*) FILTER (
            WHERE reconciled
        )::INTEGER,
        COALESCE(
            SUM(staging_row_count),
            0
        )::BIGINT
    INTO
        v_dataset_count,
        v_reconciled_count,
        v_reconciled_source_rows
    FROM validation.staging_reconciliation
    WHERE ingestion_batch_id = p_ingestion_batch_id;

    IF v_dataset_count <> 8
       OR v_reconciled_count <> 8
       OR v_reconciled_source_rows
            <> v_source_staging_rows
    THEN
        RAISE EXCEPTION
            'Staging reconciliation is not valid for ingestion batch %',
            p_ingestion_batch_id;
    END IF;


    -- --------------------------------------------------------
    -- Idempotency: return an existing successful build.
    -- --------------------------------------------------------

    SELECT
        analytics_build_run_id,
        status,
        analytics_row_count
    INTO
        v_build_run_id,
        v_existing_status,
        v_analytics_rows
    FROM analytics.build_runs
    WHERE ingestion_batch_id = p_ingestion_batch_id
      AND status = 'succeeded'
    ORDER BY analytics_build_run_id
    LIMIT 1;

    IF FOUND THEN

        SELECT
            COUNT(*)::INTEGER,
            COUNT(*) FILTER (
                WHERE reconciled
            )::INTEGER,
            COALESCE(
                SUM(staging_row_count),
                0
            )::BIGINT
        INTO
            v_dataset_count,
            v_reconciled_count,
            v_reconciled_source_rows
        FROM validation.analytics_reconciliation
        WHERE ingestion_batch_id = p_ingestion_batch_id;

        SELECT COUNT(DISTINCT experiment_id)
        INTO v_source_experiment_count
        FROM staging.experiment_assignments
        WHERE ingestion_batch_id = p_ingestion_batch_id;

        SELECT COUNT(*)
        INTO v_target_experiment_count
        FROM analytics.dim_experiment
        WHERE ingestion_batch_id = p_ingestion_batch_id;

        IF v_dataset_count <> 8
           OR v_reconciled_count <> 8
           OR v_reconciled_source_rows
                <> v_source_staging_rows
           OR v_source_experiment_count
                <> v_target_experiment_count
           OR v_analytics_rows
                <> (
                    v_source_staging_rows
                    + v_target_experiment_count
                )
        THEN
            RAISE EXCEPTION
                'Existing successful analytics build no longer reconciles';
        END IF;

        RETURN QUERY
        SELECT
            v_build_run_id,
            'succeeded'::TEXT,
            TRUE,
            v_validation_run_id,
            v_promotion_run_id,
            v_source_staging_rows,
            v_analytics_rows,
            NULL::TEXT;

        RETURN;
    END IF;


    -- --------------------------------------------------------
    -- No unexplained partial analytics state is permitted.
    -- dim_date is shared and therefore excluded from this check.
    -- --------------------------------------------------------

    SELECT
          (SELECT COUNT(*)
           FROM analytics.dim_installation
           WHERE ingestion_batch_id = p_ingestion_batch_id)

        + (SELECT COUNT(*)
           FROM analytics.dim_user
           WHERE ingestion_batch_id = p_ingestion_batch_id)

        + (SELECT COUNT(*)
           FROM analytics.dim_experiment
           WHERE ingestion_batch_id = p_ingestion_batch_id)

        + (SELECT COUNT(*)
           FROM analytics.dim_app_release
           WHERE ingestion_batch_id = p_ingestion_batch_id)

        + (SELECT COUNT(*)
           FROM analytics.fact_product_event
           WHERE ingestion_batch_id = p_ingestion_batch_id)

        + (SELECT COUNT(*)
           FROM analytics.fact_subscription
           WHERE ingestion_batch_id = p_ingestion_batch_id)

        + (SELECT COUNT(*)
           FROM analytics.fact_subscription_transaction
           WHERE ingestion_batch_id = p_ingestion_batch_id)

        + (SELECT COUNT(*)
           FROM analytics.fact_experiment_assignment
           WHERE ingestion_batch_id = p_ingestion_batch_id)

        + (SELECT COUNT(*)
           FROM analytics.fact_marketing_spend
           WHERE ingestion_batch_id = p_ingestion_batch_id)

    INTO v_existing_batch_rows;

    IF v_existing_batch_rows <> 0 THEN
        RAISE EXCEPTION
            'Unexplained partial analytics state exists for ingestion batch %',
            p_ingestion_batch_id;
    END IF;


    -- --------------------------------------------------------
    -- Create auditable running build metadata.
    -- --------------------------------------------------------

    INSERT INTO analytics.build_runs (
        ingestion_batch_id,
        validation_run_id,
        promotion_run_id,
        status,
        expected_table_count,
        completed_table_count,
        source_staging_row_count,
        analytics_row_count
    )
    VALUES (
        p_ingestion_batch_id,
        v_validation_run_id,
        v_promotion_run_id,
        'running',
        10,
        0,
        v_source_staging_rows,
        0
    )
    RETURNING analytics_build_run_id
    INTO v_build_run_id;


    -- ========================================================
    -- TRANSACTIONAL ANALYTICS TRANSFORMATION
    -- ========================================================

    BEGIN

        -- ----------------------------------------------------
        -- 1. DATE DIMENSION
        --
        -- Dates are canonical UTC calendar dates.
        -- ----------------------------------------------------

        WITH source_dates AS (

            SELECT
                MIN(
                    (installed_at AT TIME ZONE 'UTC')::DATE
                ) AS d
            FROM staging.installations
            WHERE ingestion_batch_id = p_ingestion_batch_id

            UNION ALL

            SELECT
                MAX(
                    (installed_at AT TIME ZONE 'UTC')::DATE
                )
            FROM staging.installations
            WHERE ingestion_batch_id = p_ingestion_batch_id

            UNION ALL

            SELECT
                MIN(
                    (occurred_at AT TIME ZONE 'UTC')::DATE
                )
            FROM staging.product_events
            WHERE ingestion_batch_id = p_ingestion_batch_id

            UNION ALL

            SELECT
                MAX(
                    (occurred_at AT TIME ZONE 'UTC')::DATE
                )
            FROM staging.product_events
            WHERE ingestion_batch_id = p_ingestion_batch_id

            UNION ALL

            SELECT MIN(period_start)
            FROM staging.marketing_spend
            WHERE ingestion_batch_id = p_ingestion_batch_id

            UNION ALL

            SELECT MAX(period_end)
            FROM staging.marketing_spend
            WHERE ingestion_batch_id = p_ingestion_batch_id

            UNION ALL

            SELECT
                MIN(
                    (release_at AT TIME ZONE 'UTC')::DATE
                )
            FROM staging.app_releases
            WHERE ingestion_batch_id = p_ingestion_batch_id

            UNION ALL

            SELECT
                MAX(
                    (release_at AT TIME ZONE 'UTC')::DATE
                )
            FROM staging.app_releases
            WHERE ingestion_batch_id = p_ingestion_batch_id

            UNION ALL

            SELECT
                MIN(
                    (assignment_at AT TIME ZONE 'UTC')::DATE
                )
            FROM staging.experiment_assignments
            WHERE ingestion_batch_id = p_ingestion_batch_id

            UNION ALL

            SELECT
                MAX(
                    (
                        COALESCE(
                            exposed_at,
                            assignment_at
                        )
                        AT TIME ZONE 'UTC'
                    )::DATE
                )
            FROM staging.experiment_assignments
            WHERE ingestion_batch_id = p_ingestion_batch_id

        ),
        bounds AS (
            SELECT
                MIN(d) AS min_date,
                MAX(d) AS max_date
            FROM source_dates
            WHERE d IS NOT NULL
        ),
        calendar AS (
            SELECT
                generated_date::DATE AS full_date
            FROM bounds
            CROSS JOIN LATERAL generate_series(
                min_date,
                max_date,
                INTERVAL '1 day'
            ) AS generated_date
        )

        INSERT INTO analytics.dim_date (
            date_key,
            full_date,
            calendar_year,
            calendar_quarter,
            month_number,
            month_name,
            iso_week,
            day_of_month,
            day_of_week,
            day_name,
            is_weekend
        )
        SELECT
            TO_CHAR(
                full_date,
                'YYYYMMDD'
            )::INTEGER,

            full_date,

            EXTRACT(
                YEAR FROM full_date
            )::SMALLINT,

            EXTRACT(
                QUARTER FROM full_date
            )::SMALLINT,

            EXTRACT(
                MONTH FROM full_date
            )::SMALLINT,

            TRIM(
                TO_CHAR(
                    full_date,
                    'Month'
                )
            ),

            EXTRACT(
                WEEK FROM full_date
            )::SMALLINT,

            EXTRACT(
                DAY FROM full_date
            )::SMALLINT,

            EXTRACT(
                ISODOW FROM full_date
            )::SMALLINT,

            TRIM(
                TO_CHAR(
                    full_date,
                    'Day'
                )
            ),

            EXTRACT(
                ISODOW FROM full_date
            ) IN (6, 7)

        FROM calendar
        ORDER BY full_date

        ON CONFLICT (full_date)
        DO NOTHING;


        -- ----------------------------------------------------
        -- 2. INSTALLATION DIMENSION
        -- ----------------------------------------------------

        INSERT INTO analytics.dim_installation (
            ingestion_batch_id,
            installation_id,
            anonymous_id,
            installed_at,
            installed_date_key,
            platform,
            acquisition_channel,
            country_code,
            validation_run_id,
            analytics_build_run_id,
            source_row_number,
            row_hash
        )
        SELECT
            s.ingestion_batch_id,
            s.installation_id,
            s.anonymous_id,
            s.installed_at,

            TO_CHAR(
                (
                    s.installed_at
                    AT TIME ZONE 'UTC'
                )::DATE,
                'YYYYMMDD'
            )::INTEGER,

            s.platform,
            s.acquisition_channel,
            s.country_code,
            s.validation_run_id,
            v_build_run_id,
            s.source_row_number,
            s.row_hash

        FROM staging.installations AS s

        WHERE s.ingestion_batch_id
            = p_ingestion_batch_id

        ORDER BY s.source_row_number;


        -- ----------------------------------------------------
        -- 3. USER DIMENSION
        -- ----------------------------------------------------

        INSERT INTO analytics.dim_user (
            ingestion_batch_id,
            user_id,
            installation_key,
            signed_up_at,
            signed_up_date_key,
            onboarding_started_at,
            onboarding_completed_at,
            validation_run_id,
            analytics_build_run_id,
            source_row_number,
            row_hash
        )
        SELECT
            s.ingestion_batch_id,
            s.user_id,
            i.installation_key,
            s.signed_up_at,

            TO_CHAR(
                (
                    s.signed_up_at
                    AT TIME ZONE 'UTC'
                )::DATE,
                'YYYYMMDD'
            )::INTEGER,

            s.onboarding_started_at,
            s.onboarding_completed_at,
            s.validation_run_id,
            v_build_run_id,
            s.source_row_number,
            s.row_hash

        FROM staging.users AS s

        JOIN analytics.dim_installation AS i
          ON i.ingestion_batch_id
                = s.ingestion_batch_id
         AND i.installation_id
                = s.installation_id

        WHERE s.ingestion_batch_id
            = p_ingestion_batch_id

        ORDER BY s.source_row_number;


        -- ----------------------------------------------------
        -- 4. EXPERIMENT DIMENSION
        --
        -- Experiment metadata is repeated on assignment rows.
        -- DISTINCT collapses that repeated definition into the
        -- actual experiment grain.
        -- ----------------------------------------------------

        INSERT INTO analytics.dim_experiment (
            ingestion_batch_id,
            experiment_id,
            experiment_name,
            randomization_unit,
            experiment_start_at,
            experiment_end_at,
            eligibility_rule,
            assignment_trigger,
            exposure_trigger,
            hypothesis,
            primary_metric,
            secondary_metric,
            commercial_metric,
            guardrail_metric,
            analysis_window_days,
            analytics_build_run_id
        )
        SELECT
            e.ingestion_batch_id,
            e.experiment_id,
            e.experiment_name,
            e.randomization_unit,
            e.experiment_start_at,
            e.experiment_end_at,
            e.eligibility_rule,
            e.assignment_trigger,
            e.exposure_trigger,
            e.hypothesis,
            e.primary_metric,
            e.secondary_metric,
            e.commercial_metric,
            e.guardrail_metric,
            e.analysis_window_days,
            v_build_run_id

        FROM (
            SELECT DISTINCT
                s.ingestion_batch_id,
                s.experiment_id,
                s.experiment_name,
                s.randomization_unit,
                s.experiment_start_at,
                s.experiment_end_at,
                s.eligibility_rule,
                s.assignment_trigger,
                s.exposure_trigger,
                s.hypothesis,
                s.primary_metric,
                s.secondary_metric,
                s.commercial_metric,
                s.guardrail_metric,
                s.analysis_window_days

            FROM staging.experiment_assignments AS s

            WHERE s.ingestion_batch_id
                = p_ingestion_batch_id
        ) AS e

        ORDER BY e.experiment_id;


        -- ----------------------------------------------------
        -- 5. APP RELEASE DIMENSION
        -- ----------------------------------------------------

        INSERT INTO analytics.dim_app_release (
            ingestion_batch_id,
            app_release_id,
            release_key,
            release_name,
            release_sequence,
            platform,
            version,
            release_at,
            release_date_key,
            release_type,
            feature_area,
            rollout_strategy,
            rollout_days,
            rollout_complete_at,
            release_channel,
            release_notes,
            validation_run_id,
            analytics_build_run_id,
            source_row_number,
            row_hash
        )
        SELECT
            s.ingestion_batch_id,
            s.app_release_id,
            s.release_key,
            s.release_name,
            s.release_sequence,
            s.platform,
            s.version,
            s.release_at,

            TO_CHAR(
                (
                    s.release_at
                    AT TIME ZONE 'UTC'
                )::DATE,
                'YYYYMMDD'
            )::INTEGER,

            s.release_type,
            s.feature_area,
            s.rollout_strategy,
            s.rollout_days,
            s.rollout_complete_at,
            s.release_channel,
            s.release_notes,
            s.validation_run_id,
            v_build_run_id,
            s.source_row_number,
            s.row_hash

        FROM staging.app_releases AS s

        WHERE s.ingestion_batch_id
            = p_ingestion_batch_id

        ORDER BY s.source_row_number;


        -- ----------------------------------------------------
        -- 6. PRODUCT EVENT FACT
        -- ----------------------------------------------------

        INSERT INTO analytics.fact_product_event (
            ingestion_batch_id,
            event_id,
            event_name,
            occurred_at,
            occurred_date_key,
            installation_key,
            user_key,
            session_id,
            feature_name,
            validation_run_id,
            analytics_build_run_id,
            source_row_number,
            row_hash
        )
        SELECT
            s.ingestion_batch_id,
            s.event_id,
            s.event_name,
            s.occurred_at,

            TO_CHAR(
                (
                    s.occurred_at
                    AT TIME ZONE 'UTC'
                )::DATE,
                'YYYYMMDD'
            )::INTEGER,

            i.installation_key,
            u.user_key,
            s.session_id,
            s.feature_name,
            s.validation_run_id,
            v_build_run_id,
            s.source_row_number,
            s.row_hash

        FROM staging.product_events AS s

        JOIN analytics.dim_installation AS i
          ON i.ingestion_batch_id
                = s.ingestion_batch_id
         AND i.installation_id
                = s.installation_id

        LEFT JOIN analytics.dim_user AS u
          ON u.ingestion_batch_id
                = s.ingestion_batch_id
         AND u.user_id
                = s.user_id

        WHERE s.ingestion_batch_id
            = p_ingestion_batch_id

          AND (
              s.user_id IS NULL
              OR u.user_key IS NOT NULL
          )

        ORDER BY s.source_row_number;


        -- ----------------------------------------------------
        -- 7. SUBSCRIPTION FACT
        -- ----------------------------------------------------

        INSERT INTO analytics.fact_subscription (
            ingestion_batch_id,
            subscription_id,
            user_key,
            installation_key,
            billing_period,
            price_gbp,
            currency,
            status,
            trial_started_at,
            trial_started_date_key,
            trial_ends_at,
            subscription_started_at,
            subscription_started_date_key,
            current_period_start_at,
            current_period_end_at,
            cancellation_requested_at,
            expired_at,
            expired_date_key,
            auto_renew,
            end_reason,
            validation_run_id,
            analytics_build_run_id,
            source_row_number,
            row_hash
        )
        SELECT
            s.ingestion_batch_id,
            s.subscription_id,
            u.user_key,
            i.installation_key,
            s.billing_period,
            s.price_gbp,
            s.currency,
            s.status,
            s.trial_started_at,

            TO_CHAR(
                (
                    s.trial_started_at
                    AT TIME ZONE 'UTC'
                )::DATE,
                'YYYYMMDD'
            )::INTEGER,

            s.trial_ends_at,
            s.subscription_started_at,

            CASE
                WHEN s.subscription_started_at
                    IS NULL
                THEN NULL
                ELSE TO_CHAR(
                    (
                        s.subscription_started_at
                        AT TIME ZONE 'UTC'
                    )::DATE,
                    'YYYYMMDD'
                )::INTEGER
            END,

            s.current_period_start_at,
            s.current_period_end_at,
            s.cancellation_requested_at,
            s.expired_at,

            CASE
                WHEN s.expired_at IS NULL
                THEN NULL
                ELSE TO_CHAR(
                    (
                        s.expired_at
                        AT TIME ZONE 'UTC'
                    )::DATE,
                    'YYYYMMDD'
                )::INTEGER
            END,

            s.auto_renew,
            s.end_reason,
            s.validation_run_id,
            v_build_run_id,
            s.source_row_number,
            s.row_hash

        FROM staging.subscriptions AS s

        JOIN analytics.dim_user AS u
          ON u.ingestion_batch_id
                = s.ingestion_batch_id
         AND u.user_id
                = s.user_id

        JOIN analytics.dim_installation AS i
          ON i.ingestion_batch_id
                = s.ingestion_batch_id
         AND i.installation_id
                = s.installation_id

        WHERE s.ingestion_batch_id
            = p_ingestion_batch_id

        ORDER BY s.source_row_number;


        -- ----------------------------------------------------
        -- 8. SUBSCRIPTION TRANSACTION FACT
        -- ----------------------------------------------------

        INSERT INTO analytics.fact_subscription_transaction (
            ingestion_batch_id,
            transaction_id,
            subscription_key,
            user_key,
            installation_key,
            transaction_type,
            attempted_at,
            attempted_date_key,
            billing_period,
            amount_gbp,
            currency,
            payment_status,
            billing_cycle_number,
            attempt_number,
            validation_run_id,
            analytics_build_run_id,
            source_row_number,
            row_hash
        )
        SELECT
            s.ingestion_batch_id,
            s.transaction_id,
            sub.subscription_key,
            u.user_key,
            i.installation_key,
            s.transaction_type,
            s.attempted_at,

            TO_CHAR(
                (
                    s.attempted_at
                    AT TIME ZONE 'UTC'
                )::DATE,
                'YYYYMMDD'
            )::INTEGER,

            s.billing_period,
            s.amount_gbp,
            s.currency,
            s.payment_status,
            s.billing_cycle_number,
            s.attempt_number,
            s.validation_run_id,
            v_build_run_id,
            s.source_row_number,
            s.row_hash

        FROM staging.subscription_transactions AS s

        JOIN analytics.fact_subscription AS sub
          ON sub.ingestion_batch_id
                = s.ingestion_batch_id
         AND sub.subscription_id
                = s.subscription_id

        JOIN analytics.dim_user AS u
          ON u.ingestion_batch_id
                = s.ingestion_batch_id
         AND u.user_id
                = s.user_id

        JOIN analytics.dim_installation AS i
          ON i.ingestion_batch_id
                = s.ingestion_batch_id
         AND i.installation_id
                = s.installation_id

        WHERE s.ingestion_batch_id
            = p_ingestion_batch_id

        ORDER BY s.source_row_number;


        -- ----------------------------------------------------
        -- 9. EXPERIMENT ASSIGNMENT FACT
        -- ----------------------------------------------------

        INSERT INTO analytics.fact_experiment_assignment (
            ingestion_batch_id,
            assignment_id,
            experiment_key,
            user_key,
            installation_key,
            variant,
            allocation_probability,
            assignment_at,
            assignment_date_key,
            exposed_at,
            exposed_date_key,
            validation_run_id,
            analytics_build_run_id,
            source_row_number,
            row_hash
        )
        SELECT
            s.ingestion_batch_id,
            s.assignment_id,
            e.experiment_key,
            u.user_key,
            i.installation_key,
            s.variant,
            s.allocation_probability,
            s.assignment_at,

            TO_CHAR(
                (
                    s.assignment_at
                    AT TIME ZONE 'UTC'
                )::DATE,
                'YYYYMMDD'
            )::INTEGER,

            s.exposed_at,

            CASE
                WHEN s.exposed_at IS NULL
                THEN NULL
                ELSE TO_CHAR(
                    (
                        s.exposed_at
                        AT TIME ZONE 'UTC'
                    )::DATE,
                    'YYYYMMDD'
                )::INTEGER
            END,

            s.validation_run_id,
            v_build_run_id,
            s.source_row_number,
            s.row_hash

        FROM staging.experiment_assignments AS s

        JOIN analytics.dim_experiment AS e
          ON e.ingestion_batch_id
                = s.ingestion_batch_id
         AND e.experiment_id
                = s.experiment_id

        JOIN analytics.dim_user AS u
          ON u.ingestion_batch_id
                = s.ingestion_batch_id
         AND u.user_id
                = s.user_id

        JOIN analytics.dim_installation AS i
          ON i.ingestion_batch_id
                = s.ingestion_batch_id
         AND i.installation_id
                = s.installation_id

        WHERE s.ingestion_batch_id
            = p_ingestion_batch_id

        ORDER BY s.source_row_number;


        -- ----------------------------------------------------
        -- 10. MARKETING SPEND FACT
        -- ----------------------------------------------------

        INSERT INTO analytics.fact_marketing_spend (
            ingestion_batch_id,
            marketing_spend_id,
            period_start,
            period_start_date_key,
            period_end,
            period_end_date_key,
            acquisition_channel,
            spend_type,
            campaign_type,
            spend,
            currency,
            impressions,
            clicks,
            validation_run_id,
            analytics_build_run_id,
            source_row_number,
            row_hash
        )
        SELECT
            s.ingestion_batch_id,
            s.marketing_spend_id,
            s.period_start,

            TO_CHAR(
                s.period_start,
                'YYYYMMDD'
            )::INTEGER,

            s.period_end,

            TO_CHAR(
                s.period_end,
                'YYYYMMDD'
            )::INTEGER,

            s.acquisition_channel,
            s.spend_type,
            s.campaign_type,
            s.spend,
            s.currency,
            s.impressions,
            s.clicks,
            s.validation_run_id,
            v_build_run_id,
            s.source_row_number,
            s.row_hash

        FROM staging.marketing_spend AS s

        WHERE s.ingestion_batch_id
            = p_ingestion_batch_id

        ORDER BY s.source_row_number;


        -- ====================================================
        -- BUILD RECONCILIATION
        -- ====================================================

        SELECT
            COUNT(*)::INTEGER,
            COUNT(*) FILTER (
                WHERE reconciled
            )::INTEGER,
            COALESCE(
                SUM(staging_row_count),
                0
            )::BIGINT
        INTO
            v_dataset_count,
            v_reconciled_count,
            v_reconciled_source_rows
        FROM validation.analytics_reconciliation
        WHERE ingestion_batch_id
            = p_ingestion_batch_id;

        IF v_dataset_count <> 8
           OR v_reconciled_count <> 8
           OR v_reconciled_source_rows
                <> v_source_staging_rows
        THEN
            RAISE EXCEPTION
                'Staging-to-analytics reconciliation failed';
        END IF;


        -- Experiment dimension is intentionally derived from
        -- repeated experiment metadata on assignment rows.

        SELECT COUNT(DISTINCT experiment_id)
        INTO v_source_experiment_count
        FROM staging.experiment_assignments
        WHERE ingestion_batch_id
            = p_ingestion_batch_id;

        SELECT COUNT(*)
        INTO v_target_experiment_count
        FROM analytics.dim_experiment
        WHERE ingestion_batch_id
            = p_ingestion_batch_id;

        IF v_source_experiment_count
            <> v_target_experiment_count
        THEN
            RAISE EXCEPTION
                'Experiment dimension reconciliation failed';
        END IF;


        -- dim_date is a shared conformed dimension and is not
        -- counted as batch-owned data.
        --
        -- The eight direct source datasets reconcile 1:1.
        -- dim_experiment contributes its derived experiment-grain
        -- records.

        v_analytics_rows :=
            v_source_staging_rows
            + v_target_experiment_count;


        UPDATE analytics.build_runs
        SET
            status = 'succeeded',
            completed_table_count = 10,
            analytics_row_count =
                v_analytics_rows,
            completed_at =
                clock_timestamp(),
            error_message = NULL
        WHERE analytics_build_run_id
            = v_build_run_id;


    EXCEPTION
        WHEN OTHERS THEN

            v_error_message :=
                SQLSTATE
                || ': '
                || SQLERRM;

            -- All writes performed inside this BEGIN/EXCEPTION
            -- block have already been rolled back automatically.
            -- The build_runs row was created outside the block
            -- and remains available for the failure audit.

            UPDATE analytics.build_runs
            SET
                status = 'failed',
                completed_table_count = 0,
                analytics_row_count = 0,
                completed_at =
                    clock_timestamp(),
                error_message =
                    LEFT(
                        v_error_message,
                        4000
                    )
            WHERE analytics_build_run_id
                = v_build_run_id;

            RETURN QUERY
            SELECT
                v_build_run_id,
                'failed'::TEXT,
                FALSE,
                v_validation_run_id,
                v_promotion_run_id,
                v_source_staging_rows,
                0::BIGINT,
                LEFT(
                    v_error_message,
                    4000
                );

            RETURN;
    END;


    RETURN QUERY
    SELECT
        v_build_run_id,
        'succeeded'::TEXT,
        FALSE,
        v_validation_run_id,
        v_promotion_run_id,
        v_source_staging_rows,
        v_analytics_rows,
        NULL::TEXT;

END;
$function$;

COMMIT;
