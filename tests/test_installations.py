"""Tests for the Pulse synthetic installation generator."""

from collections import Counter
import unittest

from src.generation.installations import (
    generate_installations,
    get_simulation_bounds,
    load_installation_dimensions,
)


class InstallationGeneratorTests(unittest.TestCase):
    """Validate installation generation behaviour."""

    @classmethod
    def setUpClass(cls):
        cls.start_at, cls.end_at = get_simulation_bounds()

        cls.small_sample = generate_installations(
            count=10,
            start_at=cls.start_at,
            end_at=cls.end_at,
        )

        cls.distribution_sample = generate_installations(
            count=10_000,
            start_at=cls.start_at,
            end_at=cls.end_at,
        )

        cls.dimensions = load_installation_dimensions()

    def test_row_count(self):
        self.assertEqual(
            len(self.small_sample),
            10,
        )

    def test_installation_ids_are_unique(self):
        ids = {
            row["installation_id"]
            for row in self.small_sample
        }

        self.assertEqual(
            len(ids),
            len(self.small_sample),
        )

    def test_anonymous_ids_are_unique(self):
        ids = {
            row["anonymous_id"]
            for row in self.small_sample
        }

        self.assertEqual(
            len(ids),
            len(self.small_sample),
        )

    def test_timestamps_are_chronological(self):
        timestamps = [
            row["installed_at"]
            for row in self.small_sample
        ]

        self.assertEqual(
            timestamps,
            sorted(timestamps),
        )

    def test_timestamps_are_inside_simulation_window(self):
        self.assertTrue(
            all(
                self.start_at
                <= row["installed_at"]
                <= self.end_at
                for row in self.small_sample
            )
        )

    def test_generation_is_reproducible(self):
        second_sample = generate_installations(
            count=10,
            start_at=self.start_at,
            end_at=self.end_at,
        )

        self.assertEqual(
            self.small_sample,
            second_sample,
        )

    def test_dimension_values_are_valid(self):
        for dimension_name in (
            "platform",
            "acquisition_channel",
            "country_code",
        ):
            configured_values = set(
                self.dimensions[dimension_name]["values"]
            )

            generated_values = {
                row[dimension_name]
                for row in self.distribution_sample
            }

            self.assertTrue(
                generated_values.issubset(configured_values)
            )

    def test_empirical_distributions_are_reasonable(self):
        sample_size = len(self.distribution_sample)

        for dimension_name in (
            "platform",
            "acquisition_channel",
            "country_code",
        ):
            counts = Counter(
                row[dimension_name]
                for row in self.distribution_sample
            )

            values = self.dimensions[dimension_name]["values"]
            weights = self.dimensions[dimension_name]["weights"]

            for value, expected_weight in zip(
                values,
                weights,
            ):
                observed_weight = counts[value] / sample_size

                self.assertAlmostEqual(
                    observed_weight,
                    expected_weight,
                    delta=0.015,
                    msg=(
                        f"{dimension_name}={value}: "
                        f"expected approximately {expected_weight:.3f}, "
                        f"observed {observed_weight:.3f}"
                    ),
                )


if __name__ == "__main__":
    unittest.main()