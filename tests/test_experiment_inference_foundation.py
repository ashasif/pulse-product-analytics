import unittest

from src.analysis.experiment_inference import (
    InferenceContractError,
    InferencePolicy,
    MetricInferenceSpec,
    PRIMARY_POPULATION,
    require_all_mature,
    validate_common_lineage,
    validate_variant_summary_rows,
)


class InferencePolicyTests(unittest.TestCase):
    def test_default_policy_is_assignment_based_and_maturity_controlled(self):
        policy = InferencePolicy()

        self.assertEqual(policy.primary_population, PRIMARY_POPULATION)
        self.assertTrue(policy.require_mature_window)
        self.assertFalse(policy.allow_exposure_conditioned_primary)
        self.assertEqual(policy.alpha, 0.05)
        self.assertEqual(policy.confidence_level, 0.95)
        self.assertEqual(policy.multiplicity_method, "holm")

    def test_policy_rejects_invalid_alpha(self):
        with self.assertRaises(InferenceContractError):
            InferencePolicy(alpha=0.0)

        with self.assertRaises(InferenceContractError):
            InferencePolicy(alpha=1.0)

    def test_policy_rejects_non_numeric_alpha(self):
        with self.assertRaises(InferenceContractError):
            InferencePolicy(alpha="0.05")  # type: ignore[arg-type]

    def test_policy_rejects_exposure_conditioned_primary_analysis(self):
        with self.assertRaises(InferenceContractError):
            InferencePolicy(allow_exposure_conditioned_primary=True)

    def test_policy_rejects_immature_primary_analysis(self):
        with self.assertRaises(InferenceContractError):
            InferencePolicy(require_mature_window=False)


class MetricInferenceSpecTests(unittest.TestCase):
    def test_valid_binary_primary_metric(self):
        spec = MetricInferenceSpec(
            metric_name="example_conversion",
            metric_kind="binary",
            metric_role="primary",
        )

        self.assertEqual(spec.metric_kind, "binary")
        self.assertEqual(spec.metric_role, "primary")

    def test_metric_spec_rejects_blank_name(self):
        with self.assertRaises(InferenceContractError):
            MetricInferenceSpec(
                metric_name=" ",
                metric_kind="binary",
                metric_role="primary",
            )

    def test_metric_spec_rejects_unknown_kind(self):
        with self.assertRaises(InferenceContractError):
            MetricInferenceSpec(
                metric_name="example_metric",
                metric_kind="ratio",
                metric_role="primary",
            )

    def test_metric_spec_rejects_unknown_role(self):
        with self.assertRaises(InferenceContractError):
            MetricInferenceSpec(
                metric_name="example_metric",
                metric_kind="binary",
                metric_role="exploratory",
            )


class InferencePopulationControlTests(unittest.TestCase):
    def setUp(self):
        self.lineage = {
            "ingestion_batch_id": 1,
            "analytics_build_run_id": 1,
            "observation_cutoff_at": "2026-07-01T00:59:36+01:00",
        }

    def test_common_lineage_accepts_matching_rows(self):
        rows = [
            {**self.lineage, "variant": "control"},
            {**self.lineage, "variant": "treatment"},
        ]

        validate_common_lineage(rows)

    def test_common_lineage_rejects_mismatch(self):
        rows = [
            {**self.lineage, "variant": "control"},
            {
                **self.lineage,
                "analytics_build_run_id": 2,
                "variant": "treatment",
            },
        ]

        with self.assertRaises(InferenceContractError):
            validate_common_lineage(rows)

    def test_common_lineage_rejects_missing_field(self):
        rows = [
            {**self.lineage, "variant": "control"},
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "variant": "treatment",
            },
        ]

        with self.assertRaises(InferenceContractError):
            validate_common_lineage(rows)

    def test_variant_summary_requires_control_and_treatment(self):
        rows = [
            {"variant": "control"},
            {"variant": "treatment"},
        ]

        validate_variant_summary_rows(rows)

    def test_variant_summary_rejects_duplicate_variant(self):
        rows = [
            {"variant": "control"},
            {"variant": "control"},
        ]

        with self.assertRaises(InferenceContractError):
            validate_variant_summary_rows(rows)

    def test_all_mature_accepts_mature_rows(self):
        rows = [
            {"analysis_window_mature": True},
            {"analysis_window_mature": True},
        ]

        require_all_mature(rows)

    def test_all_mature_rejects_immature_row(self):
        rows = [
            {"analysis_window_mature": True},
            {"analysis_window_mature": False},
        ]

        with self.assertRaises(InferenceContractError):
            require_all_mature(rows)


if __name__ == "__main__":
    unittest.main()
