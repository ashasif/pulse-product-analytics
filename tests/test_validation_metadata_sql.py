from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "validation"
    / "001_create_validation_metadata.sql"
)


class TestValidationMetadataSql(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SQL_PATH.read_text(encoding="utf-8").lower()

    def test_sql_file_exists(self) -> None:
        self.assertTrue(SQL_PATH.is_file())

    def test_validation_runs_table_exists(self) -> None:
        self.assertIn(
            "create table if not exists validation.validation_runs",
            self.sql,
        )

    def test_check_results_table_exists(self) -> None:
        self.assertIn(
            "create table if not exists validation.check_results",
            self.sql,
        )

    def test_validation_run_references_raw_ingestion_batch(self) -> None:
        self.assertRegex(
            self.sql,
            re.compile(
                r"references\s+raw\.ingestion_batches\s*"
                r"\(\s*ingestion_batch_id\s*\)",
                re.DOTALL,
            ),
        )

    def test_validation_status_contract_exists(self) -> None:
        for status in ("running", "succeeded", "failed"):
            self.assertIn(f"'{status}'", self.sql)

    def test_check_categories_exist(self) -> None:
        expected_categories = (
            "reconciliation",
            "uniqueness",
            "referential_integrity",
            "chronology",
            "domain",
            "nullability",
        )
        for category in expected_categories:
            self.assertIn(f"'{category}'", self.sql)

    def test_check_statuses_exist(self) -> None:
        self.assertIn("'passed'", self.sql)
        self.assertIn("'failed'", self.sql)

    def test_passed_checks_require_zero_violations(self) -> None:
        self.assertRegex(
            self.sql,
            re.compile(
                r"status\s*<>\s*'passed'.*?"
                r"violation_count\s*=\s*0",
                re.DOTALL,
            ),
        )

    def test_failed_checks_require_positive_violations(self) -> None:
        self.assertRegex(
            self.sql,
            re.compile(
                r"status\s*<>\s*'failed'.*?"
                r"violation_count\s*>\s*0",
                re.DOTALL,
            ),
        )

    def test_successful_run_requires_all_checks_to_pass(self) -> None:
        self.assertRegex(
            self.sql,
            re.compile(
                r"status\s*<>\s*'succeeded'.*?"
                r"completed_check_count\s*=\s*expected_check_count.*?"
                r"failed_check_count\s*=\s*0",
                re.DOTALL,
            ),
        )

    def test_successful_batch_validation_is_idempotent(self) -> None:
        self.assertIn(
            "uq_validation_runs_successful_batch",
            self.sql,
        )
        self.assertRegex(
            self.sql,
            re.compile(
                r"on\s+validation\.validation_runs\s*"
                r"\(\s*ingestion_batch_id\s*\).*?"
                r"where\s+status\s*=\s*'succeeded'",
                re.DOTALL,
            ),
        )

    def test_operational_timestamps_use_wall_clock_time(self) -> None:
        self.assertGreaterEqual(
            self.sql.count("clock_timestamp()"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
