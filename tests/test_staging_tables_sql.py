from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "staging"
    / "001_create_staging_tables.sql"
)

TABLES = {
    "installations": "installation_id",
    "users": "user_id",
    "product_events": "event_id",
    "subscriptions": "subscription_id",
    "subscription_transactions": "transaction_id",
    "experiment_assignments": "assignment_id",
    "marketing_spend": "marketing_spend_id",
    "app_releases": "app_release_id",
}


class TestStagingTablesSql(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SQL_PATH.read_text(encoding="utf-8").lower()

    def test_sql_file_exists(self) -> None:
        self.assertTrue(SQL_PATH.is_file())

    def test_all_eight_staging_tables_exist(self) -> None:
        for table_name in TABLES:
            self.assertIn(
                f"create table if not exists staging.{table_name}",
                self.sql,
            )

    def test_exactly_eight_staging_tables_are_declared(self) -> None:
        declarations = re.findall(
            r"create\s+table\s+if\s+not\s+exists\s+staging\.",
            self.sql,
        )
        self.assertEqual(len(declarations), 8)

    def test_staging_primary_keys_are_snapshot_aware(self) -> None:
        for business_key in TABLES.values():
            pattern = re.compile(
                rf"primary\s+key\s*\(\s*"
                rf"ingestion_batch_id\s*,\s*"
                rf"{business_key}\s*\)",
                re.DOTALL,
            )
            self.assertRegex(self.sql, pattern)

    def test_every_table_carries_validation_run_lineage(self) -> None:
        self.assertEqual(
            len(
                re.findall(
                    r"validation_run_id\s+bigint\s+not\s+null",
                    self.sql,
                )
            ),
            8,
        )

    def test_every_table_carries_raw_row_hash(self) -> None:
        self.assertEqual(
            len(
                re.findall(
                    r"row_hash\s+text\s+not\s+null",
                    self.sql,
                )
            ),
            8,
        )

    def test_every_table_carries_raw_ingestion_timestamp(self) -> None:
        self.assertEqual(
            len(
                re.findall(
                    r"raw_ingested_at\s+timestamptz\s+not\s+null",
                    self.sql,
                )
            ),
            8,
        )

    def test_every_table_uses_wall_clock_staged_timestamp(self) -> None:
        self.assertEqual(
            len(
                re.findall(
                    r"staged_at\s+timestamptz\s+not\s+null\s+"
                    r"default\s+clock_timestamp\(\)",
                    self.sql,
                )
            ),
            8,
        )

    def test_every_staging_table_references_its_raw_table(self) -> None:
        for table_name in TABLES:
            self.assertRegex(
                self.sql,
                re.compile(
                    rf"references\s+raw\.{table_name}\s*"
                    rf"\(\s*ingestion_batch_id\s*,\s*"
                    rf"source_row_number\s*\)",
                    re.DOTALL,
                ),
            )

    def test_every_table_references_authorising_validation_run(self) -> None:
        references = re.findall(
            r"references\s+validation\.validation_runs\s*"
            r"\(\s*validation_run_id\s*,\s*"
            r"ingestion_batch_id\s*\)",
            self.sql,
            flags=re.DOTALL,
        )
        self.assertEqual(len(references), 8)

    def test_users_reference_installations(self) -> None:
        self.assertRegex(
            self.sql,
            re.compile(
                r"references\s+staging\.installations\s*"
                r"\(\s*ingestion_batch_id\s*,\s*"
                r"installation_id\s*\)",
                re.DOTALL,
            ),
        )

    def test_product_events_reference_users(self) -> None:
        self.assertRegex(
            self.sql,
            re.compile(
                r"references\s+staging\.users\s*"
                r"\(\s*ingestion_batch_id\s*,\s*user_id\s*\)",
                re.DOTALL,
            ),
        )

    def test_transactions_reference_subscriptions(self) -> None:
        self.assertRegex(
            self.sql,
            re.compile(
                r"references\s+staging\.subscriptions\s*"
                r"\(\s*ingestion_batch_id\s*,\s*"
                r"subscription_id\s*\)",
                re.DOTALL,
            ),
        )

    def test_staging_ddl_contains_no_data_mutation_statements(self) -> None:
        forbidden_patterns = (
            r"\binsert\s+into\b",
            r"\bdelete\s+from\b",
            r"\btruncate\b",
            r"\bdrop\s+table\b",
        )
        for pattern in forbidden_patterns:
            self.assertNotRegex(self.sql, pattern)


if __name__ == "__main__":
    unittest.main()
