"""Tests for the Pulse synthetic installation generator."""

from collections import Counter
import unittest

from src.generation.installations import (
    generate_installations,
    get_simulation_bounds,
    load_installation_dimensions,
    load_installation_timing,
)


class InstallationGeneratorTests(unittest.TestCase):
    """Validate synthetic installation generation behaviour."""

    @classmethod
    def setUpClass(cls):
        """Create reusable deterministic samples for the test suite."""

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
        """Generator should return exactly the requested number of rows."""

        self.assertEqual(
            len(self.small_sample),
            10,
        )

    def test_installation_ids_are_unique(self):
        """Every installation must have a unique installation ID."""

        installation_ids = {
            row["installation_id"]
            for row in self.small_sample
        }

        self.assertEqual(
            len(installation_ids),
            len(self.small_sample),
        )

    def test_anonymous_ids_are_unique(self):
        """Every installation must have a unique anonymous ID."""

        anonymous_ids = {
            row["anonymous_id"]
            for row in self.small_sample
        }

        self.assertEqual(
            len(anonymous_ids),
            len(self.small_sample),
        )

    def test_timestamps_are_chronological(self):
        """Returned installations should be ordered by installation time."""

        timestamps = [
            row["installed_at"]
            for row in self.small_sample
        ]

        self.assertEqual(
            timestamps,
            sorted(timestamps),
        )

    def test_timestamps_are_inside_simulation_window(self):
        """All installations must fall inside the configured time period."""

        self.assertTrue(
            all(
                self.start_at
                <= row["installed_at"]
                <= self.end_at
                for row in self.small_sample
            )
        )

    def test_generation_is_reproducible(self):
        """Same configuration and seeds must reproduce the same data."""

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
        """Generated dimensions must only contain configured values."""

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
                generated_values.issubset(
                    configured_values
                )
            )

    def test_empirical_distributions_are_reasonable(self):
        """
        Large samples should approximately follow configured probabilities.

        A small tolerance is expected because individual records are
        randomly sampled rather than deterministically allocated.
        """

        sample_size = len(
            self.distribution_sample
        )

        for dimension_name in (
            "platform",
            "acquisition_channel",
            "country_code",
        ):
            counts = Counter(
                row[dimension_name]
                for row in self.distribution_sample
            )

            values = self.dimensions[
                dimension_name
            ]["values"]

            weights = self.dimensions[
                dimension_name
            ]["weights"]

            for value, expected_weight in zip(
                values,
                weights,
            ):
                observed_weight = (
                    counts[value] / sample_size
                )

                self.assertAlmostEqual(
                    observed_weight,
                    expected_weight,
                    delta=0.015,
                    msg=(
                        f"{dimension_name}={value}: "
                        f"expected approximately "
                        f"{expected_weight:.3f}, "
                        f"observed "
                        f"{observed_weight:.3f}"
                    ),
                )

    def test_installation_timing_configuration(self):
        """Timing configuration should have the expected structure."""

        timing = load_installation_timing()

        self.assertEqual(
            timing["growth_model"],
            "linear",
        )

        self.assertEqual(
            len(
                timing[
                    "month_multipliers"
                ]
            ),
            12,
        )

        self.assertEqual(
            len(
                timing[
                    "weekday_multipliers"
                ]
            ),
            7,
        )

        self.assertGreater(
            timing[
                "growth_end_multiplier"
            ],
            timing[
                "growth_start_multiplier"
            ],
        )

    def test_installation_volume_grows_over_time(self):
        """
        Later equivalent periods should contain more installations.

        Jan-Jun 2024 and Jan-Jun 2026 are compared so that the same
        calendar months are used on both sides, reducing seasonal bias.
        """

        sample = generate_installations(
            count=20_000,
            start_at=self.start_at,
            end_at=self.end_at,
        )

        early_period = sum(
            row["installed_at"].year == 2024
            and row["installed_at"].month <= 6
            for row in sample
        )

        late_period = sum(
            row["installed_at"].year == 2026
            and row["installed_at"].month <= 6
            for row in sample
        )

        self.assertGreater(
            late_period,
            early_period,
        )


if __name__ == "__main__":
    unittest.main()