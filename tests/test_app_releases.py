"""Tests for the Pulse synthetic app-release generator."""

from collections import defaultdict
import re
import unittest

from src.generation.app_releases import (
    VALID_RELEASE_TYPES,
    VALID_ROLLOUT_STRATEGIES,
    generate_app_releases,
    load_app_release_config,
)

from src.generation.installations import (
    generate_installations,
    get_simulation_bounds,
)


SEMVER_PATTERN = re.compile(
    r"^(\d+)\.(\d+)\.(\d+)$"
)


def _semver_tuple(
    value: str,
) -> tuple[int, int, int]:
    """Convert a semantic version into comparable integers."""

    match = SEMVER_PATTERN.fullmatch(
        value
    )

    if match is None:
        raise AssertionError(
            "Invalid semantic version "
            f"in test data: {value}"
        )

    return tuple(
        int(part)
        for part in match.groups()
    )


class AppReleaseGeneratorTests(
    unittest.TestCase
):
    """Validate app-release generation behaviour."""

    @classmethod
    def setUpClass(
        cls,
    ):
        (
            cls.start_at,
            cls.end_at,
        ) = get_simulation_bounds()

        cls.config = (
            load_app_release_config()
        )

        cls.rows = (
            generate_app_releases(
                cls.start_at,
                cls.end_at,
            )
        )

    def test_configuration_has_expected_grain_and_platforms(
        self,
    ):
        self.assertEqual(
            self.config[
                "grain"
            ],
            "release_platform",
        )

        self.assertEqual(
            self.config[
                "release_channel"
            ],
            "production",
        )

        self.assertEqual(
            set(
                self.config[
                    "platforms"
                ]
            ),
            {
                "ios",
                "android",
            },
        )

    def test_row_count_matches_release_platform_grain(
        self,
    ):
        expected = (
            len(
                self.config[
                    "definitions"
                ]
            )
            * len(
                self.config[
                    "platforms"
                ]
            )
        )

        self.assertEqual(
            len(
                self.rows
            ),
            expected,
        )

    def test_app_release_ids_are_unique(
        self,
    ):
        identifiers = {
            row[
                "app_release_id"
            ]
            for row in self.rows
        }

        self.assertEqual(
            len(
                identifiers
            ),
            len(
                self.rows
            ),
        )

    def test_release_platform_pairs_are_unique(
        self,
    ):
        keys = {
            (
                row[
                    "release_key"
                ],
                row[
                    "platform"
                ],
            )
            for row in self.rows
        }

        self.assertEqual(
            len(
                keys
            ),
            len(
                self.rows
            ),
        )

    def test_every_release_has_all_platforms(
        self,
    ):
        platforms_by_release = (
            defaultdict(
                set
            )
        )

        for row in self.rows:
            platforms_by_release[
                row[
                    "release_key"
                ]
            ].add(
                row[
                    "platform"
                ]
            )

        expected = set(
            self.config[
                "platforms"
            ]
        )

        self.assertTrue(
            all(
                platforms
                == expected
                for platforms
                in platforms_by_release.values()
            )
        )

    def test_releases_are_chronological_and_bounded(
        self,
    ):
        timestamps = [
            row[
                "release_at"
            ]
            for row in self.rows
        ]

        self.assertEqual(
            timestamps,
            sorted(
                timestamps
            ),
        )

        self.assertTrue(
            all(
                self.start_at
                <= row[
                    "release_at"
                ]
                <= self.end_at
                for row in self.rows
            )
        )

    def test_rollouts_finish_inside_simulation(
        self,
    ):
        self.assertTrue(
            all(
                row[
                    "release_at"
                ]
                <= row[
                    "rollout_complete_at"
                ]
                <= self.end_at
                for row in self.rows
            )
        )

    def test_release_sequences_are_contiguous_per_platform(
        self,
    ):
        sequences = defaultdict(
            list
        )

        for row in self.rows:
            sequences[
                row[
                    "platform"
                ]
            ].append(
                row[
                    "release_sequence"
                ]
            )

        expected = list(
            range(
                1,
                len(
                    self.config[
                        "definitions"
                    ]
                )
                + 1,
            )
        )

        for values in (
            sequences.values()
        ):
            self.assertEqual(
                values,
                expected,
            )

    def test_versions_increase_per_platform(
        self,
    ):
        versions = defaultdict(
            list
        )

        for row in self.rows:
            versions[
                row[
                    "platform"
                ]
            ].append(
                _semver_tuple(
                    row[
                        "version"
                    ]
                )
            )

        for values in (
            versions.values()
        ):
            self.assertTrue(
                all(
                    current
                    > previous
                    for (
                        previous,
                        current,
                    )
                    in zip(
                        values,
                        values[
                            1:
                        ],
                    )
                )
            )

    def test_release_metadata_uses_controlled_values(
        self,
    ):
        valid_feature_areas = set(
            self.config[
                "valid_feature_areas"
            ]
        )

        self.assertTrue(
            all(
                row[
                    "release_type"
                ]
                in VALID_RELEASE_TYPES
                for row in self.rows
            )
        )

        self.assertTrue(
            all(
                row[
                    "rollout_strategy"
                ]
                in VALID_ROLLOUT_STRATEGIES
                for row in self.rows
            )
        )

        self.assertTrue(
            all(
                row[
                    "feature_area"
                ]
                in valid_feature_areas
                for row in self.rows
            )
        )

        self.assertTrue(
            all(
                row[
                    "release_channel"
                ]
                == "production"
                for row in self.rows
            )
        )

    def test_generation_is_deterministic(
        self,
    ):
        second_run = (
            generate_app_releases(
                self.start_at,
                self.end_at,
            )
        )

        self.assertEqual(
            self.rows,
            second_run,
        )

    def test_subwindow_filtering_is_bounded(
        self,
    ):
        window_start = (
            self.config[
                "definitions"
            ][
                2
            ][
                "release_at"
            ]
        )

        window_end = (
            self.config[
                "definitions"
            ][
                4
            ][
                "release_at"
            ]
        )

        filtered = (
            generate_app_releases(
                window_start,
                window_end,
            )
        )

        self.assertTrue(
            filtered
        )

        self.assertTrue(
            all(
                window_start
                <= row[
                    "release_at"
                ]
                <= window_end
                for row in filtered
            )
        )

        expected_release_keys = {
            definition[
                "release_key"
            ]
            for definition in (
                self.config[
                    "definitions"
                ]
            )
            if (
                window_start
                <= definition[
                    "release_at"
                ]
                <= window_end
            )
        }

        self.assertEqual(
            {
                row[
                    "release_key"
                ]
                for row in filtered
            },
            expected_release_keys,
        )

    def test_app_release_generation_does_not_change_installations(
        self,
    ):
        before = (
            generate_installations(
                500,
                self.start_at,
                self.end_at,
            )
        )

        generate_app_releases(
            self.start_at,
            self.end_at,
        )

        after = (
            generate_installations(
                500,
                self.start_at,
                self.end_at,
            )
        )

        self.assertEqual(
            before,
            after,
        )


if __name__ == "__main__":
    unittest.main()