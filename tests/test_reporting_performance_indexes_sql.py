from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]

INDEX_SQL = (
    ROOT
    / "sql"
    / "reporting"
    / "010_add_reporting_performance_indexes.sql"
)

FEATURE_SQL = (
    ROOT
    / "sql"
    / "reporting"
    / "011_optimize_feature_engagement_view.sql"
)


class ReportingPerformanceIndexSQLTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.index_sql = INDEX_SQL.read_text(
            encoding="utf-8"
        ).lower()

        cls.feature_sql = FEATURE_SQL.read_text(
            encoding="utf-8"
        ).lower()

    def test_performance_sql_files_exist(self):
        self.assertTrue(INDEX_SQL.exists())
        self.assertTrue(FEATURE_SQL.exists())

    def test_daily_reporting_index_is_idempotent(self):
        self.assertIn(
            "create index if not exists "
            "ix_fact_product_event_daily_reporting",
            self.index_sql,
        )

    def test_daily_reporting_index_is_covering(self):
        self.assertIn(
            "occurred_date_key",
            self.index_sql,
        )
        self.assertIn(
            "user_key",
            self.index_sql,
        )
        self.assertIn(
            "include",
            self.index_sql,
        )
        self.assertIn(
            "event_name",
            self.index_sql,
        )
        self.assertIn(
            "installation_key",
            self.index_sql,
        )

    def test_feature_reporting_index_is_partial(self):
        self.assertIn(
            "create index if not exists "
            "ix_fact_product_event_feature_reporting",
            self.index_sql,
        )
        self.assertIn(
            "where event_name = 'feature_used'",
            self.index_sql,
        )
        self.assertIn(
            "feature_name is not null",
            self.index_sql,
        )

    def test_feature_reporting_index_covers_distinct_keys(self):
        self.assertIn(
            "installation_key",
            self.index_sql,
        )
        self.assertIn(
            "user_key",
            self.index_sql,
        )
        self.assertIn(
            "session_id",
            self.index_sql,
        )

    def test_feature_view_is_replaced(self):
        self.assertIn(
            "create or replace view "
            "reporting.vw_daily_feature_engagement",
            self.feature_sql,
        )

    def test_feature_view_aggregates_before_date_join(self):
        aggregate_position = self.feature_sql.index(
            "group by"
        )

        join_position = self.feature_sql.index(
            "join analytics.dim_date"
        )

        self.assertLess(
            aggregate_position,
            join_position,
        )

    def test_feature_view_preserves_filter_contract(self):
        self.assertIn(
            "e.event_name = 'feature_used'",
            self.feature_sql,
        )
        self.assertIn(
            "e.feature_name is not null",
            self.feature_sql,
        )

    def test_both_files_are_transaction_wrapped(self):
        for sql in (
            self.index_sql,
            self.feature_sql,
        ):
            self.assertIn("begin;", sql)
            self.assertIn("commit;", sql)


if __name__ == "__main__":
    unittest.main()