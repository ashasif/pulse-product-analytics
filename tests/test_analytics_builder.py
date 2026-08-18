"""Contract tests for the Step 5 PostgreSQL analytics builder."""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]

SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "analytics"
    / "004_create_analytics_builder.sql"
)

PYTHON_PATH = (
    PROJECT_ROOT
    / "src"
    / "ingestion"
    / "analytics_builder.py"
)


class AnalyticsBuilderSqlTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):
        cls.sql = SQL_PATH.read_text(
            encoding="utf-8"
        ).lower()

    def test_database_builder_function_exists(self):
        self.assertIn(
            "analytics.build_promoted_batch",
            self.sql,
        )

    def test_builder_uses_advisory_lock(self):
        self.assertIn(
            "pg_advisory_xact_lock",
            self.sql,
        )

        self.assertIn(
            "pulse-analytics-build:",
            self.sql,
        )

    def test_builder_requires_successful_upstream_chain(self):
        self.assertIn(
            "raw.ingestion_batches",
            self.sql,
        )

        self.assertIn(
            "validation.validation_runs",
            self.sql,
        )

        self.assertIn(
            "staging.promotion_runs",
            self.sql,
        )

    def test_builder_requires_staging_reconciliation(self):
        self.assertIn(
            "validation.staging_reconciliation",
            self.sql,
        )

    def test_builder_reconciles_analytics(self):
        self.assertIn(
            "validation.analytics_reconciliation",
            self.sql,
        )

    def test_builder_has_all_core_loads(self):
        targets = (
            "analytics.dim_date",
            "analytics.dim_installation",
            "analytics.dim_user",
            "analytics.dim_experiment",
            "analytics.dim_app_release",
            "analytics.fact_product_event",
            "analytics.fact_subscription",
            "analytics.fact_subscription_transaction",
            "analytics.fact_experiment_assignment",
            "analytics.fact_marketing_spend",
        )

        for target in targets:
            self.assertIn(
                f"insert into {target}",
                self.sql,
            )

    def test_builder_uses_utc_date_keys(self):
        self.assertIn(
            "at time zone 'utc'",
            self.sql,
        )

    def test_builder_preserves_build_lineage(self):
        self.assertIn(
            "analytics_build_run_id",
            self.sql,
        )

        self.assertIn(
            "source_row_number",
            self.sql,
        )

        self.assertIn(
            "row_hash",
            self.sql,
        )

    def test_builder_has_idempotent_success_path(self):
        self.assertIn(
            "status = 'succeeded'",
            self.sql,
        )

        self.assertIn(
            "result_already_built",
            self.sql,
        )

    def test_failed_build_is_audited(self):
        self.assertIn(
            "exception",
            self.sql,
        )

        self.assertIn(
            "when others",
            self.sql,
        )

        self.assertIn(
            "status = 'failed'",
            self.sql,
        )

    def test_builder_does_not_mutate_staging(self):
        forbidden = (
            "insert into staging.",
            "update staging.",
            "delete from staging.",
            "truncate staging.",
            "drop table staging.",
        )

        for statement in forbidden:
            self.assertNotIn(
                statement,
                self.sql,
            )


class AnalyticsBuilderPythonTests(
    unittest.TestCase
):

    @classmethod
    def setUpClass(cls):
        cls.source = PYTHON_PATH.read_text(
            encoding="utf-8"
        ).lower()

    def test_python_builder_reuses_database_contract(self):
        self.assertIn(
            "from src.ingestion.database import connect_database",
            self.source,
        )

    def test_python_builder_calls_database_function(self):
        self.assertIn(
            "analytics.build_promoted_batch(%s)",
            self.source,
        )

    def test_python_builder_reads_reconciliation(self):
        self.assertIn(
            "validation.analytics_reconciliation",
            self.source,
        )

    def test_cli_requires_batch_id(self):
        self.assertIn(
            '"--batch-id"',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
