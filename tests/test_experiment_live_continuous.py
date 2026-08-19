import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.analysis.experiment_live_continuous import (
    _fetch_assigned_mature_revenue,
    analyse_revenue_rows,
    export_live_continuous_inference,
)


class LiveContinuousRowTests(unittest.TestCase):
    def setUp(self):
        self.rows = []

        for variant, allocation, values in (
            (
                "control",
                0.5,
                [0, 0, 0, 11.99] * 25,
            ),
            (
                "treatment",
                0.5,
                [0, 0, 11.99, 11.99] * 25,
            ),
        ):
            for value in values:
                self.rows.append(
                    {
                        "ingestion_batch_id": 1,
                        "analytics_build_run_id": 1,
                        "observation_cutoff_at":
                            "2026-07-01",
                        "experiment_id":
                            "exp_paywall_redesign_2024q3",
                        "variant":
                            variant,
                        "allocation_probability":
                            allocation,
                        "outcome_value":
                            value,
                    }
                )

    def test_live_rows_produce_positive_mean_difference(self):
        result, srm, distribution = (
            analyse_revenue_rows(
                self.rows,
                bootstrap_replicates=500,
                permutation_replicates=500,
                seed=700,
            )
        )

        self.assertGreater(
            result.absolute_effect,
            0.0,
        )

        self.assertFalse(
            srm.mismatch_detected
        )

        self.assertEqual(
            distribution["control"]["count"],
            100,
        )

        self.assertEqual(
            distribution["treatment"]["count"],
            100,
        )

    def test_distribution_preserves_zero_values(self):
        _, _, distribution = (
            analyse_revenue_rows(
                self.rows,
                bootstrap_replicates=300,
                permutation_replicates=300,
                seed=800,
            )
        )

        self.assertGreater(
            distribution["control"]["zero_rate"],
            0.0,
        )

        self.assertIn(
            0.0,
            distribution["control"]["unique_values"],
        )


class QueryContractTests(unittest.TestCase):
    @patch(
        "src.analysis.experiment_live_continuous."
        "fetch_reporting_rows"
    )
    def test_query_uses_reporting_and_maturity_filter(
        self,
        fetch_rows,
    ):
        fetch_rows.return_value = []

        _fetch_assigned_mature_revenue(1)

        sql = (
            fetch_rows.call_args.args[0]
            .lower()
        )

        self.assertIn(
            "reporting.vw_experiment_assignment_outcomes",
            sql,
        )

        self.assertIn(
            "analysis_window_mature is true",
            sql,
        )

        self.assertNotIn(
            " raw.",
            sql,
        )

        self.assertNotIn(
            " staging.",
            sql,
        )

        self.assertNotIn(
            " analytics.",
            sql,
        )

        self.assertNotIn(
            " validation.",
            sql,
        )


class OutputTests(unittest.TestCase):
    def test_export_creates_expected_files(self):
        snapshot = {
            "synthetic_data": True,
            "phase": 5,
            "step": 5,
            "analysis_type":
                "randomized_experiment_continuous_inference",
            "context": {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "observation_cutoff_at":
                    "2026-07-01T00:59:36+01:00",
            },
            "experiment_id":
                "exp_paywall_redesign_2024q3",
            "experiment_name":
                "Paywall Redesign Experiment",
            "metric_role":
                "commercial",
            "metric_key":
                "revenue_per_assigned_user_30d",
            "metric_name":
                "Successful Revenue per Assigned User Within 30 Days",
            "metric_unit":
                "GBP",
            "business_interpretation":
                "successful billed payment collection per assigned user",
            "population":
                "assigned_mature",
            "outcome_primitive":
                "successful_revenue_gbp_30d",
            "distribution": {
                "control": {
                    "count": 100,
                    "zero_count": 90,
                    "zero_rate": 0.9,
                    "positive_count": 10,
                    "positive_rate": 0.1,
                    "unique_values":
                        [0.0, 11.99],
                    "minimum": 0.0,
                    "maximum": 11.99,
                },
                "treatment": {
                    "count": 100,
                    "zero_count": 89,
                    "zero_rate": 0.89,
                    "positive_count": 11,
                    "positive_rate": 0.11,
                    "unique_values":
                        [0.0, 11.99],
                    "minimum": 0.0,
                    "maximum": 11.99,
                },
            },
            "srm": {
                "status": "pass",
                "p_value": 1.0,
            },
            "inference": {
                "control_count": 100,
                "treatment_count": 100,
                "control_mean": 1.0,
                "treatment_mean": 1.1,
                "absolute_effect": 0.1,
                "relative_effect": 0.1,
                "confidence_level": 0.95,
                "confidence_interval_low": -0.2,
                "confidence_interval_high": 0.4,
                "bootstrap_replicates": 1000,
                "bootstrap_seed": 1,
                "permutation_replicates": 1000,
                "permutation_seed": 2,
                "permutation_p_value": 0.5,
                "alpha": 0.05,
                "statistically_detectable": False,
            },
            "reconciliation": {
                "population_matches_variant_summary":
                    True,
                "mean_reconciliation_applicable":
                    True,
                "mean_reconciliation_passed":
                    True,
            },
            "methodology": {
                "estimand":
                    "treatment_minus_control_mean",
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            paths = (
                export_live_continuous_inference(
                    snapshot,
                    output_dir=Path(directory),
                )
            )

            self.assertTrue(
                paths["json"].exists()
            )

            self.assertTrue(
                paths["markdown"].exists()
            )

            self.assertTrue(
                paths["manifest"].exists()
            )

            markdown = (
                paths["markdown"]
                .read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "successful billed payment collection",
                markdown,
            )

            self.assertIn(
                "synthetic",
                markdown.lower(),
            )


if __name__ == "__main__":
    unittest.main()
