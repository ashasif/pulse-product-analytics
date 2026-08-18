-- Pulse
-- Phase 3, Step 5
-- Analytics warehouse integrity and lineage validation.
--
-- These controls validate the successfully built analytics layer
-- without mutating staging data or reopening Step 4 validation.

BEGIN;


-- ============================================================
-- PERSISTED ANALYTICS CHECK RESULTS
-- ============================================================

CREATE TABLE IF NOT EXISTS validation.analytics_check_results (
    analytics_check_result_id
        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    analytics_build_run_id BIGINT NOT NULL,

    check_name TEXT NOT NULL,
    check_category TEXT NOT NULL,
    dataset_name TEXT,

    status TEXT NOT NULL,
    violation_count BIGINT NOT NULL,

    details JSONB NOT NULL DEFAULT '{}'::JSONB,

    checked_at TIMESTAMPTZ
        NOT NULL DEFAULT clock_timestamp(),

    CONSTRAINT analytics_check_results_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (
            analytics_build_run_id
        )
        ON DELETE RESTRICT,

    CONSTRAINT analytics_check_results_status_chk
        CHECK (status IN ('passed', 'failed')),

    CONSTRAINT analytics_check_results_violations_chk
        CHECK (violation_count >= 0),

    CONSTRAINT analytics_check_results_build_check_uk
        UNIQUE (
            analytics_build_run_id,
            check_name
        )
);


CREATE INDEX IF NOT EXISTS
    ix_analytics_check_results_build
ON validation.analytics_check_results (
    analytics_build_run_id
);

CREATE INDEX IF NOT EXISTS
    ix_analytics_check_results_status
ON validation.analytics_check_results (
    status
);


-- ============================================================
-- SOURCE -> ANALYTICS LINEAGE RECONCILIATION
-- ============================================================

CREATE OR REPLACE VIEW
validation.analytics_lineage_reconciliation
AS

SELECT
    s.ingestion_batch_id,
    'installations'::TEXT AS dataset_name,

    COUNT(*)::BIGINT AS staging_row_count,

    COUNT(a.installation_id)::BIGINT
        AS matched_analytics_rows,

    COUNT(*) FILTER (
        WHERE a.installation_id IS NULL
    )::BIGINT AS missing_analytics_rows,

    COUNT(*) FILTER (
        WHERE a.installation_id IS NOT NULL
          AND (
              a.source_row_number
                  IS DISTINCT FROM s.source_row_number
              OR a.row_hash
                  IS DISTINCT FROM s.row_hash
              OR a.validation_run_id
                  IS DISTINCT FROM s.validation_run_id
          )
    )::BIGINT AS lineage_mismatches

FROM staging.installations AS s

LEFT JOIN analytics.dim_installation AS a
  ON a.ingestion_batch_id = s.ingestion_batch_id
 AND a.installation_id = s.installation_id

GROUP BY s.ingestion_batch_id


UNION ALL


SELECT
    s.ingestion_batch_id,
    'users',

    COUNT(*)::BIGINT,
    COUNT(a.user_id)::BIGINT,

    COUNT(*) FILTER (
        WHERE a.user_id IS NULL
    )::BIGINT,

    COUNT(*) FILTER (
        WHERE a.user_id IS NOT NULL
          AND (
              a.source_row_number
                  IS DISTINCT FROM s.source_row_number
              OR a.row_hash
                  IS DISTINCT FROM s.row_hash
              OR a.validation_run_id
                  IS DISTINCT FROM s.validation_run_id
          )
    )::BIGINT

FROM staging.users AS s

LEFT JOIN analytics.dim_user AS a
  ON a.ingestion_batch_id = s.ingestion_batch_id
 AND a.user_id = s.user_id

GROUP BY s.ingestion_batch_id


UNION ALL


SELECT
    s.ingestion_batch_id,
    'product_events',

    COUNT(*)::BIGINT,
    COUNT(a.event_id)::BIGINT,

    COUNT(*) FILTER (
        WHERE a.event_id IS NULL
    )::BIGINT,

    COUNT(*) FILTER (
        WHERE a.event_id IS NOT NULL
          AND (
              a.source_row_number
                  IS DISTINCT FROM s.source_row_number
              OR a.row_hash
                  IS DISTINCT FROM s.row_hash
              OR a.validation_run_id
                  IS DISTINCT FROM s.validation_run_id
          )
    )::BIGINT

