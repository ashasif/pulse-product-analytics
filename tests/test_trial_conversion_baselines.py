"""Tests for Phase 6 temporal splits, baselines and preprocessing."""

from datetime import datetime, timezone
import unittest

from src.analysis.trial_conversion_baselines import (
    PREDICTOR_COLUMNS,
    STATIC_BASELINE_FEATURES,
    assign_temporal_split,
    build_linear_preprocessor,
    build_static_logistic_pipeline,
    evaluate_probabilities,
    feature_matrix,
    fit_prevalence_baseline,
    prevalence_predictions,
    split_rows,
    target_vector,
    validate_temporal_splits,
)


class TrialConversionBaselineTests(unittest.TestCase):
    """Protect temporal and baseline evaluation contracts."""

    def _row(
        self,
        key,
        started,
        target,
        *,
        platform="ios",
        channel="organic",
        country="GB",
        billing="monthly",
        recency=5.0,
    ):
        return {
            "subscription_key": key,
            "trial_started_at": datetime(
                *started,
                tzinfo=timezone.utc,
            ),
            "converted_to_paid": target,

            "platform": platform,
            "acquisition_channel": channel,
            "country_code": country,
            "billing_period": billing,

            "install_to_signup_hours": 24.0 + key,
            "signup_to_trial_hours": 48.0 + key,
            "onboarding_started_before_prediction": (
                key % 2
            ),
            "onboarding_completed_before_prediction": (
                key % 2
            ),

            "pretrial_session_count": key % 4,
            "pretrial_feature_event_count": key % 7,
            "pretrial_paywall_view_count": key % 3,

            "trial_session_count": key % 5,
            "trial_feature_event_count": key % 8,
            "trial_active_day_count": key % 4,
            "trial_distinct_feature_count": key % 5,
            "hours_since_last_trial_activity": recency,
        }

    def test_frozen_temporal_boundaries(self):
        cases = (
            (
                (2025, 6, 30, 23, 59),
                "train",
            ),
            (
                (2025, 7, 1, 0, 0),
                "validation",
            ),
            (
                (2026, 1, 1, 0, 0),
                "test",
            ),
            (
                (2026, 6, 1, 0, 0),
                "excluded",
            ),
        )

        for index, (timestamp, expected) in enumerate(
            cases,
            start=1,
        ):
            row = self._row(
                index,
                timestamp,
                index % 2,
            )

            self.assertEqual(
                assign_temporal_split(row),
                expected,
            )

    def test_static_baseline_is_subset_of_predictors(self):
        self.assertTrue(
            set(STATIC_BASELINE_FEATURES)
            < set(PREDICTOR_COLUMNS)
        )

        behavioural = {
            "trial_session_count",
            "trial_feature_event_count",
            "trial_active_day_count",
            "trial_distinct_feature_count",
            "hours_since_last_trial_activity",
        }

        self.assertFalse(
            set(STATIC_BASELINE_FEATURES)
            & behavioural
        )

    def test_prevalence_uses_training_labels_only(self):
        rows = [
            self._row(
                1,
                (2025, 1, 1, 0, 0),
                1,
            ),
            self._row(
                2,
                (2025, 1, 2, 0, 0),
                0,
            ),
            self._row(
                3,
                (2025, 1, 3, 0, 0),
                1,
            ),
        ]

        self.assertAlmostEqual(
            fit_prevalence_baseline(rows),
            2 / 3,
        )

    def test_preprocessor_handles_unseen_categories(self):
        training = [
            self._row(
                1,
                (2025, 1, 1, 0, 0),
                0,
                country="GB",
                recency=5.0,
            ),
            self._row(
                2,
                (2025, 1, 2, 0, 0),
                1,
                country="US",
                recency=None,
            ),
        ]

        validation = [
            self._row(
                3,
                (2025, 8, 1, 0, 0),
                1,
                country="DE",
                channel="content",
                recency=None,
            )
        ]

        preprocessor = build_linear_preprocessor(
            PREDICTOR_COLUMNS
        )

        transformed_training = (
            preprocessor.fit_transform(
                feature_matrix(
                    training,
                    PREDICTOR_COLUMNS,
                )
            )
        )

        transformed_validation = (
            preprocessor.transform(
                feature_matrix(
                    validation,
                    PREDICTOR_COLUMNS,
                )
            )
        )

        self.assertEqual(
            transformed_training.shape[0],
            2,
        )
        self.assertEqual(
            transformed_validation.shape[0],
            1,
        )

    def test_static_logistic_pipeline_returns_probabilities(self):
        rows = [
            self._row(
                1,
                (2025, 1, 1, 0, 0),
                0,
                platform="ios",
            ),
            self._row(
                2,
                (2025, 1, 2, 0, 0),
                1,
                platform="android",
            ),
            self._row(
                3,
                (2025, 1, 3, 0, 0),
                0,
                channel="paid_search",
            ),
            self._row(
                4,
                (2025, 1, 4, 0, 0),
                1,
                channel="referral",
            ),
        ]

        pipeline = (
            build_static_logistic_pipeline()
        )

        pipeline.fit(
            feature_matrix(
                rows,
                STATIC_BASELINE_FEATURES,
            ),
            target_vector(
                rows
            ),
        )

        probabilities = (
            pipeline.predict_proba(
                feature_matrix(
                    rows,
                    STATIC_BASELINE_FEATURES,
                )
            )[:, 1]
        )

        self.assertEqual(
            len(probabilities),
            4,
        )

        for probability in probabilities:
            self.assertGreaterEqual(
                probability,
                0.0,
            )
            self.assertLessEqual(
                probability,
                1.0,
            )

    def test_temporal_split_validation_rejects_overlap(self):
        rows = [
            self._row(
                1,
                (2024, 1, 1, 0, 0),
                0,
            ),
            self._row(
                2,
                (2024, 1, 2, 0, 0),
                1,
            ),
            self._row(
                3,
                (2025, 7, 1, 0, 0),
                0,
            ),
            self._row(
                4,
                (2025, 7, 2, 0, 0),
                1,
            ),
            self._row(
                5,
                (2026, 1, 1, 0, 0),
                0,
            ),
            self._row(
                6,
                (2026, 1, 2, 0, 0),
                1,
            ),
            self._row(
                7,
                (2026, 6, 1, 0, 0),
                0,
            ),
            self._row(
                8,
                (2026, 6, 2, 0, 0),
                1,
            ),
        ]

        splits = split_rows(rows)

        validate_temporal_splits(
            splits
        )

        splits["validation"].append(
            rows[0]
        )

        with self.assertRaisesRegex(
            ValueError,
            "more than one temporal split",
        ):
            validate_temporal_splits(
                splits
            )

    def test_probability_metrics_are_defined(self):
        y_true = [
            0,
            1,
            0,
            1,
        ]

        probabilities = [
            0.2,
            0.7,
            0.4,
            0.8,
        ]

        metrics = evaluate_probabilities(
            y_true,
            probabilities,
        )

        self.assertGreater(
            metrics.brier_score,
            0.0,
        )
        self.assertLess(
            metrics.brier_score,
            1.0,
        )
        self.assertGreater(
            metrics.roc_auc,
            0.5,
        )

    def test_constant_prevalence_prediction(self):
        predictions = prevalence_predictions(
            0.37,
            3,
        )

        self.assertEqual(
            predictions,
            [
                0.37,
                0.37,
                0.37,
            ],
        )


if __name__ == "__main__":
    unittest.main()