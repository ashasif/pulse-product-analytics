from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPORTING_SQL = ROOT / "sql" / "reporting"


class ReportingSemanticSqlTests(unittest.TestCase):

    def test_expected_reporting_sql_files_exist(self):
        expected = {
            "001_create_reporting_schema.sql",
            "002_create_metric_definitions.sql",
            "003_create_foundation_views.sql",
        }

        actual = {path.name for path in REPORTING_SQL.glob("*.sql")}

        self.assertTrue(expected.issubset(actual))

    def test_reporting_schema_is_created_idempotently(self):
        sql = (
            REPORTING_SQL / "001_create_reporting_schema.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn(
            "create schema if not exists reporting",
            sql,
        )

    def test_metric_definition_contract_is_idempotent(self):
        sql = (
            REPORTING_SQL / "002_create_metric_definitions.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn(
            "create table if not exists reporting.metric_definitions",
            sql,
        )
        self.assertIn("on conflict (metric_key) do update", sql)
        self.assertIn("support_status", sql)

    def test_metric_catalog_explicitly_records_unsupported_metrics(self):
        sql = (
            REPORTING_SQL / "002_create_metric_definitions.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("average_session_duration_seconds", sql)
        self.assertIn("recognized_revenue_gbp", sql)
        self.assertIn("campaign_attributed_cac_gbp", sql)
        self.assertIn("'unsupported'", sql)
        self.assertIn("'deferred'", sql)

    def test_reporting_views_depend_on_analytics_not_raw_or_staging(self):
        sql = (
            REPORTING_SQL / "003_create_foundation_views.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn("analytics.dim_installation", sql)
        self.assertIn("analytics.dim_user", sql)
        self.assertIn("analytics.fact_product_event", sql)
        self.assertIn(
            "analytics.fact_subscription_transaction",
            sql,
        )

        self.assertNotIn(" raw.", sql)
        self.assertNotIn(" staging.", sql)

    def test_installation_lifecycle_preserves_installation_grain(self):
        sql = (
            REPORTING_SQL / "003_create_foundation_views.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn(
            "reporting.vw_installation_lifecycle",
            sql,
        )
        self.assertIn(
            "group by installation_key",
            sql,
        )
        self.assertIn("has_signup", sql)
        self.assertIn("has_onboarding_completed", sql)

    def test_daily_product_kpis_use_session_started_for_registered_dau(self):
        sql = (
            REPORTING_SQL / "003_create_foundation_views.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn(
            "reporting.vw_daily_product_kpis",
            sql,
        )
        self.assertIn("event_name = 'session_started'", sql)
        self.assertIn("count(distinct user_key)", sql)
        self.assertIn("registered_dau", sql)

    def test_revenue_view_only_sums_succeeded_payment_revenue(self):
        sql = (
            REPORTING_SQL / "003_create_foundation_views.sql"
        ).read_text(encoding="utf-8").lower()

        self.assertIn(
            "reporting.vw_daily_subscription_revenue",
            sql,
        )
        self.assertIn("payment_status = 'succeeded'", sql)
        self.assertIn("successful_payment_revenue_gbp", sql)
        self.assertIn("payment_failure_rate", sql)


if __name__ == "__main__":
    unittest.main()
