"""SQL contract tests for Pulse analytics build metadata."""

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "analytics"
    / "001_create_build_metadata.sql"
)


class AnalyticsBuildMetadataSqlTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sql = SQL_PATH.read_text(encoding="utf-8").lower()

    def test_sql_file_exists(self):
        self.assertTrue(SQL_PATH.is_file())

    def test_build_runs_table_exists(self):
        self.assertIn(
            "create table if not exists analytics.build_runs",
            self.sql,
        )

    def test_build_references_ingestion_batch(self):
        self.assertIn(
            "references raw.ingestion_batches",
            self.sql,
        )

    def test_build_references_validation_run(self):
        self.assertIn(
            "references validation.validation_runs",
            self.sql,
        )

    def test_build_references_staging_promotion(self):
        self.assertIn(
            "references staging.promotion_runs",
            self.sql,
        )

    def test_successful_build_is_idempotent_by_batch(self):
        self.assertIn(
            "uq_analytics_build_runs_successful_batch",
            self.sql,
        )
        self.assertRegex(
            self.sql,
            re.compile(
                r"where\s+status\s*=\s*'succeeded'",
                re.DOTALL,
            ),
        )

    def test_operational_timestamps_use_wall_clock_time(self):
        self.assertIn("clock_timestamp()", self.sql)

    def test_success_requires_all_tables(self):
        self.assertIn(
            "completed_table_count = expected_table_count",
            self.sql,
        )

    def test_failed_run_requires_error_message(self):
        self.assertIn(
            "status <> 'failed'",
            self.sql,
        )
        self.assertIn(
            "error_message is not null",
            self.sql,
        )


if __name__ == "__main__":
    unittest.main()
