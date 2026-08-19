import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.analysis.experiment_inference import InferenceContractError
from src.analysis.experiment_live_inference import (
    BINARY_METRIC_FIELDS,
    _fetch_binary_metric_counts,
    analyse_binary_metric_rows,
    build_live_binary_inference,
    build_metric_plan,
    export_live_binary_inference,
)


class MetricPlanTests(unittest.TestCase):
    def setUp(self):
        self.experiments = [
            {
                "experiment_id": "exp_test",
                "experiment_name": "Test Experiment",
                "primary_metric": "primary_supported",
                "secondary_metric": "secondary_deferred",
                "commercial_metric": "commercial_continuous",
                "guardrail_metric": "guardrail_unknown",
            }
        ]

        self.contracts = [
            {
                "metric_key": "primary_supported",
                "metric_name": "Primary",
                "metric_unit": "rate",
                "support_status": "supported",
            },
            {
                "metric_key": "secondary_deferred",
                "metric_name": "Secondary",
                "metric_unit": "rate",
                "support_status": "deferred",
            },
            {
                "metric_key": "commercial_continuous",
                "metric_name": "Commercial",
                "metric_unit": "GBP",
                "support_status": "supported",
            },
        ]

    def test_plan_distinguishes_contract_states(self):
        with patch.dict(
            BINARY_METRIC_FIELDS,
            {
                "primary_supported": "feature_used_7d",
            },
            clear=False,
        ):
            with patch(
                "src.analysis.experiment_live_inference."
                "CONTINUOUS_METRIC_KEYS",
                frozenset({"commercial_continuous"}),
            ):
                plan = build_metric_plan(
                    self.experiments,
                    self.contracts,
                )

        by_role = {
            row["metric_role"]: row
            for row in plan
        }

        self.assertEqual(
            by_role["primary"]["inference_status"],
            "ready_binary",
        )

        self.assertEqual(
            by_role["secondary"]["inference_status"],
            "excluded_deferred",
        )

        self.assertEqual(
            by_role["commercial"]["inference_status"],
            "pending_continuous_inference",
        )

        self.assertEqual(
            by_role["guardrail"]["inference_status"],
            "excluded_unknown_metric_contract",
        )

    def test_real_binary_bindings_are_canonical_reporting_primitives(self):
        self.assertEqual(
            BINARY_METRIC_FIELDS,
            {
                "onboarding_completion_48h":
                    "onboarding_completed_48h",
                "overall_feature_use_7d":
                    "feature_used_7d",
                "trial_start_conversion_7d":
                    "trial_started_7d",
                "paid_conversion_14d":
                    "paid_started_14d",
                "cancellation_or_expiry_30d":
                    "cancellation_or_expiry_30d",
            },
        )


class BinaryMetricRowTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "observation_cutoff_at": "2026-07-01",
                "experiment_id": "exp_test",
                "variant": "control",
                "allocation_probability": 0.50,
                "assigned_mature_count": 500,
                "success_count": 100,
            },
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "observation_cutoff_at": "2026-07-01",
                "experiment_id": "exp_test",
                "variant": "treatment",
                "allocation_probability": 0.50,
                "assigned_mature_count": 500,
                "success_count": 125,
            },
        ]

    def test_binary_rows_produce_treatment_minus_control_result(self):
        result, srm = analyse_binary_metric_rows(
            metric_key="trial_start_conversion_7d",
            rows=self.rows,
        )

        self.assertAlmostEqual(
            result.control_rate,
            0.20,
        )

        self.assertAlmostEqual(
            result.treatment_rate,
            0.25,
        )

        self.assertAlmostEqual(
            result.percentage_point_effect,
            5.0,
        )

        self.assertFalse(srm.mismatch_detected)

    def test_srm_failure_blocks_outcome_inference(self):
        rows = [
            {
                **self.rows[0],
                "assigned_mature_count": 900,
            },
            {
                **self.rows[1],
                "assigned_mature_count": 100,
            },
        ]

        with self.assertRaises(InferenceContractError):
            analyse_binary_metric_rows(
                metric_key="trial_start_conversion_7d",
                rows=rows,
            )


class QueryContractTests(unittest.TestCase):
    @patch(
        "src.analysis.experiment_live_inference."
        "fetch_reporting_rows"
    )
    def test_binary_query_uses_reporting_and_maturity_filter(
        self,
        fetch_rows,
    ):
        fetch_rows.return_value = []

        _fetch_binary_metric_counts(
            experiment_id="exp_test",
            metric_key="trial_start_conversion_7d",
            analytics_build_run_id=1,
        )

        sql = fetch_rows.call_args.args[0].lower()

        self.assertIn(
            "reporting.vw_experiment_assignment_outcomes",
            sql,
        )

        self.assertIn(
            "analysis_window_mature is true",
            sql,
        )

        self.assertNotIn(" raw.", sql)
        self.assertNotIn(" staging.", sql)
        self.assertNotIn(" validation.", sql)
        self.assertNotIn(" analytics.", sql)

    def test_unknown_binary_binding_is_rejected(self):
        with self.assertRaises(InferenceContractError):
            _fetch_binary_metric_counts(
                experiment_id="exp_test",
                metric_key="not_a_binary_metric",
                analytics_build_run_id=1,
            )


