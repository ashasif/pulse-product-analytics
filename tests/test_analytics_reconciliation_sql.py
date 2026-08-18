"""Contract tests for Step 5 analytics reconciliation views."""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "analytics"
    / "003_create_analytics_reconciliation_views.sql"
)


class AnalyticsReconciliationSqlTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):
        cls.sql = SQL_PATH.read_text(
            encoding="utf-8"
        ).lower()

    def test_reconciliation_views_exist(self):
        self.assertIn(
            "validation.analytics_dataset_counts",
            self.sql,
        )

        self.assertIn(
            "validation.analytics_reconciliation",
            self.sql,
        )

    def test_all_eight_source_datasets_exist(self):
        datasets = (
            "installations",
            "users",
            "product_events",
            "subscriptions",
            "subscription_transactions",
            "experiment_assignments",
            "marketing_spend",
            "app_releases",
        )

        for dataset in datasets:
            self.assertIn(
                f"'{dataset}'",
                self.sql,
            )

    def test_reconciliation_uses_staging_counts(self):
        self.assertIn(
            "validation.staging_dataset_counts",
            self.sql,
        )

    def test_reconciliation_has_delta(self):
        self.assertIn(
            "row_count_delta",
            self.sql,
        )

    def test_reconciliation_has_boolean_result(self):
        self.assertIn(
            "reconciled",
            self.sql,
        )

    def test_views_do_not_mutate_staging(self):
        forbidden = (
            "insert into staging.",
            "update staging.",
            "delete from staging.",
            "truncate staging.",
        )

        for statement in forbidden:
            self.assertNotIn(
                statement,
                self.sql,
            )


if __name__ == "__main__":
    unittest.main()
