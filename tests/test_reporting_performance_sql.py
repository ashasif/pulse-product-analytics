from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "sql" / "reporting" / "009_harden_observation_cutoff.sql"


class ReportingPerformanceHardeningSQLTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.sql = SQL_PATH.read_text(encoding="utf-8").lower()

    def test_sql_file_exists(self):
        self.assertTrue(SQL_PATH.exists())

    def test_replaces_observation_cutoff_view(self):
        self.assertIn(
            "create or replace view reporting.vw_observation_cutoff",
            self.sql,
        )

    def test_uses_lateral_latest_event_lookup(self):
        self.assertIn("cross join lateral", self.sql)
        self.assertIn("order by e.occurred_at desc", self.sql)
        self.assertIn("limit 1", self.sql)

    def test_preserves_build_lineage_predicates(self):
        self.assertIn(
            "e.ingestion_batch_id = b.ingestion_batch_id",
            self.sql,
        )
        self.assertIn(
            "e.analytics_build_run_id = b.analytics_build_run_id",
            self.sql,
        )
        self.assertIn("b.status = 'succeeded'", self.sql)

    def test_does_not_add_speculative_index(self):
        self.assertNotIn("create index", self.sql)
        self.assertNotIn("create unique index", self.sql)

    def test_is_transaction_wrapped(self):
        self.assertIn("begin;", self.sql)
        self.assertIn("commit;", self.sql)


if __name__ == "__main__":
    unittest.main()
