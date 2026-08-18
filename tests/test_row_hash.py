"""Compatibility tests for the Pulse typed PostgreSQL raw tables."""

from __future__ import annotations

from pathlib import Path
import re
import unittest

from src.ingestion.raw_audit import (
    load_ingestion_contract,
)
from src.validation.field_schema import (
    get_field_rules,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_TABLE_SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "raw"
    / "003_create_raw_tables.sql"
)

POSTGRES_TYPE_BY_FIELD_KIND = {
    "string": "TEXT",
    "timestamp": "TIMESTAMPTZ",
    "date": "DATE",
    "integer": "INTEGER",
    "decimal": "NUMERIC",
    "boolean": "BOOLEAN",
}


class RawTableSQLTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sql = RAW_TABLE_SQL_PATH.read_text(
            encoding="utf-8"
        )

        _, cls.contracts = (
            load_ingestion_contract()
        )

    def _table_body(
        self,
        table_name: str,
    ) -> str:
        pattern = re.compile(
            rf"CREATE TABLE IF NOT EXISTS "
            rf"raw\.{re.escape(table_name)}\s*"
            rf"\((.*?)\n\);",
            flags=re.IGNORECASE | re.DOTALL,
        )

        match = pattern.search(self.sql)

        self.assertIsNotNone(
            match,
            f"Missing raw.{table_name}",
        )

        return match.group(1)

    def _source_column_definition(
        self,
        *,
        body: str,
        column: str,
    ) -> tuple[str, str]:
        pattern = re.compile(
            rf"^\s*{re.escape(column)}\s+"
            rf"(TEXT|TIMESTAMPTZ|DATE|INTEGER|"
            rf"NUMERIC|BOOLEAN)\b([^\n]*)",
            flags=re.IGNORECASE | re.MULTILINE,
        )

        match = pattern.search(body)

        self.assertIsNotNone(
            match,
            f"Missing PostgreSQL column {column}",
        )

        return (
            match.group(1).upper(),
            match.group(2).upper(),
        )

    def test_all_eight_raw_tables_exist(self):
        for contract in self.contracts:
            self.assertIn(
                (
                    "CREATE TABLE IF NOT EXISTS "
                    f"raw.{contract.name}"
                ),
                self.sql,
            )

    def test_source_columns_match_step2_types_and_nullability(
        self,
    ):
        for contract in self.contracts:
            body = self._table_body(
                contract.name
            )

            rules = get_field_rules(
                contract.name
            )

            self.assertEqual(
                tuple(rules),
                contract.columns,
                (
                    f"Step 2 rule order differs from "
                    f"{contract.name} contract."
                ),
            )

            for column in contract.columns:
                rule = rules[column]

                actual_type, definition_tail = (
                    self._source_column_definition(
                        body=body,
                        column=column,
                    )
                )

                expected_type = (
                    POSTGRES_TYPE_BY_FIELD_KIND[
                        str(rule.kind)
                    ]
                )

                self.assertEqual(
                    actual_type,
                    expected_type,
                    (
                        f"{contract.name}.{column}: "
                        f"expected {expected_type}, "
                        f"found {actual_type}"
                    ),
                )

                if rule.nullable:
                    self.assertNotIn(
                        "NOT NULL",
                        definition_tail,
                        (
                            f"{contract.name}.{column} "
                            "should be nullable."
                        ),
                    )
                else:
                    self.assertIn(
                        "NOT NULL",
                        definition_tail,
                        (
                            f"{contract.name}.{column} "
                            "must be NOT NULL."
                        ),
                    )

    def test_every_table_contains_lineage_columns(self):
        required_fragments = (
            "ingestion_batch_id BIGINT NOT NULL",
            "source_file TEXT NOT NULL",
            "source_row_number BIGINT NOT NULL",
            "ingested_at TIMESTAMPTZ NOT NULL",
            "row_hash TEXT NOT NULL",
        )

        for contract in self.contracts:
            body = self._table_body(
                contract.name
            )

            normalized = " ".join(
                body.split()
            )

            for fragment in required_fragments:
                self.assertIn(
                    " ".join(fragment.split()),
                    normalized,
                    (
                        f"{contract.name} missing "
                        f"{fragment}"
                    ),
                )

    def test_lineage_primary_key_protects_repeat_rows(self):
        for contract in self.contracts:
            body = self._table_body(
                contract.name
            )

            normalized = " ".join(
                body.split()
            )

            self.assertIn(
                (
                    "PRIMARY KEY "
                    "( ingestion_batch_id, "
                    "source_row_number )"
                ),
                normalized,
            )

    def test_raw_rows_reference_ingestion_files(self):
        for contract in self.contracts:
            body = self._table_body(
                contract.name
            )

            normalized = " ".join(
                body.split()
            )

            self.assertIn(
                (
                    "REFERENCES raw.ingestion_files "
                    "( ingestion_batch_id, "
                    "source_file )"
                ),
                normalized,
            )

    def test_row_hash_has_sha256_format_constraint(self):
        for contract in self.contracts:
            body = self._table_body(
                contract.name
            )

            self.assertIn(
                "^[0-9a-f]{64}$",
                body,
            )

    def test_raw_layer_does_not_use_generic_text_for_all_fields(
        self,
    ):
        upper_sql = self.sql.upper()

        self.assertIn(
            "TIMESTAMPTZ",
            upper_sql,
        )
        self.assertIn(
            "DATE",
            upper_sql,
        )
        self.assertIn(
            "INTEGER",
            upper_sql,
        )
        self.assertIn(
            "NUMERIC",
            upper_sql,
        )
        self.assertIn(
            "BOOLEAN",
            upper_sql,
        )

    def test_ddl_is_transaction_wrapped(self):
        stripped = self.sql.strip()

        self.assertIn(
            "BEGIN;",
            stripped,
        )

        self.assertTrue(
            stripped.endswith(
                "COMMIT;"
            )
        )


if __name__ == "__main__":
    unittest.main()