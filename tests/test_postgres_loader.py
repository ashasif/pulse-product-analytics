"""Unit tests for the Pulse PostgreSQL raw loader."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import unittest

from src.ingestion.postgres_loader import (
    ExistingSuccessfulBatch,
    IngestionLoadError,
    build_copy_statement,
    build_count_statement,
    copy_columns,
    find_successful_batch,
    rejected_row_message,
    row_to_copy_values,
)
from src.ingestion.raw_audit import (
    DatasetContract,
)
from src.ingestion.row_hash import (
    compute_row_hash,
)
from src.ingestion.typed_parser import (
    ParsedRow,
    RejectedRow,
    RowIssue,
)


class _FakeResult:

    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeConnection:

    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(
        self,
        query,
        params=None,
    ):
        self.calls.append(
            (query, params)
        )

        return _FakeResult(
            self.row
        )


class PostgresLoaderTests(
    unittest.TestCase
):

    def setUp(self):
        self.contract = DatasetContract(
            name="subscriptions",
            filename="subscriptions.csv",
            expected_rows=1,
            columns=(
                "subscription_id",
                "price_gbp",
                "auto_renew",
                "subscription_started_at",
            ),
        )

        self.row = ParsedRow(
            dataset_name="subscriptions",
            source_file="subscriptions.csv",
            source_row_number=2,
            values={
                "subscription_id":
                    "sub_000001",
                "price_gbp":
                    Decimal("9.99"),
                "auto_renew":
                    True,
                "subscription_started_at":
                    datetime(
                        2026,
                        1,
                        2,
                        3,
                        4,
                        5,
                        tzinfo=timezone.utc,
                    ),
            },
        )

    def test_copy_columns_preserve_source_order_then_lineage(
        self,
    ):
        result = copy_columns(
            self.contract
        )

        self.assertEqual(
            result,
            (
                "subscription_id",
                "price_gbp",
                "auto_renew",
                "subscription_started_at",
                "ingestion_batch_id",
                "source_file",
                "source_row_number",
                "row_hash",
            ),
        )

    def test_copy_statement_targets_raw_table(
        self,
    ):
        result = build_copy_statement(
            self.contract
        )

        self.assertEqual(
            result,
            (
                'COPY "raw"."subscriptions" '
                '("subscription_id", '
                '"price_gbp", '
                '"auto_renew", '
                '"subscription_started_at", '
                '"ingestion_batch_id", '
                '"source_file", '
                '"source_row_number", '
                '"row_hash") '
                "FROM STDIN"
            ),
        )

    def test_count_statement_is_batch_scoped(
        self,
    ):
        result = build_count_statement(
            self.contract
        )

        self.assertEqual(
            result,
            (
                'SELECT COUNT(*) '
                'FROM "raw"."subscriptions" '
                "WHERE ingestion_batch_id = %s"
            ),
        )

    def test_unsafe_table_identifier_is_rejected(
        self,
    ):
        unsafe_contract = (
            DatasetContract(
                name="bad;drop_table",
                filename="bad.csv",
                expected_rows=1,
                columns=("id",),
            )
        )

        with self.assertRaises(
            IngestionLoadError
        ):
            build_copy_statement(
                unsafe_contract
            )

    def test_unsafe_column_identifier_is_rejected(
        self,
    ):
        unsafe_contract = (
            DatasetContract(
                name="safe_table",
                filename="safe.csv",
                expected_rows=1,
                columns=(
                    "id",
                    "bad column",
                ),
            )
        )

        with self.assertRaises(
            IngestionLoadError
        ):
            build_copy_statement(
                unsafe_contract
            )

    def test_row_to_copy_values_preserves_lineage(
        self,
    ):
        result = row_to_copy_values(
            contract=self.contract,
            row=self.row,
            ingestion_batch_id=42,
        )

        self.assertEqual(
            result[0],
            "sub_000001",
        )

        self.assertEqual(
            result[1],
            Decimal("9.99"),
        )

        self.assertIs(
            result[2],
            True,
        )

        self.assertEqual(
            result[-4],
            42,
        )

        self.assertEqual(
            result[-3],
            "subscriptions.csv",
        )

        self.assertEqual(
            result[-2],
            2,
        )

        self.assertEqual(
            len(result[-1]),
            64,
        )

    def test_copy_row_hash_matches_row_hash_module(
        self,
    ):
        result = row_to_copy_values(
            contract=self.contract,
            row=self.row,
            ingestion_batch_id=99,
        )

        expected = compute_row_hash(
            dataset_name="subscriptions",
            values=self.row.values,
            columns=self.contract.columns,
        )

        self.assertEqual(
            result[-1],
            expected,
        )

    def test_batch_id_does_not_change_row_hash(
        self,
    ):
        first = row_to_copy_values(
            contract=self.contract,
            row=self.row,
            ingestion_batch_id=1,
        )

        second = row_to_copy_values(
            contract=self.contract,
            row=self.row,
            ingestion_batch_id=999,
        )

        self.assertEqual(
            first[-1],
            second[-1],
        )

    def test_dataset_mismatch_is_rejected(
        self,
    ):
        wrong_row = ParsedRow(
            dataset_name="users",
            source_file="subscriptions.csv",
            source_row_number=2,
            values=self.row.values,
        )

        with self.assertRaises(
            IngestionLoadError
        ):
            row_to_copy_values(
                contract=self.contract,
                row=wrong_row,
                ingestion_batch_id=1,
            )

    def test_rejected_row_message_contains_lineage(
        self,
    ):
        rejected = RejectedRow(
            dataset_name="subscriptions",
            source_file="subscriptions.csv",
            source_row_number=17,
            raw_values=("bad",),
            issues=(
                RowIssue(
                    code="invalid_decimal",
                    field="price_gbp",
                    message=(
                        "Value is not a decimal."
                    ),
                ),
            ),
        )

        result = rejected_row_message(
            rejected
        )

        self.assertIn(
            "subscriptions.csv",
            result,
        )

        self.assertIn(
            "row 17",
            result,
        )

        self.assertIn(
            "invalid_decimal",
            result,
        )

        self.assertIn(
            "price_gbp",
            result,
        )

    def test_find_successful_batch_returns_existing_batch(
        self,
    ):
        connection = _FakeConnection(
            (
                27,
                3_703_681,
                0,
            )
        )

        result = find_successful_batch(
            connection,
            "raw_" + ("a" * 64),
        )

        self.assertIsInstance(
            result,
            ExistingSuccessfulBatch,
        )

        self.assertEqual(
            result.ingestion_batch_id,
            27,
        )

        self.assertEqual(
            result.accepted_rows,
            3_703_681,
        )

        self.assertEqual(
            result.rejected_rows,
            0,
        )

    def test_find_successful_batch_returns_none(
        self,
    ):
        connection = _FakeConnection(
            None
        )

        result = find_successful_batch(
            connection,
            "raw_" + ("b" * 64),
        )

        self.assertIsNone(
            result
        )

    def test_success_lookup_is_snapshot_scoped(
        self,
    ):
        snapshot_id = (
            "raw_"
            + ("c" * 64)
        )

        connection = _FakeConnection(
            None
        )

        find_successful_batch(
            connection,
            snapshot_id,
        )

        self.assertEqual(
            len(connection.calls),
            1,
        )

        _, params = (
            connection.calls[0]
        )

        self.assertEqual(
            params,
            (snapshot_id,),
        )


if __name__ == "__main__":
    unittest.main()