from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

METADATA_PATH = (
    PROJECT_ROOT
    / "sql"
    / "staging"
    / "002_create_promotion_metadata.sql"
)

RECONCILIATION_PATH = (
    PROJECT_ROOT
    / "sql"
    / "staging"
    / "003_create_staging_reconciliation_views.sql"
)


class StagingPromotionMetadataSqlTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = METADATA_PATH.read_text(
            encoding="utf-8"
        ).lower()

    def test_promotion_runs_table_exists(self):
        self.assertIn(
            "create table if not exists "
            "staging.promotion_runs",
            self.sql,
        )

    def test_promotion_references_raw_batch(self):
        self.assertRegex(
            self.sql,
            re.compile(
                r"references\s+raw\.ingestion_batches\s*"
                r"\(\s*ingestion_batch_id\s*\)",
                re.DOTALL,
            ),
        )

    def test_promotion_references_validation_run(self):
        self.assertRegex(
            self.sql,
            re.compile(
                r"references\s+validation\.validation_runs\s*"
                r"\(\s*validation_run_id\s*,\s*"
                r"ingestion_batch_id\s*\)",
                re.DOTALL,
            ),
        )

    def test_success_requires_full_reconciliation(self):
        self.assertRegex(
            self.sql,
            re.compile(
                r"status\s*<>\s*'succeeded'.*?"
                r"promoted_dataset_count\s*"
                r"=\s*expected_dataset_count.*?"
                r"promoted_row_count\s*"
                r"=\s*expected_row_count",
                re.DOTALL,
            ),
        )

    def test_successful_batch_promotion_is_unique(self):
        self.assertIn(
            "uq_promotion_runs_successful_batch",
            self.sql,
        )

        self.assertRegex(
            self.sql,
            re.compile(
                r"where\s+status\s*=\s*'succeeded'",
                re.DOTALL,
            ),
        )

    def test_wall_clock_operational_timestamps(self):
        self.assertGreaterEqual(
            self.sql.count(
                "clock_timestamp()"
            ),
            1,
        )


class StagingReconciliationSqlTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = (
            RECONCILIATION_PATH.read_text(
                encoding="utf-8"
            ).lower()
        )

    def test_staging_counts_view_exists(self):
        self.assertIn(
            "validation.staging_dataset_counts",
            self.sql,
        )

    def test_staging_reconciliation_view_exists(self):
        self.assertIn(
            "validation.staging_reconciliation",
            self.sql,
        )

    def test_all_eight_staging_tables_are_counted(self):
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
                    rf"from\s+staging\.{table}\b"
                ),
            )

    def test_reconciliation_compares_raw_and_staging(self):
        self.assertIn(
            "validation.raw_dataset_counts",
            self.sql,
        )

        self.assertIn(
            "raw_row_count",
            self.sql,
        )

        self.assertIn(
            "staging_row_count",
            self.sql,
        )

        self.assertIn(
            "row_count_delta",
            self.sql,
        )

        self.assertIn(
            "reconciled",
            self.sql,
        )

    def test_views_do_not_mutate_data(self):
        forbidden = (
            r"\binsert\s+into\b",
            r"\bupdate\b",
            r"\bdelete\s+from\b",
            r"\btruncate\b",
        )

        for pattern in forbidden:
            self.assertNotRegex(
                self.sql,
                pattern,
            )


if __name__ == "__main__":
    unittest.main()