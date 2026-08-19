import unittest

from src.analysis.experiment_inference import (
    InferenceContractError,
    holm_adjust_p_values,
    infer_binary_outcome,
)


class BinaryInferenceTests(unittest.TestCase):
    def test_equal_rates_produce_zero_effect_and_p_one(self):
        result = infer_binary_outcome(
            metric_name="conversion",
            control_successes=500,
            control_total=1000,
            treatment_successes=500,
            treatment_total=1000,
        )

        self.assertAlmostEqual(result.control_rate, 0.5)
        self.assertAlmostEqual(result.treatment_rate, 0.5)
        self.assertAlmostEqual(result.absolute_effect, 0.0)
        self.assertAlmostEqual(result.percentage_point_effect, 0.0)
        self.assertAlmostEqual(result.relative_effect, 0.0)
        self.assertAlmostEqual(result.z_statistic, 0.0)
        self.assertAlmostEqual(result.p_value, 1.0)
        self.assertFalse(result.statistically_detectable)

        self.assertLess(result.confidence_interval_low, 0.0)
        self.assertGreater(result.confidence_interval_high, 0.0)

    def test_treatment_effect_direction_is_treatment_minus_control(self):
        result = infer_binary_outcome(
            metric_name="conversion",
            control_successes=300,
            control_total=1000,
            treatment_successes=400,
            treatment_total=1000,
        )

        self.assertAlmostEqual(result.control_rate, 0.30)
        self.assertAlmostEqual(result.treatment_rate, 0.40)
        self.assertAlmostEqual(result.absolute_effect, 0.10)
        self.assertAlmostEqual(result.percentage_point_effect, 10.0)
        self.assertAlmostEqual(
            result.relative_effect,
            0.40 / 0.30 - 1.0,
        )

        self.assertGreater(result.z_statistic, 0.0)
        self.assertLess(result.p_value, 0.05)
        self.assertTrue(result.statistically_detectable)

    def test_negative_effect_is_preserved(self):
        result = infer_binary_outcome(
            metric_name="guardrail",
            control_successes=400,
            control_total=1000,
            treatment_successes=300,
            treatment_total=1000,
        )

        self.assertLess(result.absolute_effect, 0.0)
        self.assertLess(result.percentage_point_effect, 0.0)
        self.assertLess(result.z_statistic, 0.0)

    def test_zero_control_rate_has_no_relative_effect(self):
        result = infer_binary_outcome(
            metric_name="rare_conversion",
            control_successes=0,
            control_total=1000,
            treatment_successes=5,
            treatment_total=1000,
        )

        self.assertIsNone(result.relative_effect)
        self.assertGreater(result.absolute_effect, 0.0)

    def test_all_zero_outcomes_are_handled(self):
        result = infer_binary_outcome(
            metric_name="zero_metric",
            control_successes=0,
            control_total=100,
            treatment_successes=0,
            treatment_total=100,
        )

        self.assertEqual(result.p_value, 1.0)
        self.assertEqual(result.z_statistic, 0.0)
        self.assertFalse(result.statistically_detectable)

    def test_all_one_outcomes_are_handled(self):
        result = infer_binary_outcome(
            metric_name="all_one_metric",
            control_successes=100,
            control_total=100,
            treatment_successes=100,
            treatment_total=100,
        )

        self.assertEqual(result.p_value, 1.0)
        self.assertEqual(result.z_statistic, 0.0)
        self.assertFalse(result.statistically_detectable)

    def test_successes_cannot_exceed_total(self):
        with self.assertRaises(InferenceContractError):
            infer_binary_outcome(
                metric_name="conversion",
                control_successes=101,
                control_total=100,
                treatment_successes=50,
                treatment_total=100,
            )

    def test_zero_denominator_is_rejected(self):
        with self.assertRaises(InferenceContractError):
            infer_binary_outcome(
                metric_name="conversion",
                control_successes=0,
                control_total=0,
                treatment_successes=50,
                treatment_total=100,
            )

    def test_blank_metric_name_is_rejected(self):
        with self.assertRaises(InferenceContractError):
            infer_binary_outcome(
                metric_name=" ",
                control_successes=10,
                control_total=100,
                treatment_successes=10,
                treatment_total=100,
            )

    def test_invalid_alpha_is_rejected(self):
        with self.assertRaises(InferenceContractError):
            infer_binary_outcome(
                metric_name="conversion",
                control_successes=10,
                control_total=100,
                treatment_successes=10,
                treatment_total=100,
                alpha=1.0,
            )


class HolmAdjustmentTests(unittest.TestCase):
    def test_single_p_value_is_unchanged(self):
        result = holm_adjust_p_values(
            {"secondary_metric": 0.02}
        )

        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(
            result[0].adjusted_p_value,
            0.02,
        )

    def test_holm_adjustment_uses_step_down_family(self):
        result = holm_adjust_p_values(
            {
                "secondary": 0.01,
                "commercial": 0.03,
                "guardrail": 0.20,
            }
        )

        by_name = {
            row.metric_name: row
            for row in result
        }

        self.assertAlmostEqual(
            by_name["secondary"].adjusted_p_value,
            0.03,
        )

        self.assertAlmostEqual(
            by_name["commercial"].adjusted_p_value,
            0.06,
        )

        self.assertAlmostEqual(
            by_name["guardrail"].adjusted_p_value,
            0.20,
        )

        self.assertTrue(
            by_name["secondary"]
            .statistically_detectable_after_adjustment
        )

        self.assertFalse(
            by_name["commercial"]
            .statistically_detectable_after_adjustment
        )

    def test_holm_adjustment_is_monotone_in_sorted_order(self):
        result = holm_adjust_p_values(
            {
                "a": 0.001,
                "b": 0.02,
                "c": 0.021,
                "d": 0.90,
            }
        )

        adjusted_sorted = sorted(
            (
                row.raw_p_value,
                row.adjusted_p_value,
            )
            for row in result
        )

        adjusted_values = [
            adjusted
            for _, adjusted in adjusted_sorted
        ]

        self.assertEqual(
            adjusted_values,
            sorted(adjusted_values),
        )

    def test_invalid_p_value_is_rejected(self):
        with self.assertRaises(InferenceContractError):
            holm_adjust_p_values(
                {"secondary": 1.1}
            )

    def test_empty_family_is_rejected(self):
        with self.assertRaises(InferenceContractError):
            holm_adjust_p_values({})


if __name__ == "__main__":
    unittest.main()
