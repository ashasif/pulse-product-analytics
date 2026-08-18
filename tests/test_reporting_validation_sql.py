from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = (
    ROOT
    / "sql"
    / "reporting"
    / "008_create_reporting_validation.sql"
)


class ReportingValidationSqlTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sql = SQL_PATH.read_text(
            encoding="utf-8"
        ).lower()

    def test_validation_sql_file_exists(self):
        self.assertTrue(SQL_PATH.exists())

    def test_reporting_validation_metadata_tables_exist(self):
        self.assertIn(
            "validation.reporting_validation_runs",
            self.sql,
        )
        self.assertIn(
            "validation.reporting_validation_results",
            self.sql,
        )

    def test_successful_validation_is_unique_per_build(self):
        self.assertIn(
            "uq_reporting_validation_successful_build",
            self.sql,
        )
        self.assertIn(
            "where status = 'succeeded'",
            self.sql,
        )

    def test_validation_function_exists(self):
        self.assertIn(
            "validation.validate_reporting_build",
            self.sql,
        )

    def test_validation_uses_transaction_advisory_lock(self):
        self.assertIn(
            "pg_advisory_xact_lock",
            self.sql,
        )

    def test_validation_requires_successful_analytics_build(self):
        self.assertIn(
            "v_build_status <> 'succeeded'",
            self.sql,
        )

    def test_expected_check_count_is_31(self):
        self.assertIn(
            "v_expected_check_count constant integer := 31",
            self.sql,
        )

    def test_metric_contract_is_persistently_validated(self):
        self.assertIn(
            "metric_definition_count",
            self.sql,
        )
        self.assertIn(
            "supported_metric_count",
            self.sql,
        )
        self.assertIn(
            "unsupported_metric_count",
            self.sql,
        )

    def test_reporting_reconciliation_checks_exist(self):
        required = (
            "product_installations_reconcile",
            "successful_payment_revenue_reconcile",
            "marketing_spend_reconcile",
            "feature_events_reconcile",
            "trial_rows_reconcile",
            "paid_retention_base_reconcile",
            "experiment_outcomes_reconcile",
        )

        for check_name in required:
            self.assertIn(check_name, self.sql)

    def test_reporting_quality_checks_exist(self):
        self.assertIn(
            "reporting_rate_bounds",
            self.sql,
        )
        self.assertIn(
            "retention_maturity_consistency",
            self.sql,
        )

    def test_successful_rerun_returns_existing_validation(self):
        self.assertIn(
            "v_existing_run_id",
            self.sql,
        )
        self.assertIn(
            "result_already_validated",
            self.sql,
        )
        self.assertIn(
            "where analytics_build_run_id =",
            self.sql,
        )

    def test_validation_uses_only_analytics_and_reporting_sources(self):
        self.assertNotIn(" from raw.", self.sql)
        self.assertNotIn(" from staging.", self.sql)


if __name__ == "__main__":
    unittest.main()