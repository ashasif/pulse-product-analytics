import unittest

from src.analysis.experiment_inference import InferenceContractError
from src.analysis.experiment_integrity import (
    DEFAULT_SRM_ALPHA,
    build_sample_ratio_result,
    calculate_sample_ratio_mismatch,
)


class SampleRatioTests(unittest.TestCase):
    def test_balanced_50_50_allocation_passes(self):
        result = calculate_sample_ratio_mismatch(
            experiment_id="exp_test",
            control_count=5000,
            treatment_count=5000,
            control_allocation=0.50,
            treatment_allocation=0.50,
        )

        self.assertEqual(result.total_count, 10000)
        self.assertEqual(result.chi_square_statistic, 0.0)
        self.assertEqual(result.p_value, 1.0)
        self.assertFalse(result.mismatch_detected)
        self.assertEqual(result.alpha, DEFAULT_SRM_ALPHA)

    def test_correct_40_60_allocation_passes(self):
        result = calculate_sample_ratio_mismatch(
            experiment_id="exp_test",
            control_count=4000,
            treatment_count=6000,
            control_allocation=0.40,
            treatment_allocation=0.60,
        )

        self.assertAlmostEqual(result.expected_control_count, 4000.0)
        self.assertAlmostEqual(result.expected_treatment_count, 6000.0)
        self.assertFalse(result.mismatch_detected)

    def test_large_allocation_mismatch_is_detected(self):
        result = calculate_sample_ratio_mismatch(
            experiment_id="exp_test",
            control_count=6000,
            treatment_count=4000,
            control_allocation=0.50,
            treatment_allocation=0.50,
        )

        self.assertLess(result.p_value, DEFAULT_SRM_ALPHA)
        self.assertTrue(result.mismatch_detected)

    def test_allocations_must_sum_to_one(self):
        with self.assertRaises(InferenceContractError):
            calculate_sample_ratio_mismatch(
                experiment_id="exp_test",
                control_count=500,
                treatment_count=500,
                control_allocation=0.60,
                treatment_allocation=0.60,
            )

    def test_zero_total_is_rejected(self):
        with self.assertRaises(InferenceContractError):
            calculate_sample_ratio_mismatch(
                experiment_id="exp_test",
                control_count=0,
                treatment_count=0,
                control_allocation=0.50,
                treatment_allocation=0.50,
            )

    def test_negative_count_is_rejected(self):
        with self.assertRaises(InferenceContractError):
            calculate_sample_ratio_mismatch(
                experiment_id="exp_test",
                control_count=-1,
                treatment_count=10,
                control_allocation=0.50,
                treatment_allocation=0.50,
            )

    def test_invalid_srm_alpha_is_rejected(self):
        with self.assertRaises(InferenceContractError):
            calculate_sample_ratio_mismatch(
                experiment_id="exp_test",
                control_count=500,
                treatment_count=500,
                control_allocation=0.50,
                treatment_allocation=0.50,
                alpha=0.0,
            )


class SampleRatioVariantRowTests(unittest.TestCase):
    def test_builds_result_from_variant_rows(self):
        rows = [
            {
                "experiment_id": "exp_ai",
                "variant": "control",
                "allocation_probability": 0.40,
                "assigned_mature_count": 4000,
            },
            {
                "experiment_id": "exp_ai",
                "variant": "treatment",
                "allocation_probability": 0.60,
                "assigned_mature_count": 6000,
            },
        ]

        result = build_sample_ratio_result(rows)

        self.assertEqual(result.experiment_id, "exp_ai")
        self.assertEqual(result.total_count, 10000)
        self.assertFalse(result.mismatch_detected)

    def test_mixed_experiments_are_rejected(self):
        rows = [
            {
                "experiment_id": "exp_a",
                "variant": "control",
                "allocation_probability": 0.50,
                "assigned_mature_count": 500,
            },
            {
                "experiment_id": "exp_b",
                "variant": "treatment",
                "allocation_probability": 0.50,
                "assigned_mature_count": 500,
            },
        ]

        with self.assertRaises(InferenceContractError):
            build_sample_ratio_result(rows)

    def test_missing_count_field_is_rejected(self):
        rows = [
            {
                "experiment_id": "exp_a",
                "variant": "control",
                "allocation_probability": 0.50,
                "assigned_mature_count": 500,
            },
            {
                "experiment_id": "exp_a",
                "variant": "treatment",
                "allocation_probability": 0.50,
            },
        ]

        with self.assertRaises(InferenceContractError):
            build_sample_ratio_result(rows)


if __name__ == "__main__":
    unittest.main()
