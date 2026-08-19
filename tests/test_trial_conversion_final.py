"""Tests for locked Phase 6 final evaluation."""

from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import numpy as np

from src.analysis.trial_conversion_baselines import (
    BaselineMetrics,
)
from src.analysis.trial_conversion_final import (
    HoldoutResult,
    MODEL_BEHAVIOURAL_LOGISTIC,
    MODEL_STATIC_LOGISTIC,
    behavioural_generalisation_confirmed,
    fit_locked_models,
    paired_bootstrap_deltas,
    score_locked_models,
    write_results_once,
)


class TrialConversionFinalTests(unittest.TestCase):
    """Protect final-holdout evaluation mechanics."""

    def _row(
        self,
        key,
        target,
    ):
        return {
            "subscription_key": key,

            "trial_started_at": datetime(
                2025,
                1,
                (key % 27) + 1,
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
                5.0 + key,

            "signup_to_trial_hours":
                10.0 + key,

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
                2 + target * 3,

            "trial_feature_event_count":
                4 + target * 4,

            "trial_active_day_count":
                1 + target,

            "trial_distinct_feature_count":
                1 + target,

            "hours_since_last_trial_activity":
                4.0,
        }

    def _rows(
        self,
        start,
        count,
    ):
        rows = []

        for key in range(
            start,
            start + count,
        ):

            target = int(
                key % 3 == 0
                or key % 7 == 0
            )

            rows.append(
                self._row(
                    key,
                    target,
                )
            )

        return rows

    def _result(
        self,
        name,
        brier,
        logloss,
    ):
        return HoldoutResult(
            model_name=name,
            metrics=BaselineMetrics(
                brier_score=brier,
                log_loss=logloss,
                roc_auc=0.60,
                average_precision=0.50,
            ),
            probability_mean=0.40,
            observed_rate=0.40,
            probability_min=0.10,
            probability_max=0.80,
        )

    def test_locked_models_fit_and_score(self):

        development = self._rows(
            1,
            120,
        )

        evaluation = self._rows(
            1001,
            50,
        )

        models = fit_locked_models(
            development
        )

        results, probabilities = score_locked_models(
            models,
            evaluation,
        )

        self.assertEqual(
            set(results),
            {
                "prevalence",
                "static_logistic",
                "behavioural_logistic",
            },
        )

        self.assertEqual(
            len(
                probabilities[
                    MODEL_BEHAVIOURAL_LOGISTIC
                ]
            ),
            50,
        )

    def test_generalisation_requires_brier_and_log_loss(self):

        passing = {
            MODEL_STATIC_LOGISTIC:
                self._result(
                    MODEL_STATIC_LOGISTIC,
                    0.24,
                    0.67,
                ),

            MODEL_BEHAVIOURAL_LOGISTIC:
                self._result(
                    MODEL_BEHAVIOURAL_LOGISTIC,
                    0.23,
                    0.66,
                ),
        }

        failing = {
            MODEL_STATIC_LOGISTIC:
                self._result(
                    MODEL_STATIC_LOGISTIC,
                    0.24,
                    0.67,
                ),

            MODEL_BEHAVIOURAL_LOGISTIC:
                self._result(
                    MODEL_BEHAVIOURAL_LOGISTIC,
                    0.23,
                    0.68,
                ),
        }

        self.assertTrue(
            behavioural_generalisation_confirmed(
                passing
            )
        )

        self.assertFalse(
            behavioural_generalisation_confirmed(
                failing
            )
        )

    def test_paired_bootstrap_is_deterministic(self):

        targets = [
            index % 2
            for index in range(200)
        ]

        static = np.asarray(
            [
                0.45
                if target
                else 0.35
                for target in targets
            ]
        )

        behavioural = np.asarray(
            [
                0.60
                if target
                else 0.25
                for target in targets
            ]
        )

        first = paired_bootstrap_deltas(
            targets,
            behavioural,
            static,
            replicates=200,
            seed=123,
        )

        second = paired_bootstrap_deltas(
            targets,
            behavioural,
            static,
            replicates=200,
            seed=123,
        )

        self.assertEqual(
            first,
            second,
        )

        self.assertLess(
            first.brier_delta,
            0.0,
        )

        self.assertLess(
            first.log_loss_delta,
            0.0,
        )

    def test_results_writer_refuses_overwrite(self):

        with tempfile.TemporaryDirectory() as directory:

            path = (
                Path(directory)
                / "final.md"
            )

            write_results_once(
                path,
                "first",
            )

            with self.assertRaises(
                FileExistsError
            ):
                write_results_once(
                    path,
                    "second",
                )

            self.assertEqual(
                path.read_text(
                    encoding="utf-8"
                ),
                "first\n",
            )


if __name__ == "__main__":
    unittest.main()
