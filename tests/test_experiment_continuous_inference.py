import math
import unittest

from src.analysis.experiment_continuous_inference import (
    infer_mean_difference_resampling,
)
from src.analysis.experiment_inference import (
    InferenceContractError,
)


class MeanDifferenceInferenceTests(unittest.TestCase):
    def test_equal_groups_have_zero_effect(self):
        result = infer_mean_difference_resampling(
            metric_name="collection",
            control_values=[0, 0, 10, 10] * 20,
            treatment_values=[0, 0, 10, 10] * 20,
            bootstrap_replicates=500,
            permutation_replicates=500,
            seed=100,
        )

        self.assertAlmostEqual(
            result.absolute_effect,
            0.0,
        )

        self.assertEqual(
            result.permutation_p_value,
            1.0,
        )

        self.assertLessEqual(
            result.confidence_interval_low,
            0.0,
        )

        self.assertGreaterEqual(
            result.confidence_interval_high,
            0.0,
        )

    def test_effect_direction_is_treatment_minus_control(self):
        result = infer_mean_difference_resampling(
            metric_name="collection",
            control_values=[0, 0, 0, 10] * 30,
            treatment_values=[0, 0, 10, 10] * 30,
            bootstrap_replicates=500,
            permutation_replicates=500,
            seed=200,
        )

        self.assertGreater(
            result.absolute_effect,
            0.0,
        )

        self.assertGreater(
            result.relative_effect,
            0.0,
        )

    def test_resampling_is_deterministic_for_same_seed(self):
        kwargs = {
            "metric_name": "collection",
            "control_values":
                [0, 0, 12, 100] * 25,
            "treatment_values":
                [0, 12, 12, 100] * 25,
            "bootstrap_replicates": 500,
            "permutation_replicates": 500,
            "seed": 300,
        }

        first = infer_mean_difference_resampling(
            **kwargs
        )

        second = infer_mean_difference_resampling(
            **kwargs
        )

        self.assertEqual(
            first.confidence_interval_low,
            second.confidence_interval_low,
        )

        self.assertEqual(
            first.confidence_interval_high,
            second.confidence_interval_high,
        )

        self.assertEqual(
            first.permutation_p_value,
            second.permutation_p_value,
        )

    def test_zero_control_mean_has_no_relative_effect(self):
        result = infer_mean_difference_resampling(
            metric_name="collection",
            control_values=[0] * 50,
            treatment_values=[0, 0, 0, 10] * 13,
            bootstrap_replicates=300,
            permutation_replicates=300,
            seed=400,
        )

        self.assertIsNone(
            result.relative_effect
        )

    def test_empty_group_is_rejected(self):
        with self.assertRaises(
            InferenceContractError
        ):
            infer_mean_difference_resampling(
                metric_name="collection",
                control_values=[],
                treatment_values=[1, 2, 3],
                bootstrap_replicates=100,
                permutation_replicates=100,
            )

    def test_non_finite_value_is_rejected(self):
        with self.assertRaises(
            InferenceContractError
        ):
            infer_mean_difference_resampling(
                metric_name="collection",
                control_values=[
                    0,
                    math.inf,
                ],
                treatment_values=[1, 2],
                bootstrap_replicates=100,
                permutation_replicates=100,
            )


if __name__ == "__main__":
    unittest.main()
