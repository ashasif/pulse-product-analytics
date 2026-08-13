"""Tests for the Pulse synthetic product-event generator."""

from collections import Counter
from statistics import mean
import unittest

from src.generation.installations import (
    generate_installations,
    get_simulation_bounds,
)

from src.generation.product_events import (
    LIFECYCLE_EVENT_NAMES,
    USAGE_EVENT_NAMES,
    generate_product_events,
    get_snapshot_at,
    load_product_event_config,
)

from src.generation.users import (
    generate_users,
)


class ProductEventGeneratorTests(
    unittest.TestCase
):
    """
    Validate lifecycle derivation and behavioural event generation.
    """

    @classmethod
    def setUpClass(cls):

        (
            cls.start_at,
            cls.end_at,
        ) = get_simulation_bounds()

        cls.installations = (
            generate_installations(
                count=2_000,
                start_at=cls.start_at,
                end_at=cls.end_at,
            )
        )

        cls.users = generate_users(
            cls.installations
        )

        cls.events = (
            generate_product_events(
                cls.installations,
                cls.users,
            )
        )

        cls.snapshot_at = (
            get_snapshot_at()
        )

        cls.event_config = (
            load_product_event_config()
        )

        cls.installations_by_id = {
            row["installation_id"]: row
            for row in cls.installations
        }

        cls.users_by_installation = {
            row["installation_id"]: row
            for row in cls.users
        }

    def test_event_schema(self):

        expected_fields = {
            "event_id",
            "event_name",
            "occurred_at",
            "installation_id",
            "anonymous_id",
            "user_id",
            "session_id",
            "feature_name",
        }

        for event in self.events:

            self.assertEqual(
                set(event),
                expected_fields,
            )

    def test_event_ids_are_unique(self):

        event_ids = {
            event["event_id"]
            for event in self.events
        }

        self.assertEqual(
            len(event_ids),
            len(self.events),
        )

    def test_events_are_chronologically_sorted(
        self,
    ):

        timestamps = [
            event["occurred_at"]
            for event in self.events
        ]

        self.assertEqual(
            timestamps,
            sorted(timestamps),
        )

    def test_only_step_5_event_names_are_generated(
        self,
    ):

        allowed_names = set(
            LIFECYCLE_EVENT_NAMES
            + USAGE_EVENT_NAMES
        )

        generated_names = {
            event["event_name"]
            for event in self.events
        }

        self.assertTrue(
            generated_names
            <= allowed_names
        )

    def test_app_install_is_derived_exactly(
        self,
    ):

        install_events = {
            event["installation_id"]: event
            for event in self.events
            if event["event_name"]
            == "app_install"
        }

        self.assertEqual(
            len(install_events),
            len(self.installations),
        )

        for installation in (
            self.installations
        ):

            event = install_events[
                installation[
                    "installation_id"
                ]
            ]

            self.assertEqual(
                event["occurred_at"],
                installation[
                    "installed_at"
                ],
            )

            self.assertIsNone(
                event["user_id"]
            )

    def test_signup_is_derived_exactly(
        self,
    ):

        signup_events = {
            event["installation_id"]: event
            for event in self.events
            if event["event_name"]
            == "signup"
        }

        self.assertEqual(
            len(signup_events),
            len(self.users),
        )

        for user in self.users:

            event = signup_events[
                user[
                    "installation_id"
                ]
            ]

            self.assertEqual(
                event["occurred_at"],
                user["signed_up_at"],
            )

            self.assertEqual(
                event["user_id"],
                user["user_id"],
            )

    def test_onboarding_started_is_derived_exactly(
        self,
    ):

        expected = {
            user["installation_id"]:
            user["onboarding_started_at"]
            for user in self.users
            if user[
                "onboarding_started_at"
            ]
            is not None
        }

        actual = {
            event["installation_id"]:
            event["occurred_at"]
            for event in self.events
            if event["event_name"]
            == "onboarding_started"
        }

        self.assertEqual(
            actual,
            expected,
        )

    def test_onboarding_completed_is_derived_exactly(
        self,
    ):

        expected = {
            user["installation_id"]:
            user["onboarding_completed_at"]
            for user in self.users
            if user[
                "onboarding_completed_at"
            ]
            is not None
        }

        actual = {
            event["installation_id"]:
            event["occurred_at"]
            for event in self.events
            if event["event_name"]
            == "onboarding_completed"
        }

        self.assertEqual(
            actual,
            expected,
        )

    def test_identity_switches_at_signup(
        self,
    ):

        for event in self.events:

            user = (
                self.users_by_installation.get(
                    event[
                        "installation_id"
                    ]
                )
            )

            if (
                event["event_name"]
                == "app_install"
            ):

                self.assertIsNone(
                    event["user_id"]
                )

                continue

            if (
                user is None
                or event["occurred_at"]
                < user["signed_up_at"]
            ):

                self.assertIsNone(
                    event["user_id"]
                )

            else:

                self.assertEqual(
                    event["user_id"],
                    user["user_id"],
                )

    def test_anonymous_id_is_preserved(
        self,
    ):

        for event in self.events:

            installation = (
                self.installations_by_id[
                    event[
                        "installation_id"
                    ]
                ]
            )

            self.assertEqual(
                event["anonymous_id"],
                installation[
                    "anonymous_id"
                ],
            )

    def test_generated_events_stay_inside_valid_time_window(
        self,
    ):

        for event in self.events:

            installed_at = (
                self.installations_by_id[
                    event[
                        "installation_id"
                    ]
                ][
                    "installed_at"
                ]
            )

            self.assertGreaterEqual(
                event["occurred_at"],
                installed_at,
            )

            self.assertLess(
                event["occurred_at"],
                self.snapshot_at,
            )

    def test_session_children_reference_existing_session(
        self,
    ):

        session_starts = {
            (
                event[
                    "installation_id"
                ],
                event[
                    "session_id"
                ],
            ):
            event["occurred_at"]
            for event in self.events
            if event["event_name"]
            == "session_started"
        }

        for event in self.events:

            if (
                event["event_name"]
                not in {
                    "feature_used",
                    "paywall_viewed",
                }
            ):
                continue

            key = (
                event[
                    "installation_id"
                ],
                event[
                    "session_id"
                ],
            )

            self.assertIn(
                key,
                session_starts,
            )

            self.assertGreaterEqual(
                event["occurred_at"],
                session_starts[key],
            )

    def test_feature_events_have_valid_feature_names(
        self,
    ):

        valid_features = set(
            self.event_config[
                "feature_mix"
            ]
        )

        for event in self.events:

            if (
                event["event_name"]
                == "feature_used"
            ):

                self.assertIn(
                    event[
                        "feature_name"
                    ],
                    valid_features,
                )

            else:

                self.assertIsNone(
                    event[
                        "feature_name"
                    ]
                )

    def test_lifecycle_events_have_no_session_id(
        self,
    ):

        lifecycle_names = set(
            LIFECYCLE_EVENT_NAMES
        )

        for event in self.events:

            if (
                event["event_name"]
                in lifecycle_names
            ):

                self.assertIsNone(
                    event[
                        "session_id"
                    ]
                )

    def test_onboarding_completers_are_more_engaged_on_average(
        self,
    ):

        session_counts = Counter(
            event["installation_id"]
            for event in self.events
            if event["event_name"]
            == "session_started"
        )

        completed = [
            session_counts[
                user[
                    "installation_id"
                ]
            ]
            for user in self.users
            if user[
                "onboarding_completed_at"
            ]
            is not None
        ]

        incomplete = [
            session_counts[
                user[
                    "installation_id"
                ]
            ]
            for user in self.users
            if user[
                "onboarding_completed_at"
            ]
            is None
        ]

        self.assertTrue(
            completed
        )

        self.assertTrue(
            incomplete
        )

        self.assertGreater(
            mean(completed),
            mean(incomplete),
        )

    def test_generation_is_deterministic(
        self,
    ):

        repeated = (
            generate_product_events(
                self.installations,
                self.users,
            )
        )

        self.assertEqual(
            repeated,
            self.events,
        )


if __name__ == "__main__":
    unittest.main()