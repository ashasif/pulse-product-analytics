import tempfile
import unittest
from pathlib import Path

from src.analysis.experiment_decision_synthesis import (
    build_experiment_decisions,
    build_phase5_snapshot,
    export_phase5_portfolio,
    render_forest_svg,
)
from src.analysis.experiment_inference import (
    InferenceContractError,
)


def example_binary_snapshot():
    return {
        "context": {
            "ingestion_batch_id": 1,
            "analytics_build_run_id": 1,
            "observation_cutoff_at":
                "2026-07-01T00:59:36+01:00",
        },
        "metric_plan": [
            {
                "experiment_id": "exp_a",
                "experiment_name": "Experiment A",
                "metric_role": "primary",
                "metric_key": "primary_a",
                "support_status": "supported",
                "inference_status": "ready_binary",
            },
            {
                "experiment_id": "exp_a",
                "experiment_name": "Experiment A",
                "metric_role": "secondary",
                "metric_key": "secondary_a",
                "support_status": "deferred",
                "inference_status": "excluded_deferred",
            },
            {
                "experiment_id": "exp_b",
                "experiment_name": "Experiment B",
                "metric_role": "primary",
                "metric_key": "primary_b",
                "support_status": "deferred",
                "inference_status": "excluded_deferred",
            },
            {
                "experiment_id": "exp_b",
                "experiment_name": "Experiment B",
                "metric_role": "guardrail",
                "metric_key": "guardrail_b",
                "support_status": "supported",
                "inference_status": "ready_binary",
            },
        ],
        "binary_results": [
            {
                "experiment_id": "exp_a",
                "experiment_name": "Experiment A",
                "metric_role": "primary",
                "metric_key": "primary_a",
                "control_rate": 0.40,
                "treatment_rate": 0.41,
                "percentage_point_effect": 1.0,
                "confidence_interval_low": -0.02,
                "confidence_interval_high": 0.04,
                "p_value": 0.70,
                "statistically_detectable": False,
            },
            {
                "experiment_id": "exp_b",
                "experiment_name": "Experiment B",
                "metric_role": "guardrail",
                "metric_key": "guardrail_b",
                "control_rate": 0.50,
                "treatment_rate": 0.50,
                "percentage_point_effect": 0.0,
                "confidence_interval_low": -0.03,
                "confidence_interval_high": 0.03,
                "p_value": 1.0,
                "statistically_detectable": False,
            },
        ],
    }


def example_continuous_snapshot():
    return {
        "context": {
            "ingestion_batch_id": 1,
            "analytics_build_run_id": 1,
            "observation_cutoff_at":
                "2026-07-01T00:59:36+01:00",
        },
        "experiment_id": "exp_other",
        "experiment_name": "Other Experiment",
        "metric_role": "commercial",
        "metric_key": "commercial_other",
        "inference": {
            "absolute_effect": 0.2,
            "confidence_interval_low": -1.0,
            "confidence_interval_high": 1.4,
            "permutation_p_value": 0.7,
            "statistically_detectable": False,
        },
    }


def example_sensitivity_snapshot():
    return {
        "context": {
            "ingestion_batch_id": 1,
            "analytics_build_run_id": 1,
            "observation_cutoff_at":
                "2026-07-01T00:59:36+01:00",
        },
        "multiplicity_results": [],
        "binary_sensitivity": [
            {
                "experiment_id": "exp_a",
                "metric_key": "primary_a",
                "mde_pp": 3.0,
            },
            {
                "experiment_id": "exp_b",
                "metric_key": "guardrail_b",
                "mde_pp": 4.0,
            },
        ],
        "continuous_sensitivity": {
            "mde_gbp": 1.6,
        },
    }


