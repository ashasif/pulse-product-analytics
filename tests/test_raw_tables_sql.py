"""Tests for deterministic Pulse source-row hashing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from src.ingestion.row_hash import (
    RowHashError,
    canonical_row_payload,
    compute_row_hash,
)


class RowHashTests(unittest.TestCase):

    def setUp(self):
        self.columns = (
            "subscription_id",
            "price_gbp",
            "auto_renew",
            "subscription_started_at",
            "expired_at",
        )

        self.values = {
            "subscription_id": "sub_000001",
            "price_gbp": Decimal("9.9900"),
            "auto_renew": True,
            "subscription_started_at": datetime(
                2026,
                1,
                2,
                3,
                4,
                5,
                tzinfo=timezone.utc,
            ),
            "expired_at": None,
        }

    def test_hash_is_sha256_hex(self):
        result = compute_row_hash(
            dataset_name="subscriptions",
            values=self.values,
            columns=self.columns,
        )

        self.assertEqual(
            len(result),
            64,
        )

        int(result, 16)

    def test_hash_matches_locked_reference(self):
        result = compute_row_hash(
            dataset_name="subscriptions",
            values=self.values,
            columns=self.columns,
        )

        self.assertEqual(
            result,
            (
                "91d4c7e012af37acf2e153492daa07e5c"
                "44d845c91139dfb498aa497d6d3c9e3"
            ),
        )

    def test_dictionary_insertion_order_does_not_change_hash(self):
        reordered = {
            "expired_at": None,
            "auto_renew": True,
            "subscription_started_at":
                self.values["subscription_started_at"],
            "price_gbp": Decimal("9.9900"),
            "subscription_id": "sub_000001",
        }

        first = compute_row_hash(
            dataset_name="subscriptions",
            values=self.values,
            columns=self.columns,
        )

        second = compute_row_hash(
            dataset_name="subscriptions",
            values=reordered,
            columns=self.columns,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_equivalent_decimals_hash_identically(self):
        first_values = dict(self.values)
        second_values = dict(self.values)

        first_values["price_gbp"] = Decimal("9.9900")
        second_values["price_gbp"] = Decimal("9.99")

        first = compute_row_hash(
            dataset_name="subscriptions",
            values=first_values,
            columns=self.columns,
        )

        second = compute_row_hash(
            dataset_name="subscriptions",
            values=second_values,
            columns=self.columns,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_equivalent_instants_hash_identically(self):
        first_values = dict(self.values)
        second_values = dict(self.values)

        first_values[
            "subscription_started_at"
        ] = datetime(
            2026,
            1,
            2,
            3,
            4,
            5,
            tzinfo=timezone.utc,
        )

        second_values[
            "subscription_started_at"
        ] = datetime(
            2026,
            1,
            2,
            4,
            4,
            5,
            tzinfo=timezone(
                timedelta(hours=1)
            ),
        )

        first = compute_row_hash(
            dataset_name="subscriptions",
            values=first_values,
            columns=self.columns,
        )

        second = compute_row_hash(
            dataset_name="subscriptions",
            values=second_values,
            columns=self.columns,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_changed_business_value_changes_hash(self):
        changed = dict(self.values)

        changed["subscription_id"] = "sub_000002"

        original_hash = compute_row_hash(
            dataset_name="subscriptions",
            values=self.values,
            columns=self.columns,
        )

        changed_hash = compute_row_hash(
            dataset_name="subscriptions",
            values=changed,
            columns=self.columns,
        )

        self.assertNotEqual(
            original_hash,
            changed_hash,
        )

    def test_dataset_name_is_part_of_hash(self):
        first = compute_row_hash(
            dataset_name="subscriptions",
            values=self.values,
            columns=self.columns,
        )

        second = compute_row_hash(
            dataset_name="different_dataset",
            values=self.values,
            columns=self.columns,
        )

        self.assertNotEqual(
            first,
            second,
        )

    def test_missing_column_is_rejected(self):
        values = dict(self.values)

        del values["expired_at"]

        with self.assertRaises(RowHashError):
            compute_row_hash(
                dataset_name="subscriptions",
                values=values,
                columns=self.columns,
            )

    def test_unexpected_column_is_rejected(self):
        values = dict(self.values)

        values["unexpected"] = "value"

        with self.assertRaises(RowHashError):
            compute_row_hash(
                dataset_name="subscriptions",
                values=values,
                columns=self.columns,
            )

    def test_unsupported_type_is_rejected(self):
        values = dict(self.values)

        values["price_gbp"] = 9.99

        with self.assertRaises(RowHashError):
            compute_row_hash(
                dataset_name="subscriptions",
                values=values,
                columns=self.columns,
            )

    def test_canonical_payload_excludes_ingestion_lineage(self):
        payload = canonical_row_payload(
            dataset_name="subscriptions",
            values=self.values,
            columns=self.columns,
        )

        self.assertNotIn(
            "ingestion_batch_id",
            payload,
        )
        self.assertNotIn(
            "source_file",
            payload,
        )
        self.assertNotIn(
            "source_row_number",
            payload,
        )
        self.assertNotIn(
            "ingested_at",
            payload,
        )


if __name__ == "__main__":
    unittest.main()