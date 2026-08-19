"""Point-in-time modelling dataset for Phase 6 trial conversion.

Business target semantics originate in reporting.*. Behavioural predictors are
constructed from validated analytics product events with an explicit
prediction-time boundary.

No model fitting belongs in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from psycopg import Connection
from psycopg.rows import dict_row


PREDICTION_LEAD_HOURS = 48
LABEL_MATURITY_DAYS = 3

LABEL_COLUMN = "converted_to_paid"

PREDICTOR_COLUMNS = (
    # Static context available before the prediction timestamp.
    "platform",
    "acquisition_channel",
    "country_code",
    "billing_period",

    # Lifecycle context.
    "install_to_signup_hours",
    "signup_to_trial_hours",
    "onboarding_started_before_prediction",
    "onboarding_completed_before_prediction",

    # Behaviour already observed before the trial.
    "pretrial_session_count",
    "pretrial_feature_event_count",
    "pretrial_paywall_view_count",

    # Behaviour observed during the first five trial days only.
    "trial_session_count",
    "trial_feature_event_count",
    "trial_active_day_count",
    "trial_distinct_feature_count",
    "hours_since_last_trial_activity",
)

AUDIT_COLUMNS = (
    "ingestion_batch_id",
    "analytics_build_run_id",
    "subscription_key",
    "user_key",
    "installation_key",
    "trial_started_at",
    "trial_ends_at",
    "prediction_at",
    "label_ready_at",
    "observation_cutoff_at",
    "price_gbp",
    "max_observed_trial_activity_at",
)

DATASET_COLUMNS = (
    *AUDIT_COLUMNS,
    *PREDICTOR_COLUMNS,
    LABEL_COLUMN,
)

ALLOWED_BEHAVIOUR_EVENTS = frozenset(
    {
        "session_started",
        "feature_used",
        "paywall_viewed",
    }
)

FORBIDDEN_OUTCOME_EVENTS = frozenset(
    {
        "subscription_started",
        "subscription_renewed",
        "payment_failed",
        "cancellation_requested",
        "subscription_expired",
    }
)

FORBIDDEN_SOURCE_FIELDS = frozenset(
    {
        "status",
        "subscription_started_at",
        "subscription_started_date_key",
        "current_period_start_at",
        "current_period_end_at",
        "cancellation_requested_at",
        "expired_at",
        "expired_date_key",
        "auto_renew",
        "end_reason",
        "row_hash",
        "source_row_number",
        "validation_run_id",
    }
)


TRIAL_CONVERSION_DATASET_SQL = """
WITH eligible AS (
    SELECT
        b.ingestion_batch_id,
        b.analytics_build_run_id,
        b.subscription_key,
        b.user_key,
        b.installation_key,

        b.platform,
        b.acquisition_channel,
        b.country_code,
        b.billing_period,
        b.price_gbp,

        b.installed_at,
        b.signed_up_at,
        b.onboarding_started_at,
        b.onboarding_completed_at,

        b.trial_started_at,
        b.trial_ends_at,

        b.trial_ends_at
            - INTERVAL '48 hours'
            AS prediction_at,

        b.trial_ends_at
            + INTERVAL '72 hours'
            AS label_ready_at,

        b.observation_cutoff_at,
        b.converted_to_paid

    FROM reporting.vw_trial_conversion_prediction_base b

    WHERE b.is_mature_trial
      AND b.trial_ends_at + INTERVAL '72 hours'
          <= b.observation_cutoff_at
),
activity AS (
    SELECT
        e.ingestion_batch_id,
        e.analytics_build_run_id,
        e.subscription_key,

        COUNT(pe.product_event_key)
            FILTER (
                WHERE pe.occurred_at < e.trial_started_at
                  AND pe.event_name = 'session_started'
            )::integer
            AS pretrial_session_count,

        COUNT(pe.product_event_key)
            FILTER (
                WHERE pe.occurred_at < e.trial_started_at
                  AND pe.event_name = 'feature_used'
            )::integer
            AS pretrial_feature_event_count,

        COUNT(pe.product_event_key)
            FILTER (
                WHERE pe.occurred_at < e.trial_started_at
                  AND pe.event_name = 'paywall_viewed'
            )::integer
            AS pretrial_paywall_view_count,

        COUNT(pe.product_event_key)
            FILTER (
                WHERE pe.occurred_at >= e.trial_started_at
                  AND pe.occurred_at <= e.prediction_at
                  AND pe.event_name = 'session_started'
            )::integer
            AS trial_session_count,

        COUNT(pe.product_event_key)
            FILTER (
                WHERE pe.occurred_at >= e.trial_started_at
                  AND pe.occurred_at <= e.prediction_at
                  AND pe.event_name = 'feature_used'
            )::integer
            AS trial_feature_event_count,

        COUNT(
            DISTINCT pe.occurred_at::date
        )
            FILTER (
                WHERE pe.occurred_at >= e.trial_started_at
                  AND pe.occurred_at <= e.prediction_at
                  AND pe.event_name IN (
                      'session_started',
                      'feature_used'
                  )
            )::integer
            AS trial_active_day_count,

        COUNT(
            DISTINCT pe.feature_name
        )
            FILTER (
                WHERE pe.occurred_at >= e.trial_started_at
                  AND pe.occurred_at <= e.prediction_at
                  AND pe.event_name = 'feature_used'
                  AND pe.feature_name IS NOT NULL
            )::integer
            AS trial_distinct_feature_count,

        MAX(pe.occurred_at)
            FILTER (
                WHERE pe.occurred_at >= e.trial_started_at
                  AND pe.occurred_at <= e.prediction_at
                  AND pe.event_name IN (
                      'session_started',
                      'feature_used'
                  )
            )
            AS max_observed_trial_activity_at

    FROM eligible e

    LEFT JOIN analytics.fact_product_event pe
        ON pe.user_key = e.user_key
       AND pe.ingestion_batch_id = e.ingestion_batch_id
       AND pe.analytics_build_run_id = e.analytics_build_run_id
       AND pe.occurred_at >= e.signed_up_at
       AND pe.occurred_at <= e.prediction_at
       AND pe.event_name IN (
           'session_started',
           'feature_used',
           'paywall_viewed'
       )

    GROUP BY
        e.ingestion_batch_id,
        e.analytics_build_run_id,
        e.subscription_key
)
SELECT
    e.ingestion_batch_id,
    e.analytics_build_run_id,
    e.subscription_key,
    e.user_key,
    e.installation_key,

    e.trial_started_at,
    e.trial_ends_at,
    e.prediction_at,
    e.label_ready_at,
    e.observation_cutoff_at,

    e.price_gbp,

    a.max_observed_trial_activity_at,

    e.platform,
    e.acquisition_channel,
    e.country_code,
    e.billing_period,

    (
        EXTRACT(
            EPOCH FROM (
                e.signed_up_at - e.installed_at
            )
        ) / 3600.0
    )::double precision
        AS install_to_signup_hours,

    (
        EXTRACT(
            EPOCH FROM (
                e.trial_started_at - e.signed_up_at
            )
        ) / 3600.0
    )::double precision
        AS signup_to_trial_hours,

    CASE
        WHEN e.onboarding_started_at IS NOT NULL
         AND e.onboarding_started_at <= e.prediction_at
        THEN 1
        ELSE 0
    END
        AS onboarding_started_before_prediction,

    CASE
        WHEN e.onboarding_completed_at IS NOT NULL
         AND e.onboarding_completed_at <= e.prediction_at
        THEN 1
        ELSE 0
    END
        AS onboarding_completed_before_prediction,

    a.pretrial_session_count,
    a.pretrial_feature_event_count,
    a.pretrial_paywall_view_count,

    a.trial_session_count,
    a.trial_feature_event_count,
    a.trial_active_day_count,
    a.trial_distinct_feature_count,

    CASE
        WHEN a.max_observed_trial_activity_at IS NULL
        THEN NULL
        ELSE (
            EXTRACT(
                EPOCH FROM (
                    e.prediction_at
                    - a.max_observed_trial_activity_at
                )
            ) / 3600.0
        )::double precision
    END
        AS hours_since_last_trial_activity,

    CASE
        WHEN e.converted_to_paid
        THEN 1
        ELSE 0
    END
        AS converted_to_paid

