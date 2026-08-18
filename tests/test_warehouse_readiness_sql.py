from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/'sql'/'reporting'/'015_create_warehouse_readiness_validation.sql'

class WarehouseReadinessSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.sql=SQL.read_text(encoding='ascii').lower()
    def test_file_exists(self): self.assertTrue(SQL.exists())
    def test_run_table(self): self.assertIn('validation.warehouse_readiness_runs',self.sql)
    def test_result_table(self): self.assertIn('validation.warehouse_readiness_results',self.sql)
    def test_validation_function(self): self.assertIn('validation.validate_warehouse_readiness',self.sql)
    def test_expected_checks(self): self.assertIn('v_expected constant integer := 15',self.sql)
    def test_performance_contracts(self):
        for x in ('ix_fact_product_event_daily_reporting','ix_fact_product_event_feature_reporting','ix_fact_product_event_time','observation_cutoff_exact'): self.assertIn(x,self.sql)
    def test_consumer_contracts(self):
        for x in ('pulse_reporting_reader','reporting_select_complete','reporting_write_denied','internal_schema_usage_denied','internal_select_denied','default_reporting_select_present'): self.assertIn(x,self.sql)
    def test_metadata_contracts(self):
        self.assertIn('analytics_object_comments_complete',self.sql)
        self.assertIn('reporting_object_comments_complete',self.sql)
    def test_idempotent_success_index(self): self.assertIn('uq_warehouse_readiness_runs_successful_build',self.sql)
    def test_transaction_wrapped(self): self.assertIn('begin;',self.sql); self.assertIn('commit;',self.sql)

if __name__=='__main__': unittest.main()
