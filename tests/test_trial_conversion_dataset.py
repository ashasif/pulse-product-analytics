"""Tests for the Phase 6 point-in-time trial-conversion dataset."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import unittest

from src.analysis.trial_conversion_dataset import (
    DATASET_COLUMNS,
    FORBIDDEN_OUTCOME_EVENTS,
    FORBIDDEN_SOURCE_FIELDS,
    LABEL_COLUMN,
    PREDICTION_LEAD_HOURS,
    PREDICTOR_COLUMNS,
    TRIAL_CONVERSION_DATASET_SQL,
    validate_trial_conversion_rows,
)


class TrialConversionDatasetTests(unittest.TestCase):
    """Protect feature, maturity and leakage contracts."""

    def _valid_row(self):
        trial_started_at = datetime(
            2025,
            1,
            1,
            12,
            0,
            tzinfo=timezone.utc,
        )
        trial_ends_at = (
            trial_started_at
            + timedelta(days=7)
        )
        prediction_at = (
            trial_ends_at
            - timedelta(hours=48)
        )
        label_ready_at = (
            trial_ends_at
            + timedelta(hours=72)
        )

        return {
            "ingestion_batch_id": 1,
            "analytics_build_run_id": 1,
            "subscription_key": 101,
            "user_key": 201,
            "installation_key": 301,

            "trial_started_at": trial_started_at,
            "trial_ends_at": trial_ends_at,
            "prediction_at": prediction_at,
            "label_ready_at": label_ready_at,
            "observation_cutoff_at": (
                label_ready_at
                + timedelta(days=30)
            ),

            "price_gbp": Decimal("11.99"),
            "max_observed_trial_activity_at": (
                prediction_at
                - timedelta(hours=2)
            ),

            "platform": "ios",
            "acquisition_channel": "organic",
            "country_code": "GB",
            "billing_period": "monthly",

            "install_to_signup_hours": 48.0,
            "signup_to_trial_hours": 72.0,
            "onboarding_started_before_prediction": 1,
            "onboarding_completed_before_prediction": 1,

            "pretrial_session_count": 3,
            "pretrial_feature_event_count": 8,
            "pretrial_paywall_view_count": 2,

            "trial_session_count": 2,
            "trial_feature_event_count": 5,
            "trial_active_day_count": 2,
            "trial_distinct_feature_count": 3,
            "hours_since_last_trial_activity": 2.0,

            LABEL_COLUMN: 1,
        }

    def test_predictor_contract_is_intentionally_small(self):
        self.assertEqual(
            len(PREDICTOR_COLUMNS),
            16,
        )

    def test_forbidden_source_fields_are_not_predictors(self):
        self.assertFalse(
            set(PREDICTOR_COLUMNS)
            & FORBIDDEN_SOURCE_FIELDS
        )

    def test_price_is_audit_context_not_predictor(self):
        self.assertIn(
            "price_gbp",
            DATASET_COLUMNS,
        )
        self.assertNotIn(
            "price_gbp",
            PREDICTOR_COLUMNS,
        )

    def test_dataset_sql_uses_reporting_label_contract(self):
        self.assertIn(
            "reporting.vw_trial_conversion_prediction_base",
            TRIAL_CONVERSION_DATASET_SQL,
        )

    def test_dataset_sql_applies_strict_label_maturity(self):
        compact = " ".join(
            TRIAL_CONVERSION_DATASET_SQL.lower().split()
        )
        self.assertIn(
            "trial_ends_at + interval '72 hours' "
            "<= b.observation_cutoff_at",
            compact,
        )

    def test_dataset_sql_limits_events_to_prediction_time(self):
        compact = " ".join(
            TRIAL_CONVERSION_DATASET_SQL.lower().split()
        )
        self.assertIn(
            "pe.occurred_at <= e.prediction_at",
            compact,
        )

    def test_forbidden_outcome_events_are_not_used(self):
        lower_sql = (
            TRIAL_CONVERSION_DATASET_SQL.lower()
        )
        for event_name in FORBIDDEN_OUTCOME_EVENTS:
            self.assertNotIn(
                f"'{event_name}'",
                lower_sql,
            )

    def test_valid_row_passes(self):
        summary = validate_trial_conversion_rows(
            [self._valid_row()]
        )

        self.assertEqual(
            summary.row_count,
            1,
        )
        self.assertEqual(
            summary.converted_count,
            1,
        )

    def test_post_prediction_activity_fails(self):
        row = self._valid_row()
        row["max_observed_trial_activity_at"] = (
            row["prediction_at"]
            + timedelta(seconds=1)
        )

        with self.assertRaisesRegex(
            ValueError,
            "Post-prediction",
        ):
            validate_trial_conversion_rows(
                [row]
            )

    def test_right_censored_label_fails(self):
        row = self._valid_row()
        row["observation_cutoff_at"] = (
            row["label_ready_at"]
            - timedelta(seconds=1)
        )

        with self.assertRaisesRegex(
            ValueError,
            "Right-censored",
        ):
            validate_trial_conversion_rows(
                [row]
            )

    def test_duplicate_subscription_fails(self):
        row = self._valid_row()

        with self.assertRaisesRegex(
            ValueError,
            "Duplicate subscription_key",
        ):
            validate_trial_conversion_rows(
                [row, dict(row)]
            )

    def test_prediction_timestamp_is_fixed_at_day_five(self):
        row = self._valid_row()

        self.assertEqual(
            row["prediction_at"],
            row["trial_ends_at"]
            - timedelta(
                hours=PREDICTION_LEAD_HOURS
            ),
        )



def test_dst_crossing_trial_uses_absolute_elapsed_time(self):
    london = ZoneInfo("Europe/London")

    row = self._valid_row()

    # UK spring DST starts during this trial.
    # 12:00 GMT -> 13:00 BST seven elapsed days later.
    trial_started_at = datetime(
        2025,
        3,
        27,
        12,
        0,
        tzinfo=london,
    )

    trial_ends_at = datetime(
        2025,
        4,
        3,
        13,
        0,
        tzinfo=london,
    )

    prediction_utc = (
        trial_ends_at.astimezone(timezone.utc)
        - timedelta(
            hours=PREDICTION_LEAD_HOURS
        )
    )

    label_ready_utc = (
        trial_ends_at.astimezone(timezone.utc)
        + timedelta(hours=72)
    )

    row["trial_started_at"] = (
        trial_started_at
    )
    row["trial_ends_at"] = trial_ends_at
    row["prediction_at"] = (
        prediction_utc.astimezone(london)
    )
    row["label_ready_at"] = (
        label_ready_utc.astimezone(london)
    )
    row["observation_cutoff_at"] = (
        label_ready_utc
        + timedelta(days=30)
    ).astimezone(london)

    row[
        "max_observed_trial_activity_at"
    ] = (
        prediction_utc
        - timedelta(hours=2)
    ).astimezone(london)

    row[
        "hours_since_last_trial_activity"
    ] = 2.0

    summary = (
        validate_trial_conversion_rows(
            [row]
        )
    )

    self.assertEqual(
        summary.row_count,
        1,
    )


if __name__ == "__main__":
    unittest.main()