FROM eligible e

JOIN activity a
    ON a.ingestion_batch_id = e.ingestion_batch_id
   AND a.analytics_build_run_id = e.analytics_build_run_id
   AND a.subscription_key = e.subscription_key

ORDER BY
    e.trial_started_at,
    e.subscription_key
"""


REPORTING_RECONCILIATION_SQL = """
WITH row_level AS (
    SELECT
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
        )::bigint AS mature_paid_conversion_count
    FROM reporting.vw_trial_conversion_prediction_base
),
cohort AS (
    SELECT
        SUM(trial_count)::bigint AS trial_count,
        SUM(mature_trial_count)::bigint
            AS mature_trial_count,
        SUM(immature_trial_count)::bigint
            AS immature_trial_count,
        SUM(
            mature_trial_paid_conversion_count
        )::bigint
            AS mature_paid_conversion_count
    FROM reporting.vw_trial_conversion_cohorts
)
SELECT
    r.trial_count AS row_trial_count,
    c.trial_count AS cohort_trial_count,

    r.mature_trial_count AS row_mature_trial_count,
    c.mature_trial_count AS cohort_mature_trial_count,

    r.immature_trial_count AS row_immature_trial_count,
    c.immature_trial_count AS cohort_immature_trial_count,

    r.mature_paid_conversion_count
        AS row_mature_paid_conversion_count,
    c.mature_paid_conversion_count
        AS cohort_mature_paid_conversion_count

