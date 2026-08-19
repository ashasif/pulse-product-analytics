from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd

from src.analysis.reporting_client import ReportingContext
from src.app.data_access import (
    fetch_reporting_dataframe,
    load_reporting_context,
    load_supported_metric_definitions,
)


class AppDataAccessTests(unittest.TestCase):

    @patch("src.app.data_access.fetch_reporting_rows")
    def test_fetch_reporting_dataframe_returns_dataframe(self, mocked_fetch):
        mocked_fetch.return_value = [
            {"metric": "installations", "value": 100000}
        ]

        frame = fetch_reporting_dataframe(
            "SELECT * FROM reporting.metric_definitions"
        )

        self.assertIsInstance(frame, pd.DataFrame)
        self.assertEqual(len(frame), 1)
        self.assertEqual(
            frame.iloc[0]["metric"],
            "installations",
        )

    @patch("src.app.data_access.get_reporting_context")
    def test_load_reporting_context_preserves_lineage(self, mocked_context):
        cutoff = datetime(
            2026,
            7,
            1,
            0,
            59,
            36,
            tzinfo=timezone.utc,
        )

        mocked_context.return_value = ReportingContext(
            ingestion_batch_id=1,
            analytics_build_run_id=1,
            observation_cutoff_at=cutoff,
        )

        result = load_reporting_context()

        self.assertEqual(result["ingestion_batch_id"], 1)
        self.assertEqual(result["analytics_build_run_id"], 1)
        self.assertEqual(
            result["observation_cutoff_at"],
            cutoff,
        )

    @patch("src.app.data_access.get_metric_contracts")
    def test_load_supported_metrics_excludes_non_supported(self, mocked_metrics):
        mocked_metrics.return_value = [
            {
                "metric_key": "installation_count",
                "support_status": "supported",
            },
            {
                "metric_key": "customer_ltv_gbp",
                "support_status": "deferred",
            },
        ]

        frame = load_supported_metric_definitions()

        self.assertEqual(
            list(frame["metric_key"]),
            ["installation_count"],
        )


if __name__ == "__main__":
    unittest.main()