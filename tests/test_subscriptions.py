"""Tests for the Pulse synthetic subscription lifecycle generator."""

from collections import Counter, defaultdict
import unittest

from src.generation.installations import (
    generate_installations,
    get_simulation_bounds,
)
from src.generation.product_events import (
    LIFECYCLE_EVENT_NAMES,
    USAGE_EVENT_NAMES,
    generate_product_events,
)
from src.generation.subscriptions import (
    SUBSCRIPTION_EVENT_NAMES,
    generate_subscription_lifecycle,
    get_snapshot_at,
    load_subscription_config,
    merge_subscription_events,
)
from src.generation.users import generate_users


class SubscriptionLifecycleGeneratorTests(unittest.TestCase):
    """Validate subscription, billing and monetisation event generation."""

    @classmethod
    def setUpClass(cls):
        cls.start_at, cls.end_at = get_simulation_bounds()
        cls.installations = generate_installations(
            count=3_000,
            start_at=cls.start_at,
            end_at=cls.end_at,
        )
        cls.users = generate_users(cls.installations)
        cls.product_events = generate_product_events(
            cls.installations,
            cls.users,
        )
        (
            cls.subscriptions,
            cls.transactions,
            cls.subscription_events,
        ) = generate_subscription_lifecycle(
            cls.users,
            cls.product_events,
        )
        cls.merged_events = merge_subscription_events(
            cls.product_events,
            cls.subscription_events,
        )
        cls.snapshot_at = get_snapshot_at()
        cls.config = load_subscription_config()
        cls.users_by_id = {
            row["user_id"]: row
            for row in cls.users
        }
        cls.subscriptions_by_id = {
            row["subscription_id"]: row
            for row in cls.subscriptions
        }

    def test_subscription_schema(self):
        expected_fields = {
            "subscription_id",
            "user_id",
            "installation_id",
            "billing_period",
            "price_gbp",
            "currency",
            "status",
            "trial_started_at",
            "trial_ends_at",
            "subscription_started_at",
            "current_period_start_at",
            "current_period_end_at",
            "cancellation_requested_at",
            "expired_at",
            "auto_renew",
            "end_reason",
        }

        for subscription in self.subscriptions:
            self.assertEqual(
                set(subscription),
                expected_fields,
            )

    def test_transaction_schema(self):
        expected_fields = {
            "transaction_id",
            "subscription_id",
            "user_id",
            "installation_id",
            "transaction_type",
            "attempted_at",
            "billing_period",
            "amount_gbp",
            "currency",
            "payment_status",
            "billing_cycle_number",
            "attempt_number",
        }

        for transaction in self.transactions:
            self.assertEqual(
                set(transaction),
                expected_fields,
            )

    def test_subscription_event_schema_and_names(self):
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

        for event in self.subscription_events:
            self.assertEqual(
                set(event),
                expected_fields,
            )
            self.assertIn(
                event["event_name"],
                SUBSCRIPTION_EVENT_NAMES,
            )
            self.assertIsNotNone(event["user_id"])
            self.assertIsNone(event["session_id"])
            self.assertIsNone(event["feature_name"])

    def test_only_registered_users_can_have_subscriptions(self):
        registered_user_ids = set(self.users_by_id)
        subscription_user_ids = {
            row["user_id"]
            for row in self.subscriptions
        }

        self.assertTrue(
            subscription_user_ids
            <= registered_user_ids
        )
        self.assertEqual(
            len(subscription_user_ids),
            len(self.subscriptions),
        )

    def test_every_trial_has_prior_registered_paywall_exposure(self):
        paywalls_by_user = defaultdict(list)
        for event in self.product_events:
            if (
                event["event_name"] == "paywall_viewed"
                and event["user_id"] is not None
            ):
                paywalls_by_user[event["user_id"]].append(
                    event["occurred_at"]
                )

        for subscription in self.subscriptions:
            user = self.users_by_id[subscription["user_id"]]
            prior_paywalls = [
                timestamp
                for timestamp in paywalls_by_user[
                    subscription["user_id"]
                ]
                if (
                    user["signed_up_at"]
                    <= timestamp
                    <= subscription["trial_started_at"]
                )
            ]
            self.assertTrue(prior_paywalls)

    def test_subscription_timestamps_are_chronologically_valid(self):
        for subscription in self.subscriptions:
            user = self.users_by_id[subscription["user_id"]]

            self.assertGreaterEqual(
                subscription["trial_started_at"],
                user["signed_up_at"],
            )
            self.assertGreater(
                subscription["trial_ends_at"],
                subscription["trial_started_at"],
            )

            started_at = subscription["subscription_started_at"]
            if started_at is not None:
                self.assertGreaterEqual(
                    started_at,
                    subscription["trial_ends_at"],
                )
                self.assertLess(
                    started_at,
                    self.snapshot_at,
                )

            cancellation_at = subscription[
                "cancellation_requested_at"
            ]
            if cancellation_at is not None:
                self.assertIsNotNone(started_at)
                self.assertGreaterEqual(
                    cancellation_at,
                    started_at,
                )
                self.assertLess(
                    cancellation_at,
                    self.snapshot_at,
                )

            expired_at = subscription["expired_at"]
            if expired_at is not None:
                self.assertGreaterEqual(
                    expired_at,
                    subscription["trial_ends_at"],
                )
                self.assertLess(
                    expired_at,
                    self.snapshot_at,
                )

    def test_observed_events_and_transactions_are_before_snapshot(self):
        for event in self.subscription_events:
            self.assertLess(
                event["occurred_at"],
                self.snapshot_at,
            )

        for transaction in self.transactions:
            self.assertLess(
                transaction["attempted_at"],
                self.snapshot_at,
            )

    def test_statuses_are_consistent_with_observed_state(self):
        allowed_statuses = {
            "trialing",
            "active",
            "cancel_at_period_end",
            "past_due",
            "expired",
        }

        for subscription in self.subscriptions:
            status = subscription["status"]
            self.assertIn(status, allowed_statuses)

            if status == "trialing":
                self.assertGreaterEqual(
                    subscription["trial_ends_at"],
                    self.snapshot_at,
                )
                self.assertIsNone(
                    subscription["subscription_started_at"]
                )
                self.assertIsNone(subscription["expired_at"])

            elif status == "active":
                self.assertIsNotNone(
                    subscription["subscription_started_at"]
                )
                self.assertIsNone(subscription["expired_at"])
                self.assertTrue(subscription["auto_renew"])
                self.assertGreaterEqual(
                    subscription["current_period_end_at"],
                    self.snapshot_at,
                )

            elif status == "cancel_at_period_end":
                self.assertIsNotNone(
                    subscription["cancellation_requested_at"]
                )
                self.assertIsNone(subscription["expired_at"])
                self.assertFalse(subscription["auto_renew"])
                self.assertGreaterEqual(
                    subscription["current_period_end_at"],
                    self.snapshot_at,
                )

            elif status == "expired":
                self.assertIsNotNone(subscription["expired_at"])
                self.assertFalse(subscription["auto_renew"])

    def test_transactions_match_subscription_terms(self):
        for transaction in self.transactions:
            subscription = self.subscriptions_by_id[
                transaction["subscription_id"]
            ]
            self.assertEqual(
                transaction["user_id"],
                subscription["user_id"],
            )
            self.assertEqual(
                transaction["installation_id"],
                subscription["installation_id"],
            )
            self.assertEqual(
                transaction["billing_period"],
                subscription["billing_period"],
            )
            self.assertEqual(
                transaction["amount_gbp"],
                subscription["price_gbp"],
            )
            self.assertEqual(
                transaction["currency"],
                subscription["currency"],
            )
            self.assertIn(
                transaction["transaction_type"],
                {"initial_charge", "renewal"},
            )
            self.assertIn(
                transaction["payment_status"],
                {"succeeded", "failed"},
            )
            self.assertGreaterEqual(
                transaction["billing_cycle_number"],
                1,
            )
            self.assertIn(
                transaction["attempt_number"],
                {1, 2},
            )

    def test_failed_transactions_have_payment_failed_events(self):
        failed_by_user_time = Counter(
            (
                row["user_id"],
                row["attempted_at"],
            )
            for row in self.transactions
            if row["payment_status"] == "failed"
        )
        failure_events = Counter(
            (
                row["user_id"],
                row["occurred_at"],
            )
            for row in self.subscription_events
            if row["event_name"] == "payment_failed"
        )
        self.assertEqual(
            failure_events,
            failed_by_user_time,
        )

    def test_successful_payments_have_correct_lifecycle_events(self):
        successful_initial = Counter(
            (row["user_id"], row["attempted_at"])
            for row in self.transactions
            if (
                row["transaction_type"] == "initial_charge"
                and row["payment_status"] == "succeeded"
            )
        )
        successful_renewals = Counter(
            (row["user_id"], row["attempted_at"])
            for row in self.transactions
            if (
                row["transaction_type"] == "renewal"
                and row["payment_status"] == "succeeded"
            )
        )
        started_events = Counter(
            (row["user_id"], row["occurred_at"])
            for row in self.subscription_events
            if row["event_name"] == "subscription_started"
        )
        renewal_events = Counter(
            (row["user_id"], row["occurred_at"])
            for row in self.subscription_events
            if row["event_name"] == "subscription_renewed"
        )

        self.assertEqual(started_events, successful_initial)
        self.assertEqual(renewal_events, successful_renewals)

    def test_cancellation_and_expiry_fields_have_matching_events(self):
        cancellation_events = {
            (row["user_id"], row["occurred_at"])
            for row in self.subscription_events
            if row["event_name"] == "cancellation_requested"
        }
        expiry_events = {
            (row["user_id"], row["occurred_at"])
            for row in self.subscription_events
            if row["event_name"] == "subscription_expired"
        }

        for subscription in self.subscriptions:
            cancellation_at = subscription[
                "cancellation_requested_at"
            ]
            if cancellation_at is not None:
                self.assertIn(
                    (subscription["user_id"], cancellation_at),
                    cancellation_events,
                )

            expired_at = subscription["expired_at"]
            if expired_at is not None:
                self.assertIn(
                    (subscription["user_id"], expired_at),
                    expiry_events,
                )

    def test_merged_product_events_preserve_base_event_payloads(self):
        base_names = set(
            LIFECYCLE_EVENT_NAMES + USAGE_EVENT_NAMES
        )

        def signature(row):
            return (
                row["event_name"],
                row["occurred_at"],
                row["installation_id"],
                row["anonymous_id"],
                row["user_id"],
                row["session_id"],
                row["feature_name"],
            )

        original = Counter(
            signature(row)
            for row in self.product_events
        )
        merged_base = Counter(
            signature(row)
            for row in self.merged_events
            if row["event_name"] in base_names
        )

        self.assertEqual(original, merged_base)
        self.assertEqual(
            len(self.merged_events),
            len(self.product_events)
            + len(self.subscription_events),
        )

    def test_merged_events_are_sorted_and_have_unique_ids(self):
        timestamps = [
            row["occurred_at"]
            for row in self.merged_events
        ]
        event_ids = {
            row["event_id"]
            for row in self.merged_events
        }

        self.assertEqual(timestamps, sorted(timestamps))
        self.assertEqual(
            len(event_ids),
            len(self.merged_events),
        )

    def test_moderate_sample_business_rates_are_sane(self):
        exposed_users = {
            row["user_id"]
            for row in self.product_events
            if (
                row["event_name"] == "paywall_viewed"
                and row["user_id"] is not None
            )
        }
        self.assertTrue(exposed_users)
        self.assertTrue(self.subscriptions)

        trial_rate = (
            len(self.subscriptions)
            / len(exposed_users)
        )
        self.assertGreater(trial_rate, 0.05)
        self.assertLess(trial_rate, 0.65)

        matured_trials = [
            row
            for row in self.subscriptions
            if row["trial_ends_at"] < self.snapshot_at
        ]
        self.assertTrue(matured_trials)

        paid_trials = [
            row
            for row in matured_trials
            if row["subscription_started_at"] is not None
        ]
        paid_conversion_rate = (
            len(paid_trials)
            / len(matured_trials)
        )
        self.assertGreater(paid_conversion_rate, 0.15)
        self.assertLess(paid_conversion_rate, 0.85)

        annual_share = (
            sum(
                row["billing_period"] == "annual"
                for row in self.subscriptions
            )
            / len(self.subscriptions)
        )
        self.assertGreater(annual_share, 0.10)
        self.assertLess(annual_share, 0.40)

        if self.transactions:
            failed_share = (
                sum(
                    row["payment_status"] == "failed"
                    for row in self.transactions
                )
                / len(self.transactions)
            )
            self.assertLess(failed_share, 0.12)

    def test_generation_is_deterministic(self):
        repeated = generate_subscription_lifecycle(
            self.users,
            self.product_events,
        )
        self.assertEqual(
            repeated,
            (
                self.subscriptions,
                self.transactions,
                self.subscription_events,
            ),
        )


if __name__ == "__main__":
    unittest.main()