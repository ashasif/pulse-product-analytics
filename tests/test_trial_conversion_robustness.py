"""Tests for Phase 6 calibration, decision utility and robustness."""

from datetime import datetime, timezone
import unittest

import numpy as np

from src.analysis.trial_conversion_baselines import (
    BaselineMetrics,
)
from src.analysis.trial_conversion_robustness import (
    CALIBRATION_ISOTONIC,
    CALIBRATION_NONE,
    CALIBRATION_SIGMOID,
    CalibrationResult,
    reliability_bins,
    select_calibration_method,
    targeting_utility,
    temporal_oof_probabilities,
    validation_robustness,
)


class TrialConversionRobustnessTests(unittest.TestCase):
    """Protect Step 5 evaluation contracts."""

    def _result(
        self,
        method,
        brier,
        logloss,
    ):
        return CalibrationResult(
            method=method,
            metrics=BaselineMetrics(
                brier_score=brier,
                log_loss=logloss,
                roc_auc=0.60,
                average_precision=0.50,
            ),
            probability_mean=0.40,
            observed_rate=0.40,
            mean_probability_bias=0.0,
        )

    def _row(
        self,
        key,
        month,
        target,
    ):
        return {
            "subscription_key": key,
            "trial_started_at": datetime(
                2025,
                month,
                (key % 20) + 1,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            "converted_to_paid": target,

            "platform":
                "ios"
                if key % 2
                else "android",

            "acquisition_channel":
                "organic"
                if key % 3
                else "paid_search",

            "country_code":
                "GB"
                if key % 2
                else "US",

            "billing_period":
                "monthly"
                if key % 4
                else "annual",

            "install_to_signup_hours":
                10.0 + key,

            "signup_to_trial_hours":
                20.0 + key,

            "onboarding_started_before_prediction":
                1,

            "onboarding_completed_before_prediction":
                target,

            "pretrial_session_count":
                key % 4,

            "pretrial_feature_event_count":
                key % 6,

            "pretrial_paywall_view_count":
                key % 3,

            "trial_session_count":
                1 + target * 2,

            "trial_feature_event_count":
                2 + target * 3,

            "trial_active_day_count":
                1 + target,

            "trial_distinct_feature_count":
                1 + target,

            "hours_since_last_trial_activity":
                3.0,
        }

    def test_calibration_selection_requires_both_metrics(self):
        results = {
            CALIBRATION_NONE:
                self._result(
                    CALIBRATION_NONE,
                    0.23,
                    0.66,
                ),

            CALIBRATION_SIGMOID:
                self._result(
                    CALIBRATION_SIGMOID,
                    0.22,
                    0.65,
                ),

            CALIBRATION_ISOTONIC:
                self._result(
                    CALIBRATION_ISOTONIC,
                    0.21,
                    0.67,
                ),
        }

        self.assertEqual(
            select_calibration_method(
                results
            ),
            CALIBRATION_SIGMOID,
        )

    def test_no_calibration_is_preferred_without_joint_gain(self):
        results = {
            CALIBRATION_NONE:
                self._result(
                    CALIBRATION_NONE,
                    0.23,
                    0.66,
                ),

            CALIBRATION_SIGMOID:
                self._result(
                    CALIBRATION_SIGMOID,
                    0.23,
                    0.65,
                ),

            CALIBRATION_ISOTONIC:
                self._result(
                    CALIBRATION_ISOTONIC,
                    0.22,
                    0.67,
                ),
        }

        self.assertEqual(
            select_calibration_method(
                results
            ),
            CALIBRATION_NONE,
        )

    def test_reliability_bins_cover_population(self):
        targets = [
            index % 2
            for index in range(100)
        ]

        probabilities = np.linspace(
            0.05,
            0.95,
            100,
        )

        bins = reliability_bins(
            targets,
            probabilities,
            bin_count=10,
        )

        self.assertEqual(
            len(bins),
            10,
        )

        self.assertEqual(
            sum(
                item.row_count
                for item in bins
            ),
            100,
        )

    def test_targeting_prioritises_high_risk(self):
        targets = [
            0,
            0,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
            1,
        ]

        conversion_probabilities = [
            0.05,
            0.10,
            0.80,
            0.82,
            0.84,
            0.86,
            0.88,
            0.90,
            0.92,
            0.94,
        ]

        result = targeting_utility(
            targets,
            conversion_probabilities,
            capacities=(0.20,),
        )[0]

        self.assertEqual(
            result.targeted_non_conversions,
            2,
        )

        self.assertEqual(
            result.non_conversion_capture_rate,
            1.0,
        )

        self.assertGreater(
            result.lift_vs_population,
            1.0,
        )

    def test_validation_robustness_covers_all_rows(self):
        rows = [
            self._row(
                index,
                7 + (index % 6),
                index % 2,
            )
            for index in range(
                1,
                121,
            )
        ]

        probabilities = np.asarray(
            [
                0.7
                if row["converted_to_paid"]
                else 0.3
                for row in rows
            ]
        )

        output = validation_robustness(
            rows,
            probabilities,
        )

        self.assertEqual(
            set(output),
            {
                "month",
                "platform",
                "billing_period",
                "acquisition_channel",
            },
        )

        for dimension_results in output.values():
            self.assertEqual(
                sum(
                    item.row_count
                    for item in dimension_results
                ),
                len(rows),
            )

    def test_temporal_oof_uses_training_history_only(self):
        rows = []

        for index in range(
            1,
            301,
        ):
            target = int(
                index % 3 == 0
                or index % 7 == 0
            )

            row = self._row(
                index,
                ((index - 1) % 6) + 1,
                target,
            )

            # Ensure strict chronological order across the synthetic
            # test population rather than repeating the same months.
            row["trial_started_at"] = datetime(
                2024,
                1,
                1,
                0,
                0,
                tzinfo=timezone.utc,
            ).replace(
                day=((index - 1) % 28) + 1
            )

            # Use the key as a deterministic secondary ordering field.
            rows.append(row)

        targets, probabilities = (
            temporal_oof_probabilities(
                rows,
                n_splits=3,
            )
        )

        self.assertEqual(
            len(targets),
            len(probabilities),
        )

        self.assertGreater(
            len(targets),
            100,
        )

        self.assertTrue(
            np.all(
                probabilities >= 0.0
            )
        )

        self.assertTrue(
            np.all(
                probabilities <= 1.0
            )
        )


if __name__ == "__main__":
    unittest.main()
