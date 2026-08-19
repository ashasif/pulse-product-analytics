import tempfile
import unittest
from pathlib import Path

from src.analysis.experiment_inference import (
    InferenceContractError,
)
from src.analysis.experiment_multiplicity_sensitivity import (
    build_multiplicity_results,
    export_step6,
    validate_matching_contexts,
)


class ContextTests(unittest.TestCase):
    def test_matching_contexts_are_accepted(self):
        context = {
            "ingestion_batch_id": 1,
            "analytics_build_run_id": 1,
            "observation_cutoff_at":
                "2026-07-01T00:59:36+01:00",
        }

        result = validate_matching_contexts(
            context,
            dict(context),
        )

        self.assertEqual(
            result,
            context,
        )

    def test_mismatched_build_is_rejected(self):
        first = {
            "ingestion_batch_id": 1,
            "analytics_build_run_id": 1,
            "observation_cutoff_at":
                "2026-07-01T00:59:36+01:00",
        }

        second = {
            **first,
            "analytics_build_run_id": 2,
        }

        with self.assertRaises(
            InferenceContractError
        ):
            validate_matching_contexts(
                first,
                second,
            )


class MultiplicityTests(unittest.TestCase):
    def test_holm_uses_completed_supportive_family_only(self):
        binary = {
            "binary_results": [
                {
                    "experiment_id": "exp_a",
                    "metric_role": "primary",
                    "metric_key": "primary",
                    "p_value": 0.01,
                },
                {
                    "experiment_id": "exp_a",
                    "metric_role": "secondary",
                    "metric_key": "secondary",
                    "p_value": 0.02,
                },
                {
                    "experiment_id": "exp_a",
                    "metric_role": "guardrail",
                    "metric_key": "guardrail",
                    "p_value": 0.20,
                },
            ]
        }

        continuous = {
            "experiment_id": "exp_a",
            "metric_role": "commercial",
            "metric_key": "commercial",
            "inference": {
                "permutation_p_value":
                    0.03,
            },
        }

        results = (
            build_multiplicity_results(
                binary,
                continuous,
            )
        )

        by_metric = {
            row["metric_key"]: row
            for row in results
        }

        self.assertNotIn(
            "primary",
            by_metric,
        )

        self.assertEqual(
            by_metric["secondary"][
                "family_size"
            ],
            3,
        )

        self.assertAlmostEqual(
            by_metric["secondary"][
                "holm_adjusted_p_value"
            ],
            0.06,
        )

        self.assertAlmostEqual(
            by_metric["commercial"][
                "holm_adjusted_p_value"
            ],
            0.06,
        )

        self.assertAlmostEqual(
            by_metric["guardrail"][
                "holm_adjusted_p_value"
            ],
            0.20,
        )


class OutputTests(unittest.TestCase):
    def test_export_creates_expected_files(self):
        snapshot = {
            "synthetic_data": True,
            "phase": 5,
            "step": 6,
            "analysis_type":
                "experiment_multiplicity_and_design_sensitivity",
            "context": {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "observation_cutoff_at":
                    "2026-07-01T00:59:36+01:00",
            },
            "methodology": {},
            "multiplicity_results": [],
            "binary_sensitivity": [],
            "continuous_sensitivity": {
                "experiment_id": "exp_test",
                "metric_key": "collection",
                "observed_effect_gbp": 0.1,
                "mde_gbp": 1.5,
                "effect_to_mde_ratio": 0.07,
                "control_stddev": 15.0,
                "treatment_stddev": 16.0,
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            paths = export_step6(
                snapshot,
                output_dir=Path(directory),
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


if __name__ == "__main__":
    unittest.main()
