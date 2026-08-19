"""Tests for Phase 6 behavioural model comparison."""

from datetime import datetime, timezone
import unittest

from src.analysis.trial_conversion_models import (
    MODEL_BEHAVIOURAL_LOGISTIC,
    MODEL_HIST_GRADIENT_BOOSTING,
    MODEL_STATIC_LOGISTIC,
    ValidationModelResult,
    behavioural_increment_passes,
    build_behavioural_logistic_pipeline,
    build_hist_gradient_boosting_pipeline,
    fit_validation_models,
    metric_delta,
    rank_validation_models,
)
from src.analysis.trial_conversion_baselines import (
    BaselineMetrics,
    PREDICTOR_COLUMNS,
)


class TrialConversionModelTests(unittest.TestCase):
    """Protect the approved Step 4 model-development contract."""

    def _row(
        self,
        key,
        timestamp,
        target,
        *,
        trial_sessions,
        trial_features,
    ):
        return {
            "subscription_key": key,
            "trial_started_at": datetime(
                *timestamp,
                tzinfo=timezone.utc,
            ),
            "converted_to_paid": target,

            "platform": (
                "ios"
                if key % 2
                else "android"
            ),
            "acquisition_channel": (
                "organic"
                if key % 3
                else "paid_search"
            ),
            "country_code": (
                "GB"
                if key % 2
                else "US"
            ),
            "billing_period": (
                "monthly"
                if key % 4
                else "annual"
            ),

            "install_to_signup_hours": (
                5.0 + key
            ),
            "signup_to_trial_hours": (
                10.0 + key
            ),

            "onboarding_started_before_prediction": (
                1
            ),
            "onboarding_completed_before_prediction": (
                target
            ),

            "pretrial_session_count": key % 4,
            "pretrial_feature_event_count": key % 6,
            "pretrial_paywall_view_count": key % 3,

            "trial_session_count": trial_sessions,
            "trial_feature_event_count": trial_features,
            "trial_active_day_count": min(
                5,
                trial_sessions,
            ),
            "trial_distinct_feature_count": min(
                5,
                trial_features,
            ),
            "hours_since_last_trial_activity": (
                2.0
                if trial_sessions
                else None
            ),
        }

    def _training_rows(self):
        rows = []

        for key in range(1, 81):
            target = int(
                key % 3 == 0
                or key % 7 == 0
            )

            rows.append(
                self._row(
                    key,
                    (
                        2025,
                        1,
                        (key % 27) + 1,
                        12,
                        0,
                    ),
                    target,
                    trial_sessions=(
                        3 + target * 3
                    ),
                    trial_features=(
                        6 + target * 5
                    ),
                )
            )

        return rows

    def _validation_rows(self):
        rows = []

        for offset, key in enumerate(
            range(101, 141),
            start=1,
        ):
            target = int(
                key % 3 == 0
                or key % 7 == 0
            )

            rows.append(
                self._row(
                    key,
                    (
                        2025,
                        8,
                        (offset % 27) + 1,
                        12,
                        0,
                    ),
                    target,
                    trial_sessions=(
                        3 + target * 3
                    ),
                    trial_features=(
                        6 + target * 5
                    ),
                )
            )

        return rows

    def _result(
        self,
        name,
        *,
        brier,
        log_loss,
        roc_auc,
        average_precision,
    ):
        return ValidationModelResult(
            model_name=name,
            metrics=BaselineMetrics(
                brier_score=brier,
                log_loss=log_loss,
                roc_auc=roc_auc,
                average_precision=average_precision,
            ),
            probability_min=0.1,
            probability_max=0.9,
            probability_mean=0.4,
        )

    def test_candidate_set_is_exactly_three_models(self):
        expected = {
            MODEL_STATIC_LOGISTIC,
            MODEL_BEHAVIOURAL_LOGISTIC,
            MODEL_HIST_GRADIENT_BOOSTING,
        }

        self.assertEqual(
            len(expected),
            3,
        )

    def test_behavioural_logistic_uses_all_predictors(self):
        pipeline = (
            build_behavioural_logistic_pipeline()
        )

        self.assertIn(
            "preprocessor",
            pipeline.named_steps,
        )
        self.assertIn(
            "classifier",
            pipeline.named_steps,
        )
        self.assertEqual(
            len(PREDICTOR_COLUMNS),
            16,
        )

    def test_gradient_boosting_is_single_nonlinear_challenger(self):
        pipeline = (
            build_hist_gradient_boosting_pipeline()
        )

        self.assertIn(
            "dense",
            pipeline.named_steps,
        )
        self.assertIn(
            "classifier",
            pipeline.named_steps,
        )

    def test_models_fit_and_return_all_validation_results(self):
        results = fit_validation_models(
            self._training_rows(),
            self._validation_rows(),
        )

        self.assertEqual(
            set(results),
            {
                MODEL_STATIC_LOGISTIC,
                MODEL_BEHAVIOURAL_LOGISTIC,
                MODEL_HIST_GRADIENT_BOOSTING,
            },
        )

        for result in results.values():
            self.assertGreaterEqual(
                result.probability_min,
                0.0,
            )
            self.assertLessEqual(
                result.probability_max,
                1.0,
            )

    def test_ranking_prioritises_brier_then_log_loss(self):
        results = {
            MODEL_STATIC_LOGISTIC:
                self._result(
                    MODEL_STATIC_LOGISTIC,
                    brier=0.24,
                    log_loss=0.67,
                    roc_auc=0.53,
                    average_precision=0.40,
                ),

            MODEL_BEHAVIOURAL_LOGISTIC:
                self._result(
                    MODEL_BEHAVIOURAL_LOGISTIC,
                    brier=0.21,
                    log_loss=0.61,
                    roc_auc=0.70,
                    average_precision=0.55,
                ),

            MODEL_HIST_GRADIENT_BOOSTING:
                self._result(
                    MODEL_HIST_GRADIENT_BOOSTING,
                    brier=0.21,
                    log_loss=0.60,
                    roc_auc=0.71,
                    average_precision=0.56,
                ),
        }

        ranking = rank_validation_models(
            results
        )

        self.assertEqual(
            ranking[0].model_name,
            MODEL_HIST_GRADIENT_BOOSTING,
        )

    def test_behavioural_increment_requires_brier_and_log_loss(self):
        static = self._result(
            MODEL_STATIC_LOGISTIC,
            brier=0.24,
            log_loss=0.67,
            roc_auc=0.53,
            average_precision=0.40,
        )

        good = self._result(
            MODEL_BEHAVIOURAL_LOGISTIC,
            brier=0.22,
            log_loss=0.63,
            roc_auc=0.65,
            average_precision=0.50,
        )

        bad_guardrail = self._result(
            MODEL_HIST_GRADIENT_BOOSTING,
            brier=0.22,
            log_loss=0.68,
            roc_auc=0.66,
            average_precision=0.51,
        )

        self.assertTrue(
            behavioural_increment_passes(
                good,
                static,
            )
        )

        self.assertFalse(
            behavioural_increment_passes(
                bad_guardrail,
                static,
            )
        )

    def test_metric_delta_uses_candidate_minus_reference(self):
        static = self._result(
            MODEL_STATIC_LOGISTIC,
            brier=0.24,
            log_loss=0.67,
            roc_auc=0.53,
            average_precision=0.40,
        )

        candidate = self._result(
            MODEL_BEHAVIOURAL_LOGISTIC,
            brier=0.21,
            log_loss=0.62,
            roc_auc=0.68,
            average_precision=0.52,
        )

        delta = metric_delta(
            candidate,
            static,
        )

        self.assertAlmostEqual(
            delta["brier_score"],
            -0.03,
        )
        self.assertAlmostEqual(
            delta["log_loss"],
            -0.05,
        )
        self.assertAlmostEqual(
            delta["roc_auc"],
            0.15,
        )
        self.assertAlmostEqual(
            delta["average_precision"],
            0.12,
        )


if __name__ == "__main__":
    unittest.main()