FROM row_level r
CROSS JOIN cohort c
"""


@dataclass(frozen=True)
class DatasetSummary:
    """Validated point-in-time dataset summary."""

    row_count: int
    converted_count: int
    not_converted_count: int
    conversion_rate: float
    earliest_prediction_at: datetime
    latest_prediction_at: datetime
    zero_trial_session_count: int
    zero_trial_feature_count: int


def load_trial_conversion_rows(
    connection: Connection,
) -> list[dict[str, Any]]:
    """Load the Phase 6 point-in-time modelling population."""

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(TRIAL_CONVERSION_DATASET_SQL)
        return [
            dict(row)
            for row in cursor.fetchall()
        ]


def load_reporting_reconciliation(
    connection: Connection,
) -> dict[str, Any]:
    """Reconcile the row-level label contract to the canonical cohort mart."""

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(REPORTING_RECONCILIATION_SQL)
        row = cursor.fetchone()

    if row is None:
        raise ValueError(
            "Trial-conversion reporting reconciliation returned no row."
        )

    return dict(row)


def validate_reporting_reconciliation(
    reconciliation: Mapping[str, Any],
) -> None:
    """Require exact row-level to canonical-cohort reconciliation."""

    pairs = (
        (
            "row_trial_count",
            "cohort_trial_count",
        ),
        (
            "row_mature_trial_count",
            "cohort_mature_trial_count",
        ),
        (
            "row_immature_trial_count",
            "cohort_immature_trial_count",
        ),
        (
            "row_mature_paid_conversion_count",
            "cohort_mature_paid_conversion_count",
        ),
    )

    for row_key, cohort_key in pairs:
        if reconciliation[row_key] != reconciliation[cohort_key]:
            raise ValueError(
                "Trial-conversion reporting reconciliation failed: "
                f"{row_key}={reconciliation[row_key]!r}, "
                f"{cohort_key}={reconciliation[cohort_key]!r}."
            )


def validate_trial_conversion_rows(
    rows: Sequence[Mapping[str, Any]],
) -> DatasetSummary:
    """Validate leakage, maturity and point-in-time dataset invariants."""

    if not rows:
        raise ValueError(
            "Trial-conversion modelling dataset is empty."
        )

    expected_columns = set(DATASET_COLUMNS)
    seen_subscription_keys: set[Any] = set()

    converted_count = 0
    zero_trial_session_count = 0
    zero_trial_feature_count = 0

    earliest_prediction_at: datetime | None = None
    latest_prediction_at: datetime | None = None

    count_columns = (
        "pretrial_session_count",
        "pretrial_feature_event_count",
        "pretrial_paywall_view_count",
        "trial_session_count",
        "trial_feature_event_count",
        "trial_active_day_count",
        "trial_distinct_feature_count",
    )

    def as_utc(
        value: datetime,
        field_name: str,
    ) -> datetime:
        """Normalize an aware timestamp for absolute elapsed-time checks."""

        if value.tzinfo is None:
            raise ValueError(
                f"{field_name} must be timezone-aware."
            )

        return value.astimezone(timezone.utc)

    for row_number, row in enumerate(rows, start=1):
        actual_columns = set(row)

        if actual_columns != expected_columns:
            missing = sorted(
                expected_columns - actual_columns
            )
            extra = sorted(
                actual_columns - expected_columns
            )

            raise ValueError(
                "Unexpected modelling dataset schema at "
                f"row {row_number}: "
                f"missing={missing}, extra={extra}."
            )

        leaked_fields = (
            FORBIDDEN_SOURCE_FIELDS
            & actual_columns
        )

        if leaked_fields:
            raise ValueError(
                "Forbidden source fields leaked into modelling "
                f"dataset: {sorted(leaked_fields)}"
            )

        subscription_key = row["subscription_key"]

        if subscription_key in seen_subscription_keys:
            raise ValueError(
                "Duplicate subscription_key in modelling dataset: "
                f"{subscription_key}"
            )

        seen_subscription_keys.add(
            subscription_key
        )

        trial_started_at = row["trial_started_at"]
        trial_ends_at = row["trial_ends_at"]
        prediction_at = row["prediction_at"]
        label_ready_at = row["label_ready_at"]
        observation_cutoff_at = row[
            "observation_cutoff_at"
        ]

        trial_started_utc = as_utc(
            trial_started_at,
            "trial_started_at",
        )
        trial_ends_utc = as_utc(
            trial_ends_at,
            "trial_ends_at",
        )
        prediction_utc = as_utc(
            prediction_at,
            "prediction_at",
        )
        label_ready_utc = as_utc(
            label_ready_at,
            "label_ready_at",
        )
        observation_cutoff_utc = as_utc(
            observation_cutoff_at,
            "observation_cutoff_at",
        )

        observed_trial_duration = (
            trial_ends_utc
            - trial_started_utc
        )

        if observed_trial_duration != timedelta(days=7):
            raise ValueError(
                "Trial duration differs from the approved "
                "seven-day elapsed-time contract for "
                f"subscription_key={subscription_key}: "
                f"{observed_trial_duration!r}."
            )

        expected_prediction_utc = (
            trial_ends_utc
            - timedelta(
                hours=PREDICTION_LEAD_HOURS
            )
        )

        if prediction_utc != expected_prediction_utc:
            raise ValueError(
                "prediction_at does not equal trial end minus "
                f"{PREDICTION_LEAD_HOURS} elapsed hours."
            )

        expected_label_ready_utc = (
            trial_ends_utc
            + timedelta(
                hours=24 * LABEL_MATURITY_DAYS
            )
        )

        if label_ready_utc != expected_label_ready_utc:
            raise ValueError(
                "label_ready_at does not match the supervised "
                "72-hour maturity buffer."
            )

        if label_ready_utc > observation_cutoff_utc:
            raise ValueError(
                "Right-censored row entered the modelling dataset."
            )

        max_activity_at = row[
            "max_observed_trial_activity_at"
        ]

        if max_activity_at is not None:
            max_activity_utc = as_utc(
                max_activity_at,
                "max_observed_trial_activity_at",
            )

            if max_activity_utc > prediction_utc:
                raise ValueError(
                    "Post-prediction product activity leaked "
                    "into the modelling dataset."
                )

        target = row[LABEL_COLUMN]

        if target not in (0, 1):
            raise ValueError(
                f"{LABEL_COLUMN} must be binary."
            )

        converted_count += int(target)

        for column in count_columns:
            value = row[column]

            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            ):
                raise ValueError(
                    f"{column} must be a non-negative integer."
                )

        if (
            row["trial_distinct_feature_count"]
            > row["trial_feature_event_count"]
        ):
            raise ValueError(
                "Distinct trial features exceed trial feature "
                "event count."
            )

        if (
            row["onboarding_completed_before_prediction"] == 1
            and row[
                "onboarding_started_before_prediction"
            ] != 1
        ):
            raise ValueError(
                "Onboarding completion cannot precede "
                "onboarding start."
            )

        for column in (
            "install_to_signup_hours",
            "signup_to_trial_hours",
        ):
            value = row[column]

            if value is None or value < 0:
                raise ValueError(
                    f"{column} must be non-negative."
                )

        recency = row[
            "hours_since_last_trial_activity"
        ]

        if max_activity_at is None:
            if recency is not None:
                raise ValueError(
                    "Activity recency must be NULL when no "
                    "trial activity was observed."
                )

        else:
            if recency is None or recency < 0:
                raise ValueError(
                    "Activity recency must be non-negative "
                    "when trial activity exists."
                )

            if recency > 120.000001:
                raise ValueError(
                    "Trial activity recency exceeds the "
                    "five-day prediction window."
                )

        if row["trial_session_count"] == 0:
            zero_trial_session_count += 1

        if row["trial_feature_event_count"] == 0:
            zero_trial_feature_count += 1

        if (
            earliest_prediction_at is None
            or prediction_utc
            < as_utc(
                earliest_prediction_at,
                "earliest_prediction_at",
            )
        ):
            earliest_prediction_at = prediction_at

        if (
            latest_prediction_at is None
            or prediction_utc
            > as_utc(
                latest_prediction_at,
                "latest_prediction_at",
            )
        ):
            latest_prediction_at = prediction_at

    if (
        earliest_prediction_at is None
        or latest_prediction_at is None
    ):
        raise ValueError(
            "Prediction timestamp range could not be established."
        )

    row_count = len(rows)
    not_converted_count = (
        row_count - converted_count
    )

    return DatasetSummary(
        row_count=row_count,
        converted_count=converted_count,
        not_converted_count=not_converted_count,
        conversion_rate=(
            converted_count / row_count
        ),
        earliest_prediction_at=earliest_prediction_at,
        latest_prediction_at=latest_prediction_at,
        zero_trial_session_count=zero_trial_session_count,
        zero_trial_feature_count=zero_trial_feature_count,
    )
