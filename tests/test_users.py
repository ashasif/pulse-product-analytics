"""Tests for the Pulse synthetic registered-user lifecycle generator."""

from collections import Counter
from datetime import timedelta
import unittest

from src.generation.installations import (
    generate_installations,
    get_simulation_bounds,
)
from src.generation.users import (
    generate_users,
    load_user_lifecycle_config,
)


class UserGeneratorTests(unittest.TestCase):
    """Validate signup identity and onboarding lifecycle behaviour."""

    @classmethod
    def setUpClass(cls):
        """Build one reusable deterministic sample."""
        cls.start_at, cls.end_at = get_simulation_bounds()

        cls.installations = generate_installations(
            count=20_000,
            start_at=cls.start_at,
            end_at=cls.end_at,
        )

        cls.users = generate_users(
            cls.installations
        )

        cls.lifecycle = load_user_lifecycle_config()

        cls.installations_by_id = {
            row["installation_id"]: row
            for row in cls.installations
        }

    def test_generation_is_reproducible(self):
        """Same inputs and seeds must reproduce identical users."""
        second_sample = generate_users(
            self.installations
        )

        self.assertEqual(
            self.users,
            second_sample,
        )

    def test_only_signed_up_installations_become_users(self):
        """Registered users must be a subset of installations."""
        self.assertGreater(
            len(self.users),
            0,
        )

        self.assertLess(
            len(self.users),
            len(self.installations),
        )

        installation_ids = set(
            self.installations_by_id
        )

        self.assertTrue(
            all(
                user["installation_id"] in installation_ids
                for user in self.users
            )
        )

    def test_user_ids_are_unique(self):
        """Every registered user must have a unique user_id."""
        user_ids = [
            row["user_id"]
            for row in self.users
        ]

        self.assertEqual(
            len(user_ids),
            len(set(user_ids)),
        )

    def test_installation_ids_are_unique_in_users(self):
        """One installation can create at most one registered user."""
        installation_ids = [
            row["installation_id"]
            for row in self.users
        ]

        self.assertEqual(
            len(installation_ids),
            len(set(installation_ids)),
        )

    def test_anonymous_ids_are_unique_in_users(self):
        """Registered users should preserve unique anonymous identities."""
        anonymous_ids = [
            row["anonymous_id"]
            for row in self.users
        ]

        self.assertEqual(
            len(anonymous_ids),
            len(set(anonymous_ids)),
        )

    def test_anonymous_identity_is_retained_after_signup(self):
        """The user's anonymous_id must match the installation."""
        for user in self.users:
            installation = self.installations_by_id[
                user["installation_id"]
            ]

            self.assertEqual(
                user["anonymous_id"],
                installation["anonymous_id"],
            )

    def test_signup_occurs_after_installation(self):
        """Signup must always happen after installation."""
        for user in self.users:
            installation = self.installations_by_id[
                user["installation_id"]
            ]

            self.assertGreater(
                user["signed_up_at"],
                installation["installed_at"],
            )

    def test_onboarding_start_occurs_after_signup(self):
        """Onboarding start cannot precede signup."""
        for user in self.users:
            started_at = user[
                "onboarding_started_at"
            ]

            if started_at is not None:
                self.assertGreaterEqual(
                    started_at,
                    user["signed_up_at"],
                )

    def test_onboarding_completion_requires_start(self):
        """Completion cannot exist without onboarding having started."""
        for user in self.users:
            completed_at = user[
                "onboarding_completed_at"
            ]

            if completed_at is not None:
                self.assertIsNotNone(
                    user["onboarding_started_at"]
                )

    def test_onboarding_completion_occurs_after_start(self):
        """Completed onboarding must occur after onboarding starts."""
        for user in self.users:
            completed_at = user[
                "onboarding_completed_at"
            ]

            if completed_at is not None:
                self.assertGreater(
                    completed_at,
                    user["onboarding_started_at"],
                )

    def test_all_observed_timestamps_are_before_snapshot(self):
        """No lifecycle milestone may occur after the dataset snapshot."""
        snapshot_at = (
            self.end_at
            + timedelta(seconds=1)
        )

        for user in self.users:
            for field in (
                "signed_up_at",
                "onboarding_started_at",
                "onboarding_completed_at",
            ):
                value = user[field]

                if value is not None:
                    self.assertLess(
                        value,
                        snapshot_at,
                    )

    def test_install_to_signup_rate_is_reasonable(self):
        """The sample should reproduce the approximate 62% signup rate."""
        signup_rate = (
            len(self.users)
            / len(self.installations)
        )

        self.assertAlmostEqual(
            signup_rate,
            0.62,
            delta=0.025,
        )

    def test_signup_to_onboarding_start_rate_is_reasonable(self):
        """Approximately 89% of signups should start onboarding."""
        starts = sum(
            row["onboarding_started_at"] is not None
            for row in self.users
        )

        start_rate = (
            starts / len(self.users)
        )

        self.assertAlmostEqual(
            start_rate,
            0.89,
            delta=0.025,
        )

    def test_signup_to_onboarding_completion_rate_is_reasonable(self):
        """Approximately 69% of signups should complete onboarding."""
        completions = sum(
            row["onboarding_completed_at"] is not None
            for row in self.users
        )

        completion_rate = (
            completions / len(self.users)
        )

        self.assertAlmostEqual(
            completion_rate,
            0.69,
            delta=0.03,
        )

    def test_referral_signup_rate_exceeds_paid_social(self):
        """Configured acquisition quality difference should be visible."""
        installs_by_channel = Counter(
            row["acquisition_channel"]
            for row in self.installations
        )

        signups_by_channel = Counter(
            self.installations_by_id[
                user["installation_id"]
            ]["acquisition_channel"]
            for user in self.users
        )

        referral_rate = (
            signups_by_channel["referral"]
            / installs_by_channel["referral"]
        )

        paid_social_rate = (
            signups_by_channel["paid_social"]
            / installs_by_channel["paid_social"]
        )

        self.assertGreater(
            referral_rate,
            paid_social_rate,
        )

    def test_ios_completion_rate_exceeds_android(self):
        """Configured platform completion difference should be visible."""
        signups_by_platform = Counter(
            self.installations_by_id[
                user["installation_id"]
            ]["platform"]
            for user in self.users
        )

        completions_by_platform = Counter(
            self.installations_by_id[
                user["installation_id"]
            ]["platform"]
            for user in self.users
            if user["onboarding_completed_at"] is not None
        )

        ios_rate = (
            completions_by_platform["ios"]
            / signups_by_platform["ios"]
        )

        android_rate = (
            completions_by_platform["android"]
            / signups_by_platform["android"]
        )

        self.assertGreater(
            ios_rate,
            android_rate,
        )

    def test_lifecycle_configuration_matches_design(self):
        """The config should contain the intended base funnel."""
        self.assertEqual(
            self.lifecycle[
                "signup_probability"
            ],
            0.62,
        )

        self.assertEqual(
            self.lifecycle[
                "onboarding_start_given_signup_probability"
            ],
            0.89,
        )

        self.assertAlmostEqual(
            self.lifecycle[
                "onboarding_complete_given_start_probability"
            ],
            0.775,
        )


if __name__ == "__main__":
    unittest.main()