class DecisionTests(unittest.TestCase):
    def test_missing_primary_metric_blocks_decision_readiness(self):
        decisions = build_experiment_decisions(
            example_binary_snapshot(),
            example_continuous_snapshot(),
            example_sensitivity_snapshot(),
        )

        by_id = {
            row["experiment_id"]: row
            for row in decisions
        }

        self.assertEqual(
            by_id["exp_b"]["decision_status"],
            "not_decision_ready_primary_metric_unavailable",
        )

    def test_non_detectable_primary_with_missing_support_is_inconclusive(self):
        decisions = build_experiment_decisions(
            example_binary_snapshot(),
            example_continuous_snapshot(),
            example_sensitivity_snapshot(),
        )

        by_id = {
            row["experiment_id"]: row
            for row in decisions
        }

        self.assertEqual(
            by_id["exp_a"]["decision_status"],
            "primary_not_detectable_supporting_metrics_incomplete",
        )

    def test_excluded_metric_reason_is_preserved(self):
        decisions = build_experiment_decisions(
            example_binary_snapshot(),
            example_continuous_snapshot(),
            example_sensitivity_snapshot(),
        )

        by_id = {
            row["experiment_id"]: row
            for row in decisions
        }

        excluded = by_id["exp_a"][
            "excluded_metrics"
        ]

        self.assertEqual(
            excluded[0]["reason"],
            "excluded_deferred",
        )


class PortfolioTests(unittest.TestCase):
    def test_forest_svg_is_valid_svg_document(self):
        decisions = build_experiment_decisions(
            example_binary_snapshot(),
            example_continuous_snapshot(),
            example_sensitivity_snapshot(),
        )

        snapshot = {
            "decisions": decisions,
        }

        svg = render_forest_svg(
            snapshot
        )

        self.assertTrue(
            svg.startswith("<svg")
        )

        self.assertIn(
            "<circle",
            svg,
        )

        self.assertIn(
            "95% confidence intervals",
            svg,
        )

    def test_export_creates_expected_portfolio_outputs(self):
        binary = example_binary_snapshot()
        continuous = example_continuous_snapshot()
        sensitivity = example_sensitivity_snapshot()

        decisions = build_experiment_decisions(
            binary,
            continuous,
            sensitivity,
        )

        snapshot = {
            "synthetic_data": True,
            "phase": 5,
            "step": 7,
            "status": "ready_for_formal_closure",
            "analysis_type": "test",
            "context": binary["context"],
            "experiment_count": 2,
            "completed_inference_result_count": 2,
            "statistically_detectable_result_count": 0,
            "decisions": decisions,
            "methodology_summary": {},
            "headline":
                "No completed result is statistically detectable.",
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            paths = export_phase5_portfolio(
                snapshot,
                output_dir=root / "portfolio",
                summary_doc=root / "phase5-summary.md",
            )

            for path in paths.values():
                self.assertTrue(
                    path.exists()
                )

            markdown = (
                paths["portfolio_summary"]
                .read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "synthetic",
                markdown.lower(),
            )

            self.assertIn(
                "does not prove exact equality",
                markdown,
            )

    def test_manifest_marks_ready_not_closed(self):
        binary = example_binary_snapshot()
        continuous = example_continuous_snapshot()
        sensitivity = example_sensitivity_snapshot()

        decisions = build_experiment_decisions(
            binary,
            continuous,
            sensitivity,
        )

        snapshot = {
            "synthetic_data": True,
            "phase": 5,
            "step": 7,
            "status": "ready_for_formal_closure",
            "analysis_type": "test",
            "context": binary["context"],
            "experiment_count": 2,
            "completed_inference_result_count": 2,
            "statistically_detectable_result_count": 0,
            "decisions": decisions,
            "methodology_summary": {},
            "headline": "Test headline.",
        }

        with tempfile.TemporaryDirectory() as directory:
            paths = export_phase5_portfolio(
                snapshot,
                output_dir=Path(directory) / "portfolio",
                summary_doc=Path(directory) / "summary.md",
            )

            manifest = (
                paths["manifest"]
                .read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "ready_for_formal_closure",
                manifest,
            )


class ProductionSnapshotTests(unittest.TestCase):
    def test_real_phase5_snapshot_has_three_experiments(self):
        snapshot = build_phase5_snapshot()

        self.assertEqual(
            snapshot["experiment_count"],
            3,
        )

    def test_real_phase5_snapshot_has_zero_detectable_results(self):
        snapshot = build_phase5_snapshot()

        self.assertEqual(
            snapshot[
                "statistically_detectable_result_count"
            ],
            0,
        )

    def test_real_phase5_snapshot_preserves_synthetic_disclosure(self):
        snapshot = build_phase5_snapshot()

        self.assertTrue(
            snapshot["synthetic_data"]
        )


if __name__ == "__main__":
    unittest.main()