class LiveSnapshotTests(unittest.TestCase):
    @patch(
        "src.analysis.experiment_live_inference."
        "_fetch_binary_metric_counts"
    )
    @patch(
        "src.analysis.experiment_live_inference."
        "require_supported_metrics"
    )
    @patch(
        "src.analysis.experiment_live_inference."
        "get_metric_contracts"
    )
    @patch(
        "src.analysis.experiment_live_inference."
        "_fetch_experiment_definitions"
    )
    @patch(
        "src.analysis.experiment_live_inference."
        "get_reporting_context"
    )
    def test_snapshot_excludes_deferred_and_unknown_metrics(
        self,
        get_context,
        get_experiments,
        get_contracts,
        require_supported,
        get_counts,
    ):
        get_context.return_value = SimpleNamespace(
            ingestion_batch_id=1,
            analytics_build_run_id=1,
            observation_cutoff_at="2026-07-01T00:59:36+01:00",
        )

        get_experiments.return_value = [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "experiment_id": "exp_test",
                "experiment_name": "Test Experiment",
                "primary_metric": "trial_start_conversion_7d",
                "secondary_metric": "activation_48h",
                "commercial_metric":
                    "revenue_per_assigned_user_30d",
                "guardrail_metric":
                    "trial_start_conversion_14d",
                "analysis_window_days": 30,
            }
        ]

        get_contracts.return_value = [
            {
                "metric_key": "trial_start_conversion_7d",
                "metric_name":
                    "Trial Start Conversion Within 7 Days",
                "metric_unit": "rate",
                "support_status": "supported",
            },
            {
                "metric_key": "activation_48h",
                "metric_name": "Activation Within 48 Hours",
                "metric_unit": "rate",
                "support_status": "deferred",
            },
            {
                "metric_key":
                    "revenue_per_assigned_user_30d",
                "metric_name":
                    "Successful Revenue per Assigned User",
                "metric_unit": "GBP",
                "support_status": "supported",
            },
        ]

        get_counts.return_value = [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "observation_cutoff_at":
                    "2026-07-01T00:59:36+01:00",
                "experiment_id": "exp_test",
                "variant": "control",
                "allocation_probability": 0.50,
                "assigned_mature_count": 500,
                "success_count": 100,
            },
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "observation_cutoff_at":
                    "2026-07-01T00:59:36+01:00",
                "experiment_id": "exp_test",
                "variant": "treatment",
                "allocation_probability": 0.50,
                "assigned_mature_count": 500,
                "success_count": 100,
            },
        ]

        snapshot = build_live_binary_inference()

        self.assertEqual(
            len(snapshot["binary_results"]),
            1,
        )

        plan_by_role = {
            row["metric_role"]: row
            for row in snapshot["metric_plan"]
        }

        self.assertEqual(
            plan_by_role["primary"]["inference_status"],
            "ready_binary",
        )

        self.assertEqual(
            plan_by_role["secondary"]["inference_status"],
            "excluded_deferred",
        )

        self.assertEqual(
            plan_by_role["commercial"]["inference_status"],
            "pending_continuous_inference",
        )

        self.assertEqual(
            plan_by_role["guardrail"]["inference_status"],
            "excluded_unknown_metric_contract",
        )

        gated_metrics = require_supported.call_args.args[0]

        self.assertIn(
            "trial_start_conversion_7d",
            gated_metrics,
        )

        self.assertIn(
            "revenue_per_assigned_user_30d",
            gated_metrics,
        )

        self.assertNotIn(
            "activation_48h",
            gated_metrics,
        )

        self.assertNotIn(
            "trial_start_conversion_14d",
            gated_metrics,
        )


class OutputTests(unittest.TestCase):
    def test_export_creates_json_markdown_and_manifest(self):
        snapshot = {
            "synthetic_data": True,
            "phase": 5,
            "step": 4,
            "analysis_type":
                "randomized_experiment_binary_inference",
            "context": {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "observation_cutoff_at":
                    "2026-07-01T00:59:36+01:00",
            },
            "metric_plan": [],
            "binary_results": [],
            "methodology": {
                "primary_population": "assigned_mature",
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            paths = export_live_binary_inference(
                snapshot,
                output_dir=Path(directory),
            )

            self.assertTrue(paths["json"].exists())
            self.assertTrue(paths["markdown"].exists())
            self.assertTrue(paths["manifest"].exists())

            markdown = paths["markdown"].read_text(
                encoding="utf-8"
            )

            self.assertIn(
                "synthetic",
                markdown.lower(),
            )

            self.assertIn(
                "assigned_mature",
                markdown,
            )


if __name__ == "__main__":
    unittest.main()
