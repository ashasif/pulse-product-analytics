"""Static tests for the Pulse PostgreSQL raw-layer foundation."""

from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SCHEMA_SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "raw"
    / "001_create_schemas.sql"
)

METADATA_SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "raw"
    / "002_create_ingestion_metadata.sql"
)


class PostgreSQLFoundationSQLTests(unittest.TestCase):
    """Validate the Step 3 PostgreSQL foundation without a live database."""

    @classmethod
    def setUpClass(cls):
        cls.schema_sql = SCHEMA_SQL_PATH.read_text(
            encoding="utf-8"
        ).lower()

        cls.metadata_sql = METADATA_SQL_PATH.read_text(
            encoding="utf-8"
        ).lower()

    def test_foundation_sql_files_exist(self):
        self.assertTrue(SCHEMA_SQL_PATH.is_file())
        self.assertTrue(METADATA_SQL_PATH.is_file())

    def test_all_approved_schemas_are_created(self):
        for schema_name in (
            "raw",
            "staging",
            "analytics",
            "validation",
        ):
            self.assertIn(
                f"create schema if not exists {schema_name}",
                self.schema_sql,
            )

    def test_ingestion_batches_table_exists(self):
        self.assertIn(
            "create table if not exists raw.ingestion_batches",
            self.metadata_sql,
        )

    def test_ingestion_files_table_exists(self):
        self.assertIn(
            "create table if not exists raw.ingestion_files",
            self.metadata_sql,
        )

    def test_batch_metadata_contains_snapshot_id(self):
        self.assertIn(
            "snapshot_id text not null",
            self.metadata_sql,
        )

    def test_batch_metadata_tracks_expected_and_actual_rows(self):
        required_columns = (
            "expected_row_count bigint not null",
            "accepted_row_count bigint not null",
            "rejected_row_count bigint not null",
        )

        for column in required_columns:
            self.assertIn(column, self.metadata_sql)

    def test_file_metadata_contains_sha256(self):
        self.assertIn(
            "file_sha256 text not null",
            self.metadata_sql,
        )

        self.assertIn(
            "^[0-9a-f]{64}$",
            self.metadata_sql,
        )

    def test_file_metadata_references_batch(self):
        self.assertIn(
            "references raw.ingestion_batches",
            self.metadata_sql,
        )

    def test_successful_snapshot_has_database_idempotency_guard(self):
        self.assertIn(
            "uq_ingestion_batches_successful_snapshot",
            self.metadata_sql,
        )

        self.assertIn(
            "where status = 'succeeded'",
            self.metadata_sql,
        )

    def test_file_is_unique_within_batch(self):
        self.assertIn(
            "uq_ingestion_files_batch_source",
            self.metadata_sql,
        )

    def test_dataset_is_unique_within_batch(self):
        self.assertIn(
            "uq_ingestion_files_batch_dataset",
            self.metadata_sql,
        )

    def test_metadata_uses_bigint_for_row_counts(self):
        self.assertIn(
            "expected_row_count bigint",
            self.metadata_sql,
        )

        self.assertIn(
            "accepted_row_count bigint",
            self.metadata_sql,
        )

        self.assertIn(
            "rejected_row_count bigint",
            self.metadata_sql,
        )

    def test_batch_statuses_are_explicit(self):
        for status in (
            "'running'",
            "'succeeded'",
            "'failed'",
        ):
            self.assertIn(status, self.metadata_sql)

    def test_file_statuses_are_explicit(self):
        for status in (
            "'pending'",
            "'loading'",
            "'loaded'",
            "'failed'",
            "'rolled_back'",
        ):
            self.assertIn(status, self.metadata_sql)

    def test_metadata_ddl_is_transaction_wrapped(self):
        self.assertTrue(
            self.metadata_sql.strip().startswith(
                "-- pulse"
            )
        )

        self.assertIn(
            "begin;",
            self.metadata_sql,
        )

        self.assertTrue(
            self.metadata_sql.strip().endswith(
                "commit;"
            )
        )


if __name__ == "__main__":
    unittest.main()