from __future__ import annotations

import inspect
import unittest

from src.app.evidence import load_portfolio_evidence
from src.app.pages import experiments, predictive


class FrozenEvidencePageTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.evidence = load_portfolio_evidence()

    def test_phase5_presentation_contains_six_completed_results(self):
        frame = experiments.build_experiment_evidence_frame(
            self.evidence["phase5"]
        )

        self.assertEqual(
            len(frame),
            6,
        )

        self.assertEqual(
            int(frame["detectable"].sum()),
            0,
        )

    def test_phase5_decision_statuses_are_preserved(self):
        statuses = {
            item["decision_status"]
            for item in self.evidence[
                "phase5"
            ]["decisions"]
        }

        self.assertEqual(
            statuses,
            {
                "not_decision_ready_primary_metric_unavailable",
                "primary_not_detectable_supporting_metrics_incomplete",
                "no_detectable_effect_in_completed_metric_family",
            },
        )

    def test_phase6_model_comparison_preserves_locked_result(self):
        manifest = self.evidence[
            "phase6"
        ]["manifest"]

        frame = predictive.build_model_comparison_frame(
            manifest
        )

        self.assertEqual(
            list(frame["model"]),
            [
                "Prevalence baseline",
                "Static logistic",
                "Behavioural logistic",
            ],
        )

        behavioural = frame.iloc[2]

        self.assertAlmostEqual(
            behavioural["Brier"],
            0.232913,
        )

        self.assertAlmostEqual(
            behavioural["Log loss"],
            0.658714,
        )

        self.assertAlmostEqual(
            behavioural["ROC-AUC"],
            0.548994,
        )

        self.assertAlmostEqual(
            behavioural["Average precision"],
            0.424815,
        )

    def test_phase6_targeting_evidence_is_frozen(self):
        manifest = self.evidence[
            "phase6"
        ]["manifest"]

        frame = predictive.build_targeting_frame(
            manifest
        )

        self.assertEqual(
            list(frame["capacity"]),
            ["10%", "20%"],
        )

        self.assertAlmostEqual(
            frame.iloc[0]["lift_vs_population"],
            1.0954,
        )

        self.assertAlmostEqual(
            frame.iloc[1]["lift_vs_population"],
            1.0942,
        )

    def test_frozen_pages_do_not_query_reporting_database(self):
        for module in (
            experiments,
            predictive,
        ):
            source = inspect.getsource(module)

            with self.subTest(
                module=module.__name__
            ):
                self.assertNotIn(
                    "load_named_query",
                    source,
                )

                self.assertNotIn(
                    "fetch_reporting_rows",
                    source,
                )

    def test_frozen_pages_do_not_import_model_training_library(self):
        source = (
            inspect.getsource(experiments)
            + inspect.getsource(predictive)
        ).lower()

        self.assertNotIn(
            "sklearn",
            source,
        )

        self.assertNotIn(
            "scikit-learn",
            source,
        )


if __name__ == "__main__":
    unittest.main()