FROM staging.product_events AS s

LEFT JOIN analytics.fact_product_event AS a
  ON a.ingestion_batch_id = s.ingestion_batch_id
 AND a.event_id = s.event_id

GROUP BY s.ingestion_batch_id


UNION ALL


SELECT
    s.ingestion_batch_id,
    'subscriptions',

    COUNT(*)::BIGINT,
    COUNT(a.subscription_id)::BIGINT,

    COUNT(*) FILTER (
        WHERE a.subscription_id IS NULL
    )::BIGINT,

    COUNT(*) FILTER (
        WHERE a.subscription_id IS NOT NULL
          AND (
              a.source_row_number
                  IS DISTINCT FROM s.source_row_number
              OR a.row_hash
                  IS DISTINCT FROM s.row_hash
              OR a.validation_run_id
                  IS DISTINCT FROM s.validation_run_id
          )
    )::BIGINT

FROM staging.subscriptions AS s

LEFT JOIN analytics.fact_subscription AS a
  ON a.ingestion_batch_id = s.ingestion_batch_id
 AND a.subscription_id = s.subscription_id

GROUP BY s.ingestion_batch_id


UNION ALL


SELECT
    s.ingestion_batch_id,
    'subscription_transactions',

    COUNT(*)::BIGINT,
    COUNT(a.transaction_id)::BIGINT,

    COUNT(*) FILTER (
        WHERE a.transaction_id IS NULL
    )::BIGINT,

    COUNT(*) FILTER (
        WHERE a.transaction_id IS NOT NULL
          AND (
              a.source_row_number
                  IS DISTINCT FROM s.source_row_number
              OR a.row_hash
                  IS DISTINCT FROM s.row_hash
              OR a.validation_run_id
                  IS DISTINCT FROM s.validation_run_id
          )
    )::BIGINT

FROM staging.subscription_transactions AS s

LEFT JOIN analytics.fact_subscription_transaction AS a
  ON a.ingestion_batch_id = s.ingestion_batch_id
 AND a.transaction_id = s.transaction_id

GROUP BY s.ingestion_batch_id


UNION ALL


SELECT
    s.ingestion_batch_id,
    'experiment_assignments',

    COUNT(*)::BIGINT,
    COUNT(a.assignment_id)::BIGINT,

    COUNT(*) FILTER (
        WHERE a.assignment_id IS NULL
    )::BIGINT,

    COUNT(*) FILTER (
        WHERE a.assignment_id IS NOT NULL
          AND (
              a.source_row_number
                  IS DISTINCT FROM s.source_row_number
              OR a.row_hash
                  IS DISTINCT FROM s.row_hash
              OR a.validation_run_id
                  IS DISTINCT FROM s.validation_run_id
          )
    )::BIGINT

FROM staging.experiment_assignments AS s

LEFT JOIN analytics.fact_experiment_assignment AS a
  ON a.ingestion_batch_id = s.ingestion_batch_id
 AND a.assignment_id = s.assignment_id

GROUP BY s.ingestion_batch_id


UNION ALL


SELECT
    s.ingestion_batch_id,
    'marketing_spend',

    COUNT(*)::BIGINT,
    COUNT(a.marketing_spend_id)::BIGINT,

    COUNT(*) FILTER (
        WHERE a.marketing_spend_id IS NULL
    )::BIGINT,

    COUNT(*) FILTER (
        WHERE a.marketing_spend_id IS NOT NULL
          AND (
              a.source_row_number
                  IS DISTINCT FROM s.source_row_number
              OR a.row_hash
                  IS DISTINCT FROM s.row_hash
              OR a.validation_run_id
                  IS DISTINCT FROM s.validation_run_id
          )
    )::BIGINT

FROM staging.marketing_spend AS s

LEFT JOIN analytics.fact_marketing_spend AS a
  ON a.ingestion_batch_id = s.ingestion_batch_id
 AND a.marketing_spend_id = s.marketing_spend_id

GROUP BY s.ingestion_batch_id


UNION ALL


