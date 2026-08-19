"""Tests for the Phase 4 reporting-only analysis client."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from src.analysis.reporting_client import (
    MetricContractError,
    ReportingContext,
    ReportingQueryError,
    get_reporting_context,
    require_supported_metrics,
    validate_reporting_sql,
)


class ReportingSqlContractTests(unittest.TestCase):

    def test_select_from_reporting_is_allowed(self):
        sql = validate_reporting_sql(
            "SELECT * FROM reporting.vw_daily_product_kpis"
        )
        self.assertIn(
            "reporting.vw_daily_product_kpis",
            sql,
        )

    def test_with_query_from_reporting_is_allowed(self):
        sql = validate_reporting_sql(
            """
            WITH x AS (
                SELECT full_date
                FROM reporting.vw_daily_product_kpis
            )
            SELECT *
            FROM x
            """
        )
        self.assertTrue(sql.lstrip().upper().startswith("WITH"))

    def test_direct_analytics_access_is_rejected(self):
        with self.assertRaises(ReportingQueryError):
            validate_reporting_sql(
                "SELECT * FROM analytics.fact_product_event"
            )

    def test_direct_raw_access_is_rejected(self):
        with self.assertRaises(ReportingQueryError):
            validate_reporting_sql(
                "SELECT * FROM raw.product_events"
            )

    def test_direct_staging_access_is_rejected(self):
        with self.assertRaises(ReportingQueryError):
            validate_reporting_sql(
                "SELECT * FROM staging.product_events"
            )

    def test_direct_validation_access_is_rejected(self):
        with self.assertRaises(ReportingQueryError):
            validate_reporting_sql(
                "SELECT * FROM validation.reporting_validation_runs"
            )

    def test_write_statement_is_rejected(self):
        with self.assertRaises(ReportingQueryError):
            validate_reporting_sql(
                "DELETE FROM reporting.metric_definitions"
            )

    def test_multiple_statements_are_rejected(self):
        with self.assertRaises(ReportingQueryError):
            validate_reporting_sql(
                (
                    "SELECT * FROM reporting.metric_definitions; "
                    "SELECT * FROM reporting.vw_observation_cutoff"
                )
            )


class MetricContractTests(unittest.TestCase):

    @patch("src.analysis.reporting_client.get_metric_contracts")
    def test_supported_metric_is_accepted(self, mocked_contracts):
        mocked_contracts.return_value = [
            {
                "metric_key": "registered_dau",
                "support_status": "supported",
            }
        ]

        result = require_supported_metrics(
            ["registered_dau"]
        )

        self.assertEqual(
            result["registered_dau"]["support_status"],
            "supported",
        )

    @patch("src.analysis.reporting_client.get_metric_contracts")
    def test_deferred_metric_is_rejected(self, mocked_contracts):
        mocked_contracts.return_value = [
            {
                "metric_key": "customer_ltv_gbp",
                "support_status": "deferred",
            }
        ]

        with self.assertRaises(MetricContractError):
            require_supported_metrics(
                ["customer_ltv_gbp"]
            )

    @patch("src.analysis.reporting_client.get_metric_contracts")
    def test_unknown_metric_is_rejected(self, mocked_contracts):
        mocked_contracts.return_value = []

        with self.assertRaises(MetricContractError):
            require_supported_metrics(
                ["invented_metric"]
            )


class ReportingContextTests(unittest.TestCase):

    @patch("src.analysis.reporting_client.fetch_reporting_rows")
    def test_context_preserves_lineage(self, mocked_fetch):
        cutoff = datetime(
            2026,
            7,
            1,
            0,
            59,
            36,
            tzinfo=timezone.utc,
        )

        mocked_fetch.return_value = [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "observation_cutoff_at": cutoff,
            }
        ]

        context = get_reporting_context()

        self.assertIsInstance(context, ReportingContext)
        self.assertEqual(context.ingestion_batch_id, 1)
        self.assertEqual(context.analytics_build_run_id, 1)
        self.assertEqual(context.observation_cutoff_at, cutoff)


if __name__ == "__main__":
    unittest.main()
