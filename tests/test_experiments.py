"""Tests for Pulse synthetic experiment assignments."""

from collections import Counter, defaultdict
from math import sqrt
import unittest

from src.generation.experiments import (
    generate_experiment_assignments,
    get_experiment_snapshot_at,
    load_experiment_config,
)
from src.generation.installations import (
    generate_installations,
    get_simulation_bounds,
)
from src.generation.product_events import (
    generate_product_events,
)
from src.generation.users import (
    generate_users,
)


class ExperimentAssignmentGeneratorTests(
    unittest.TestCase
):
    """Validate experiment assignment generation."""

    @classmethod
    def setUpClass(cls):
        cls.start_at, cls.end_at = (
            get_simulation_bounds()
        )

        cls.installations = (
            generate_installations(
                count=3_000,
                start_at=cls.start_at,
                end_at=cls.end_at,
            )
        )

        cls.users = generate_users(
            cls.installations
        )

        cls.product_events = (
            generate_product_events(
                cls.installations,
                cls.users,
            )
        )

        cls.assignments = (
            generate_experiment_assignments(
                cls.users,
                cls.product_events,
            )
        )

        cls.config = (
            load_experiment_config()
        )

        cls.snapshot_at = (
            get_experiment_snapshot_at()
        )

        cls.users_by_id = {
            row["user_id"]: row
            for row in cls.users
        }

        cls.definitions_by_id = {
            row["experiment_id"]: row
            for row in cls.config[
                "definitions"
            ]
        }

        cls.event_times = defaultdict(
            lambda: defaultdict(set)
        )

        for event in cls.product_events:
            user_id = event["user_id"]

            if user_id is None:
                continue

            cls.event_times[
                user_id
            ][
                event["event_name"]
            ].add(
                event["occurred_at"]
            )

    def test_config_defines_expected_experiments(
        self,
    ):
        expected = {
            "exp_paywall_redesign_2024q3",
            "exp_onboarding_guidance_2025q1",
            "exp_ai_discovery_2025q4",
        }

        actual = {
            row["experiment_id"]
            for row in self.config[
                "definitions"
            ]
        }

        self.assertEqual(
            actual,
            expected,
        )

    def test_assignment_schema(self):
        expected_fields = {
            "assignment_id",
            "experiment_id",
            "experiment_name",
            "user_id",
            "installation_id",
            "randomization_unit",
            "variant",
            "allocation_probability",
            "assignment_at",
            "exposed_at",
            "experiment_start_at",
            "experiment_end_at",
            "eligibility_rule",
            "assignment_trigger",
            "exposure_trigger",
            "hypothesis",
            "primary_metric",
            "secondary_metric",
            "commercial_metric",
            "guardrail_metric",
            "analysis_window_days",
        }

        for assignment in self.assignments:
            self.assertEqual(
                set(assignment),
                expected_fields,
            )

    def test_assignment_ids_and_pairs_are_unique(
        self,
    ):
        assignment_ids = [
            row["assignment_id"]
            for row in self.assignments
        ]

        pairs = [
            (
                row["experiment_id"],
                row["user_id"],
            )
            for row in self.assignments
        ]

        self.assertEqual(
            len(assignment_ids),
            len(set(assignment_ids)),
        )

        self.assertEqual(
            len(pairs),
            len(set(pairs)),
        )

    def test_variants_and_allocation_metadata(
        self,
    ):
        for assignment in self.assignments:
            definition = (
                self.definitions_by_id[
                    assignment[
                        "experiment_id"
                    ]
                ]
            )

            self.assertIn(
                assignment["variant"],
                {"control", "treatment"},
            )

            index = definition[
                "variants"
            ].index(
                assignment["variant"]
            )

            expected_probability = (
                definition[
                    "allocation"
                ][index]
            )

            self.assertEqual(
                assignment[
                    "allocation_probability"
                ],
                expected_probability,
            )

            self.assertEqual(
                assignment[
                    "randomization_unit"
                ],
                "user",
            )

    def test_assignment_chronology_and_identity(
        self,
    ):
        for assignment in self.assignments:
            user = self.users_by_id[
                assignment["user_id"]
            ]

            self.assertEqual(
                assignment[
                    "installation_id"
                ],
                user["installation_id"],
            )

            self.assertGreaterEqual(
                assignment[
                    "assignment_at"
                ],
                user["signed_up_at"],
            )

            self.assertGreaterEqual(
                assignment[
                    "assignment_at"
                ],
                assignment[
                    "experiment_start_at"
                ],
            )

            self.assertLess(
                assignment[
                    "assignment_at"
                ],
                assignment[
                    "experiment_end_at"
                ],
            )

            self.assertLess(
                assignment[
                    "assignment_at"
                ],
                self.snapshot_at,
            )

            exposed_at = assignment[
                "exposed_at"
            ]

            if exposed_at is not None:
                self.assertGreaterEqual(
                    exposed_at,
                    assignment[
                        "assignment_at"
                    ],
                )

                self.assertLess(
                    exposed_at,
                    assignment[
                        "experiment_end_at"
                    ],
                )

                self.assertLess(
                    exposed_at,
                    self.snapshot_at,
                )

    def test_paywall_experiment_eligibility(
        self,
    ):
        rows = [
            row
            for row in self.assignments
            if row["eligibility_rule"]
            == "paywall_viewers"
        ]

        self.assertTrue(rows)

        for assignment in rows:
            user = self.users_by_id[
                assignment["user_id"]
            ]

            assignment_at = assignment[
                "assignment_at"
            ]

            self.assertGreaterEqual(
                assignment_at,
                user["signed_up_at"],
            )

            self.assertIn(
                assignment_at,
                self.event_times[
                    assignment["user_id"]
                ]["paywall_viewed"],
            )

            self.assertEqual(
                assignment["exposed_at"],
                assignment_at,
            )

    def test_onboarding_experiment_eligibility(
        self,
    ):
        rows = [
            row
            for row in self.assignments
            if row["eligibility_rule"]
            == "new_signups"
        ]

        self.assertTrue(rows)

        for assignment in rows:
            user = self.users_by_id[
                assignment["user_id"]
            ]

            self.assertEqual(
                assignment[
                    "assignment_at"
                ],
                user["signed_up_at"],
            )

            onboarding_started_at = user[
                "onboarding_started_at"
            ]

            expected_exposure = None

            if (
                onboarding_started_at
                is not None
                and assignment[
                    "assignment_at"
                ]
                <= onboarding_started_at
                < assignment[
                    "experiment_end_at"
                ]
            ):
                expected_exposure = (
                    onboarding_started_at
                )

            self.assertEqual(
                assignment["exposed_at"],
                expected_exposure,
            )

    def test_onboarded_session_experiment_eligibility(
        self,
    ):
        rows = [
            row
            for row in self.assignments
            if row["eligibility_rule"]
            == "onboarded_session_users"
        ]

        self.assertTrue(rows)

        for assignment in rows:
            user = self.users_by_id[
                assignment["user_id"]
            ]

            completed_at = user[
                "onboarding_completed_at"
            ]

            self.assertIsNotNone(
                completed_at
            )

            self.assertLessEqual(
                completed_at,
                assignment[
                    "assignment_at"
                ],
            )

            self.assertIn(
                assignment[
                    "assignment_at"
                ],
                self.event_times[
                    assignment["user_id"]
                ]["session_started"],
            )

            self.assertEqual(
                assignment["exposed_at"],
                assignment[
                    "assignment_at"
                ],
            )

    def test_allocation_balance_is_reasonable(
        self,
    ):
        rows_by_experiment = defaultdict(
            list
        )

        for row in self.assignments:
            rows_by_experiment[
                row["experiment_id"]
            ].append(row)

        for experiment_id, rows in (
            rows_by_experiment.items()
        ):
            self.assertGreater(
                len(rows),
                20,
            )

            definition = (
                self.definitions_by_id[
                    experiment_id
                ]
            )

            counts = Counter(
                row["variant"]
                for row in rows
            )

            n = len(rows)

            for variant, probability in zip(
                definition["variants"],
                definition[
                    "allocation"
                ],
                strict=True,
            ):
                observed = (
                    counts[variant] / n
                )

                standard_error = sqrt(
                    probability
                    * (1.0 - probability)
                    / n
                )

                tolerance = max(
                    0.08,
                    4.0
                    * standard_error,
                )

                self.assertLessEqual(
                    abs(
                        observed
                        - probability
                    ),
                    tolerance,
                )

    def test_generation_is_deterministic_and_order_invariant(
        self,
    ):
        repeated = (
            generate_experiment_assignments(
                self.users,
                self.product_events,
            )
        )

        reversed_inputs = (
            generate_experiment_assignments(
                list(reversed(self.users)),
                list(
                    reversed(
                        self.product_events
                    )
                ),
            )
        )

        self.assertEqual(
            self.assignments,
            repeated,
        )

        self.assertEqual(
            self.assignments,
            reversed_inputs,
        )

    def test_every_experiment_has_assignments(
        self,
    ):
        expected = set(
            self.definitions_by_id
        )

        actual = {
            row["experiment_id"]
            for row in self.assignments
        }

        self.assertEqual(
            actual,
            expected,
        )


if __name__ == "__main__":
    unittest.main()