SELECT
    s.ingestion_batch_id,
    'app_releases',

    COUNT(*)::BIGINT,
    COUNT(a.app_release_id)::BIGINT,

    COUNT(*) FILTER (
        WHERE a.app_release_id IS NULL
    )::BIGINT,

    COUNT(*) FILTER (
        WHERE a.app_release_id IS NOT NULL
          AND (
              a.source_row_number
                  IS DISTINCT FROM s.source_row_number
              OR a.row_hash
                  IS DISTINCT FROM s.row_hash
              OR a.validation_run_id
                  IS DISTINCT FROM s.validation_run_id
          )
    )::BIGINT

FROM staging.app_releases AS s

LEFT JOIN analytics.dim_app_release AS a
  ON a.ingestion_batch_id = s.ingestion_batch_id
 AND a.app_release_id = s.app_release_id

GROUP BY s.ingestion_batch_id;


-- ============================================================
-- VALIDATION FUNCTION
-- 23 persisted checks:
--
--  8 reconciliation
--  8 lineage
--  5 relationship mappings
--  1 date-key integrity
--  1 build control
-- ============================================================

CREATE OR REPLACE FUNCTION
validation.validate_analytics_build(
    p_analytics_build_run_id BIGINT
)
RETURNS TABLE (
    expected_check_count INTEGER,
    completed_check_count INTEGER,
    passed_check_count INTEGER,
    failed_check_count INTEGER,
    total_violations BIGINT
)
LANGUAGE plpgsql
AS $function$
DECLARE
    v_ingestion_batch_id BIGINT;
    v_violations BIGINT;
