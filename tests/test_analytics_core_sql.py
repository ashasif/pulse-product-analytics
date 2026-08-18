"""SQL contract tests for the Pulse Step 5 analytics core model."""

from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = (
    PROJECT_ROOT
    / "sql"
    / "analytics"
    / "002_create_core_model.sql"
)


EXPECTED_TABLES = {
    "dim_date",
    "dim_installation",
    "dim_user",
    "dim_experiment",
    "dim_app_release",
    "fact_product_event",
    "fact_subscription",
    "fact_subscription_transaction",
    "fact_experiment_assignment",
    "fact_marketing_spend",
}


class AnalyticsCoreModelSqlTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sql = SQL_PATH.read_text(encoding="utf-8").lower()

    def test_sql_file_exists(self):
        self.assertTrue(SQL_PATH.is_file())

    def test_exact_core_tables_exist(self):
        declared = set(
            re.findall(
                r"create table if not exists analytics\.([a-z_]+)",
                self.sql,
            )
        )
        self.assertEqual(declared, EXPECTED_TABLES)

    def test_surrogate_keys_exist(self):
        for key in (
            "installation_key",
            "user_key",
            "experiment_key",
            "app_release_key",
            "product_event_key",
            "subscription_key",
            "subscription_transaction_key",
            "experiment_assignment_key",
            "marketing_spend_key",
        ):
            self.assertRegex(
                self.sql,
                rf"{key}\s+bigint\s+generated always as identity",
            )

    def test_natural_business_keys_remain_snapshot_aware(self):
        for identifier in (
            "installation_id",
            "user_id",
            "experiment_id",
            "app_release_id",
            "event_id",
            "subscription_id",
            "transaction_id",
            "assignment_id",
            "marketing_spend_id",
        ):
            self.assertRegex(
                self.sql,
                re.compile(
                    rf"unique\s*\(\s*ingestion_batch_id\s*,\s*{identifier}\s*\)",
                    re.DOTALL,
                ),
            )

    def test_users_reference_installations(self):
        self.assertIn(
            "references analytics.dim_installation",
            self.sql,
        )

    def test_product_events_reference_users_and_installations(self):
        self.assertIn(
            "fact_product_event_user_fk",
            self.sql,
        )
        self.assertIn(
            "fact_product_event_installation_fk",
            self.sql,
        )

    def test_transactions_reference_subscription(self):
        self.assertIn(
            "references analytics.fact_subscription",
            self.sql,
        )

    def test_experiment_assignments_reference_experiment(self):
        self.assertIn(
            "references analytics.dim_experiment",
            self.sql,
        )

    def test_facts_use_date_dimension(self):
        for token in (
            "fact_product_event_date_fk",
            "fact_subscription_trial_date_fk",
            "fact_subscription_transaction_date_fk",
            "fact_experiment_assignment_date_fk",
            "fact_marketing_spend_start_date_fk",
        ):
            self.assertIn(token, self.sql)

    def test_source_lineage_is_preserved(self):
        for token in (
            "source_row_number",
            "row_hash",
            "validation_run_id",
            "analytics_build_run_id",
        ):
            self.assertIn(token, self.sql)

    def test_core_ddl_does_not_mutate_staging(self):
        forbidden = (
            "insert into staging.",
            "update staging.",
            "delete from staging.",
            "truncate staging.",
            "drop table staging.",
        )
        for statement in forbidden:
            self.assertNotIn(statement, self.sql)

    def test_model_has_transaction_boundary(self):
        self.assertIn("begin;", self.sql)
        self.assertIn("commit;", self.sql)


if __name__ == "__main__":
    unittest.main()
