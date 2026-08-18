from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "validation"
    / "002_create_raw_validation_views.sql"
)


class RawValidationViewsSqlTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SQL_PATH.read_text(
            encoding="utf-8"
        ).lower()

    def test_sql_file_exists(self) -> None:
        self.assertTrue(SQL_PATH.is_file())

    def test_dataset_counts_view_exists(self) -> None:
        self.assertIn(
            "validation.raw_dataset_counts",
            self.sql,
        )

    def test_reconciliation_view_exists(self) -> None:
        self.assertIn(
            "validation.raw_reconciliation",
            self.sql,
        )

    def test_all_eight_raw_tables_are_counted(self) -> None:
        tables = (
            "installations",
            "users",
            "product_events",
            "subscriptions",
            "subscription_transactions",
            "experiment_assignments",
            "marketing_spend",
            "app_releases",
        )

        for table in tables:
            self.assertRegex(
                self.sql,
                re.compile(
                    rf"from\s+raw\.{table}\b"
                ),
            )

    def test_reconciliation_uses_ingestion_file_metadata(
        self,
    ) -> None:
        self.assertIn(
            "from raw.ingestion_files as f",
            self.sql,
        )

    def test_reconciliation_exposes_deltas(self) -> None:
        self.assertIn(
            "accepted_vs_actual_delta",
            self.sql,
        )
        self.assertIn(
            "expected_vs_processed_delta",
            self.sql,
        )
        self.assertIn(
            "reconciled",
            self.sql,
        )

    def test_views_do_not_mutate_raw_data(self) -> None:
        forbidden = (
            r"\binsert\s+into\s+raw\.",
            r"\bupdate\s+raw\.",
            r"\bdelete\s+from\s+raw\.",
            r"\btruncate\s+raw\.",
            r"\bdrop\s+table\s+raw\.",
        )

        for pattern in forbidden:
            self.assertNotRegex(
                self.sql,
                pattern,
            )


if __name__ == "__main__":
    unittest.main()
