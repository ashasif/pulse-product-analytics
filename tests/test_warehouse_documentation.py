from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DD = ROOT / 'docs' / 'warehouse-data-dictionary.md'
CC = ROOT / 'docs' / 'reporting-consumer-contract.md'
OPS = ROOT / 'docs' / 'warehouse-operations.md'
SQL = ROOT / 'sql' / 'reporting' / '014_comment_analytics_objects.sql'

class WarehouseDocumentationTests(unittest.TestCase):
    def test_files_exist(self):
        for p in (DD, CC, OPS, SQL): self.assertTrue(p.exists())

    def test_dictionary_documents_schemas(self):
        text = DD.read_text(encoding='utf-8').lower()
        for x in ('raw','staging','validation','analytics','reporting'): self.assertIn(x, text)

    def test_dictionary_documents_semantics(self):
        text = DD.read_text(encoding='utf-8').lower()
        for x in ('successful billed payment collection','immature cohorts','descriptive only','observation cutoff','metric_definitions'): self.assertIn(x, text)

    def test_consumer_contract(self):
        text = CC.read_text(encoding='utf-8').lower()
        for x in ('pulse_reporting_reader','nologin','read-only','raw','staging','validation','analytics'): self.assertIn(x, text)

    def test_operations_and_comments(self):
        ops = OPS.read_text(encoding='utf-8').lower()
        sql = SQL.read_text(encoding='utf-8').lower()
        for x in ('009_harden_observation_cutoff.sql','010_add_reporting_performance_indexes.sql','011_optimize_feature_engagement_view.sql','012_admin_create_reporting_reader.sql','013_grant_reporting_reader.sql','014_comment_analytics_objects.sql'): self.assertIn(x, ops)
        for x in ('analytics.build_runs','analytics.dim_date','analytics.dim_installation','analytics.dim_user','analytics.dim_experiment','analytics.dim_app_release','analytics.fact_product_event','analytics.fact_subscription','analytics.fact_subscription_transaction','analytics.fact_experiment_assignment','analytics.fact_marketing_spend'): self.assertIn('comment on table ' + x, sql)

if __name__ == '__main__': unittest.main()
