import unittest

from src.analysis.experiment_inference import (
    InferenceContractError,
)
from src.analysis.experiment_sensitivity import (
    binary_mde,
    mean_mde,
)


class BinaryMdeTests(unittest.TestCase):
    def test_binary_mde_is_positive(self):
        result = binary_mde(
            metric_key="conversion",
            control_rate=0.20,
            control_count=1000,
            treatment_count=1000,
        )

        self.assertGreater(
            result.mde_absolute,
            0.0,
        )

        self.assertGreater(
            result.mde_percentage_points,
            0.0,
        )

        self.assertEqual(
            result.status,
            "estimated",
        )

    def test_saturated_binary_baseline_is_not_estimable(self):
        result = binary_mde(
            metric_key="feature_use",
            control_rate=1.0,
            control_count=1000,
            treatment_count=1000,
        )

        self.assertIsNone(
            result.mde_absolute
        )

        self.assertEqual(
            result.status,
            "not_estimable_saturated_baseline",
        )

    def test_invalid_binary_count_is_rejected(self):
        with self.assertRaises(
            InferenceContractError
        ):
            binary_mde(
                metric_key="conversion",
                control_rate=0.20,
                control_count=1,
                treatment_count=100,
            )


class MeanMdeTests(unittest.TestCase):
    def test_mean_mde_is_positive(self):
        result = mean_mde(
            metric_key="collection",
            control_stddev=15.0,
            treatment_stddev=16.0,
            control_count=1300,
            treatment_count=1350,
        )

        self.assertGreater(
            result.mde_absolute,
            0.0,
        )

    def test_invalid_target_power_is_rejected(self):
        with self.assertRaises(
            InferenceContractError
        ):
            mean_mde(
                metric_key="collection",
                control_stddev=15.0,
                treatment_stddev=16.0,
                control_count=1300,
                treatment_count=1350,
                target_power=1.0,
            )


if __name__ == "__main__":
    unittest.main()