BEGIN

    SELECT ingestion_batch_id
    INTO v_ingestion_batch_id
    FROM analytics.build_runs
    WHERE analytics_build_run_id
            = p_analytics_build_run_id
      AND status = 'succeeded';

    IF NOT FOUND THEN
        RAISE EXCEPTION
            'Analytics build run % is not successful',
            p_analytics_build_run_id;
    END IF;


    -- --------------------------------------------------------
    -- 1-8. DIRECT DATASET RECONCILIATION
    -- --------------------------------------------------------

    INSERT INTO validation.analytics_check_results (
        analytics_build_run_id,
        check_name,
        check_category,
        dataset_name,
        status,
        violation_count,
        details,
        checked_at
    )
    SELECT
        p_analytics_build_run_id,

        'reconciliation_' || dataset_name,

        'reconciliation',

        dataset_name,

        CASE
            WHEN reconciled
             AND row_count_delta = 0
            THEN 'passed'
            ELSE 'failed'
        END,

        ABS(row_count_delta),

        jsonb_build_object(
            'staging_row_count',
            staging_row_count,
            'analytics_row_count',
            analytics_row_count,
            'row_count_delta',
            row_count_delta
        ),

        clock_timestamp()

    FROM validation.analytics_reconciliation

    WHERE ingestion_batch_id
        = v_ingestion_batch_id

    ON CONFLICT (
        analytics_build_run_id,
        check_name
    )
    DO UPDATE SET
        status = EXCLUDED.status,
        violation_count = EXCLUDED.violation_count,
        details = EXCLUDED.details,
        checked_at = EXCLUDED.checked_at;


    -- --------------------------------------------------------
    -- 9-16. SOURCE LINEAGE RECONCILIATION
    -- --------------------------------------------------------

    INSERT INTO validation.analytics_check_results (
        analytics_build_run_id,
        check_name,
        check_category,
        dataset_name,
        status,
        violation_count,
        details,
        checked_at
    )
    SELECT
        p_analytics_build_run_id,

        'lineage_' || dataset_name,

        'lineage',

        dataset_name,

        CASE
            WHEN missing_analytics_rows = 0
             AND lineage_mismatches = 0
            THEN 'passed'
            ELSE 'failed'
        END,

        (
            missing_analytics_rows
            + lineage_mismatches
        ),

        jsonb_build_object(
            'staging_row_count',
            staging_row_count,
            'matched_analytics_rows',
            matched_analytics_rows,
            'missing_analytics_rows',
            missing_analytics_rows,
            'lineage_mismatches',
            lineage_mismatches
        ),

        clock_timestamp()

    FROM validation.analytics_lineage_reconciliation

    WHERE ingestion_batch_id
        = v_ingestion_batch_id

    ON CONFLICT (
        analytics_build_run_id,
        check_name
    )
    DO UPDATE SET
        status = EXCLUDED.status,
        violation_count = EXCLUDED.violation_count,
        details = EXCLUDED.details,
        checked_at = EXCLUDED.checked_at;


    -- --------------------------------------------------------
    -- 17. USER -> INSTALLATION SURROGATE MAPPING
    -- --------------------------------------------------------

    SELECT COUNT(*)::BIGINT
    INTO v_violations
    FROM staging.users AS s

    JOIN analytics.dim_user AS u
      ON u.ingestion_batch_id = s.ingestion_batch_id
     AND u.user_id = s.user_id

    JOIN analytics.dim_installation AS i
      ON i.installation_key = u.installation_key

    WHERE s.ingestion_batch_id
            = v_ingestion_batch_id

      AND i.installation_id
            IS DISTINCT FROM s.installation_id;

    INSERT INTO validation.analytics_check_results (
        analytics_build_run_id,
        check_name,
        check_category,
        dataset_name,
        status,
        violation_count,
        checked_at
    )
    VALUES (
        p_analytics_build_run_id,
        'relationship_users_installation',
        'relationship',
        'users',
        CASE
            WHEN v_violations = 0
            THEN 'passed'
            ELSE 'failed'
        END,
        v_violations,
        clock_timestamp()
    )
    ON CONFLICT (
        analytics_build_run_id,
        check_name
    )
    DO UPDATE SET
        status = EXCLUDED.status,
        violation_count = EXCLUDED.violation_count,
        checked_at = EXCLUDED.checked_at;


    -- --------------------------------------------------------
    -- 18. PRODUCT EVENT SURROGATE MAPPINGS
    -- --------------------------------------------------------

    SELECT COUNT(*)::BIGINT
    INTO v_violations
    FROM staging.product_events AS s

    JOIN analytics.fact_product_event AS f
      ON f.ingestion_batch_id = s.ingestion_batch_id
     AND f.event_id = s.event_id

    JOIN analytics.dim_installation AS i
      ON i.installation_key = f.installation_key

    LEFT JOIN analytics.dim_user AS u
      ON u.user_key = f.user_key

    WHERE s.ingestion_batch_id
            = v_ingestion_batch_id

      AND (
          i.installation_id
              IS DISTINCT FROM s.installation_id

          OR u.user_id
              IS DISTINCT FROM s.user_id
      );

    INSERT INTO validation.analytics_check_results (
        analytics_build_run_id,
        check_name,
        check_category,
        dataset_name,
        status,
        violation_count,
        checked_at
    )
    VALUES (
        p_analytics_build_run_id,
        'relationship_product_events',
        'relationship',
        'product_events',
        CASE
            WHEN v_violations = 0
            THEN 'passed'
            ELSE 'failed'
        END,
        v_violations,
        clock_timestamp()
    )
    ON CONFLICT (
        analytics_build_run_id,
        check_name
    )
    DO UPDATE SET
        status = EXCLUDED.status,
        violation_count = EXCLUDED.violation_count,
        checked_at = EXCLUDED.checked_at;


    -- --------------------------------------------------------
    -- 19. SUBSCRIPTION SURROGATE MAPPINGS
    -- --------------------------------------------------------

    SELECT COUNT(*)::BIGINT
    INTO v_violations
    FROM staging.subscriptions AS s

    JOIN analytics.fact_subscription AS f
      ON f.ingestion_batch_id = s.ingestion_batch_id
     AND f.subscription_id = s.subscription_id

    JOIN analytics.dim_user AS u
      ON u.user_key = f.user_key

    JOIN analytics.dim_installation AS i
      ON i.installation_key = f.installation_key

    WHERE s.ingestion_batch_id
            = v_ingestion_batch_id

      AND (
          u.user_id
              IS DISTINCT FROM s.user_id

          OR i.installation_id
              IS DISTINCT FROM s.installation_id
      );

    INSERT INTO validation.analytics_check_results (
        analytics_build_run_id,
        check_name,
        check_category,
        dataset_name,
        status,
        violation_count,
        checked_at
    )
    VALUES (
        p_analytics_build_run_id,
        'relationship_subscriptions',
        'relationship',
        'subscriptions',
        CASE
            WHEN v_violations = 0
            THEN 'passed'
            ELSE 'failed'
        END,
        v_violations,
        clock_timestamp()
    )
    ON CONFLICT (
        analytics_build_run_id,
        check_name
    )
    DO UPDATE SET
        status = EXCLUDED.status,
        violation_count = EXCLUDED.violation_count,
        checked_at = EXCLUDED.checked_at;


    -- --------------------------------------------------------
    -- 20. TRANSACTION SURROGATE MAPPINGS
    -- --------------------------------------------------------

    SELECT COUNT(*)::BIGINT
    INTO v_violations
    FROM staging.subscription_transactions AS s

    JOIN analytics.fact_subscription_transaction AS f
      ON f.ingestion_batch_id = s.ingestion_batch_id
     AND f.transaction_id = s.transaction_id

    JOIN analytics.fact_subscription AS sub
      ON sub.subscription_key = f.subscription_key

    JOIN analytics.dim_user AS u
      ON u.user_key = f.user_key

    JOIN analytics.dim_installation AS i
      ON i.installation_key = f.installation_key

    WHERE s.ingestion_batch_id
            = v_ingestion_batch_id

      AND (
          sub.subscription_id
              IS DISTINCT FROM s.subscription_id

          OR u.user_id
              IS DISTINCT FROM s.user_id

          OR i.installation_id
              IS DISTINCT FROM s.installation_id
      );

    INSERT INTO validation.analytics_check_results (
        analytics_build_run_id,
        check_name,
        check_category,
        dataset_name,
        status,
        violation_count,
        checked_at
    )
    VALUES (
        p_analytics_build_run_id,
        'relationship_subscription_transactions',
        'relationship',
        'subscription_transactions',
        CASE
            WHEN v_violations = 0
            THEN 'passed'
            ELSE 'failed'
        END,
        v_violations,
        clock_timestamp()
    )
    ON CONFLICT (
        analytics_build_run_id,
        check_name
    )
    DO UPDATE SET
        status = EXCLUDED.status,
        violation_count = EXCLUDED.violation_count,
        checked_at = EXCLUDED.checked_at;


    -- --------------------------------------------------------
    -- 21. EXPERIMENT ASSIGNMENT SURROGATE MAPPINGS
    -- --------------------------------------------------------

    SELECT COUNT(*)::BIGINT
    INTO v_violations
    FROM staging.experiment_assignments AS s

    JOIN analytics.fact_experiment_assignment AS f
      ON f.ingestion_batch_id = s.ingestion_batch_id
     AND f.assignment_id = s.assignment_id

    JOIN analytics.dim_experiment AS e
      ON e.experiment_key = f.experiment_key

    JOIN analytics.dim_user AS u
      ON u.user_key = f.user_key

    JOIN analytics.dim_installation AS i
      ON i.installation_key = f.installation_key

    WHERE s.ingestion_batch_id
            = v_ingestion_batch_id

      AND (
          e.experiment_id
              IS DISTINCT FROM s.experiment_id

          OR u.user_id
              IS DISTINCT FROM s.user_id

          OR i.installation_id
              IS DISTINCT FROM s.installation_id
      );

    INSERT INTO validation.analytics_check_results (
        analytics_build_run_id,
        check_name,
        check_category,
        dataset_name,
        status,
        violation_count,
        checked_at
    )
    VALUES (
        p_analytics_build_run_id,
        'relationship_experiment_assignments',
        'relationship',
        'experiment_assignments',
        CASE
            WHEN v_violations = 0
            THEN 'passed'
            ELSE 'failed'
        END,
        v_violations,
        clock_timestamp()
    )
    ON CONFLICT (
        analytics_build_run_id,
        check_name
    )
    DO UPDATE SET
        status = EXCLUDED.status,
        violation_count = EXCLUDED.violation_count,
        checked_at = EXCLUDED.checked_at;


    -- --------------------------------------------------------
    -- 22. DATE KEY CORRECTNESS
    -- --------------------------------------------------------

    SELECT
        COALESCE(
            SUM(violations),
            0
        )::BIGINT
    INTO v_violations
    FROM (

        SELECT COUNT(*)::BIGINT AS violations
        FROM analytics.dim_installation AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.installed_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.installed_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.dim_user AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.signed_up_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.signed_up_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.dim_app_release AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.release_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.release_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.fact_product_event AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.occurred_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.occurred_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.fact_subscription AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.trial_started_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.trial_started_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.fact_subscription AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.subscription_started_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND x.subscription_started_at IS NOT NULL
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.subscription_started_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.fact_subscription AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.expired_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND x.expired_at IS NOT NULL
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.expired_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.fact_subscription_transaction AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.attempted_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.attempted_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.fact_experiment_assignment AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.assignment_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.assignment_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.fact_experiment_assignment AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.exposed_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND x.exposed_at IS NOT NULL
          AND d.full_date
                IS DISTINCT FROM
                (
                    x.exposed_at
                    AT TIME ZONE 'UTC'
                )::DATE

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.fact_marketing_spend AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.period_start_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND d.full_date
                IS DISTINCT FROM x.period_start

        UNION ALL

        SELECT COUNT(*)::BIGINT
        FROM analytics.fact_marketing_spend AS x
        JOIN analytics.dim_date AS d
          ON d.date_key = x.period_end_date_key
        WHERE x.ingestion_batch_id
                = v_ingestion_batch_id
          AND d.full_date
                IS DISTINCT FROM x.period_end

    ) AS date_checks;

    INSERT INTO validation.analytics_check_results (
        analytics_build_run_id,
        check_name,
        check_category,
        status,
        violation_count,
        checked_at
    )
    VALUES (
        p_analytics_build_run_id,
        'date_key_integrity',
        'date',
        CASE
            WHEN v_violations = 0
            THEN 'passed'
            ELSE 'failed'
        END,
        v_violations,
        clock_timestamp()
    )
    ON CONFLICT (
        analytics_build_run_id,
        check_name
    )
    DO UPDATE SET
        status = EXCLUDED.status,
        violation_count = EXCLUDED.violation_count,
        checked_at = EXCLUDED.checked_at;


    -- --------------------------------------------------------
    -- 23. BUILD CONTROL CONSISTENCY
    -- --------------------------------------------------------

    SELECT
        CASE
            WHEN b.status = 'succeeded'
             AND b.expected_table_count = 10
             AND b.completed_table_count = 10

             AND b.source_staging_row_count = (
                 SELECT SUM(staging_row_count)
                 FROM validation.staging_dataset_counts
                 WHERE ingestion_batch_id
                     = v_ingestion_batch_id
             )

             AND b.analytics_row_count = (
                 b.source_staging_row_count
                 +
                 (
                     SELECT COUNT(*)
                     FROM analytics.dim_experiment
                     WHERE ingestion_batch_id
                         = v_ingestion_batch_id
                 )
             )

            THEN 0
            ELSE 1
        END::BIGINT

    INTO v_violations

    FROM analytics.build_runs AS b

    WHERE b.analytics_build_run_id
        = p_analytics_build_run_id;

    INSERT INTO validation.analytics_check_results (
        analytics_build_run_id,
        check_name,
        check_category,
        status,
        violation_count,
        checked_at
    )
    VALUES (
        p_analytics_build_run_id,
        'analytics_build_control',
        'build_control',
        CASE
            WHEN v_violations = 0
            THEN 'passed'
            ELSE 'failed'
        END,
        v_violations,
        clock_timestamp()
    )
    ON CONFLICT (
        analytics_build_run_id,
        check_name
    )
    DO UPDATE SET
        status = EXCLUDED.status,
        violation_count = EXCLUDED.violation_count,
        checked_at = EXCLUDED.checked_at;


    -- --------------------------------------------------------
    -- SUMMARY
    -- --------------------------------------------------------

    RETURN QUERY
    SELECT
        23::INTEGER AS expected_check_count,

        COUNT(*)::INTEGER
            AS completed_check_count,

        COUNT(*) FILTER (
            WHERE status = 'passed'
        )::INTEGER
            AS passed_check_count,

        COUNT(*) FILTER (
            WHERE status = 'failed'
        )::INTEGER
            AS failed_check_count,

        COALESCE(
            SUM(violation_count),
            0
        )::BIGINT
            AS total_violations

    FROM validation.analytics_check_results

    WHERE analytics_build_run_id
        = p_analytics_build_run_id;

END;
$function$;


COMMIT;
