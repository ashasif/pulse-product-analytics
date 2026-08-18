"""Contract tests for Pulse Step 5 analytics validation controls."""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "analytics"
    / "005_create_analytics_validation.sql"
)


class AnalyticsValidationSqlTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sql = SQL_PATH.read_text(
            encoding="utf-8"
        ).lower()

    def test_sql_file_exists(self):
        self.assertTrue(SQL_PATH.is_file())

    def test_check_results_table_exists(self):
        self.assertIn(
            "validation.analytics_check_results",
            self.sql,
        )

    def test_lineage_reconciliation_view_exists(self):
        self.assertIn(
            "validation.analytics_lineage_reconciliation",
            self.sql,
        )

    def test_validation_function_exists(self):
        self.assertIn(
            "validation.validate_analytics_build",
            self.sql,
        )

    def test_validation_has_23_checks(self):
        self.assertIn(
            "23::integer",
            self.sql,
        )

    def test_all_direct_datasets_have_lineage_checks(self):
        for dataset in (
            "installations",
            "users",
            "product_events",
            "subscriptions",
            "subscription_transactions",
            "experiment_assignments",
            "marketing_spend",
            "app_releases",
        ):
            self.assertIn(
                f"'{dataset}'",
                self.sql,
            )

    def test_lineage_uses_row_hash(self):
        self.assertIn(
            "row_hash",
            self.sql,
        )

    def test_lineage_uses_source_row_number(self):
        self.assertIn(
            "source_row_number",
            self.sql,
        )

    def test_relationship_checks_exist(self):
        for check in (
            "relationship_users_installation",
            "relationship_product_events",
            "relationship_subscriptions",
            "relationship_subscription_transactions",
            "relationship_experiment_assignments",
        ):
            self.assertIn(
                check,
                self.sql,
            )

    def test_date_integrity_check_exists(self):
        self.assertIn(
            "date_key_integrity",
            self.sql,
        )

        self.assertIn(
            "at time zone 'utc'",
            self.sql,
        )

    def test_build_control_check_exists(self):
        self.assertIn(
            "analytics_build_control",
            self.sql,
        )

    def test_results_are_idempotent_per_build_check(self):
        self.assertIn(
            "on conflict",
            self.sql,
        )

        self.assertIn(
            "analytics_build_run_id",
            self.sql,
        )

    def test_validation_does_not_mutate_staging(self):
        for forbidden in (
            "insert into staging.",
            "update staging.",
            "delete from staging.",
            "truncate staging.",
            "drop table staging.",
        ):
            self.assertNotIn(
                forbidden,
                self.sql,
            )


if __name__ == "__main__":
    unittest.main()
