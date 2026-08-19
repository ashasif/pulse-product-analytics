"""Tests for Pulse Phase 4 Step 2 analysis."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.analysis.growth_acquisition import (
    STEP2_SUPPORTED_METRICS,
    build_growth_acquisition_snapshot,
    channel_highlights,
    compare_periods,
    export_growth_acquisition_snapshot,
    render_findings_report,
)
from src.analysis.reporting_client import ReportingContext


def _sample_snapshot():
    context = ReportingContext(
        ingestion_batch_id=1,
        analytics_build_run_id=1,
        observation_cutoff_at=datetime(
            2026,
            7,
            1,
            tzinfo=timezone.utc,
        ),
    )

    return {
        "context": context,
        "monthly_growth": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "month_start": date(2024, 1, 1),
                "installation_count": 100,
                "signup_count": 60,
                "paywall_view_count": 20,
                "trial_start_count": 10,
                "paid_subscription_start_count": 4,
            },
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "month_start": date(2026, 1, 1),
                "installation_count": 200,
                "signup_count": 130,
                "paywall_view_count": 40,
                "trial_start_count": 25,
                "paid_subscription_start_count": 10,
            },
        ],
        "funnel_summary": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "installation_count": 300,
                "installations_with_signup": 190,
                "install_to_signup_rate":
                    Decimal("0.633333"),
                "registered_user_count": 190,
                "onboarding_started_user_count": 170,
                "onboarding_completed_user_count": 140,
                "onboarding_start_rate":
                    Decimal("0.894737"),
                "onboarding_completion_rate":
                    Decimal("0.736842"),
            }
        ],
        "acquisition_channel_performance": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "acquisition_channel": "paid_search",
                "marketing_period_count": 10,
                "marketing_spend_gbp":
                    Decimal("1000.00"),
                "impressions": 50000,
                "clicks": 1000,
                "installation_count": 400,
                "installations_with_signup": 240,
                "click_through_rate":
                    Decimal("0.02"),
                "cost_per_click_gbp":
                    Decimal("1.00"),
                "cost_per_install_gbp":
                    Decimal("2.50"),
                "install_to_signup_rate":
                    Decimal("0.60"),
            },
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "acquisition_channel": "referral",
                "marketing_period_count": 10,
                "marketing_spend_gbp":
                    Decimal("200.00"),
                "impressions": 10000,
                "clicks": 250,
                "installation_count": 250,
                "installations_with_signup": 180,
                "click_through_rate":
                    Decimal("0.025"),
                "cost_per_click_gbp":
                    Decimal("0.80"),
                "cost_per_install_gbp":
                    Decimal("0.80"),
                "install_to_signup_rate":
                    Decimal("0.72"),
            },
        ],
        "platform_funnel_performance": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "platform": "ios",
                "installation_count": 150,
                "installations_with_signup": 100,
                "install_to_signup_rate":
                    Decimal("0.666667"),
            }
        ],
        "country_funnel_performance": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "country_code": "GB",
                "installation_count": 150,
                "installations_with_signup": 100,
                "install_to_signup_rate":
                    Decimal("0.666667"),
            }
        ],
    }


class Step2QueryContractTests(unittest.TestCase):

    @patch(
        "src.analysis.growth_acquisition."
        "fetch_reporting_rows"
    )
    @patch(
        "src.analysis.growth_acquisition."
        "get_reporting_context"
    )
    @patch(
        "src.analysis.growth_acquisition."
        "require_supported_metrics"
    )
    def test_snapshot_enforces_metric_gate(
        self,
        require_metrics,
        context,
        fetch_rows,
    ):
        context.return_value = _sample_snapshot()["context"]
        fetch_rows.side_effect = [
            [],
            [],
            [],
            [],
            [],
        ]

        build_growth_acquisition_snapshot()

        require_metrics.assert_called_once()
        requested = require_metrics.call_args.args[0]

        self.assertEqual(
            tuple(requested),
            STEP2_SUPPORTED_METRICS,
        )

    @patch(
        "src.analysis.growth_acquisition."
        "fetch_reporting_rows"
    )
    @patch(
        "src.analysis.growth_acquisition."
        "get_reporting_context"
    )
    @patch(
        "src.analysis.growth_acquisition."
        "require_supported_metrics"
    )
    def test_all_step2_queries_use_reporting_schema(
        self,
        require_metrics,
        context,
        fetch_rows,
    ):
        context.return_value = _sample_snapshot()["context"]
        fetch_rows.side_effect = [
            [],
            [],
            [],
            [],
            [],
        ]

        build_growth_acquisition_snapshot()

        self.assertEqual(
            fetch_rows.call_count,
            5,
        )

        for call in fetch_rows.call_args_list:
            sql = call.args[0].lower()

            self.assertIn(
                "reporting.",
                sql,
            )

            for forbidden in (
                "raw.",
                "staging.",
                "validation.",
                "analytics.",
            ):
                self.assertNotIn(
                    forbidden,
                    sql,
                )


class PeriodComparisonTests(unittest.TestCase):

    def test_aligned_period_growth_is_calculated(self):
        result = compare_periods(
            _sample_snapshot()["monthly_growth"]
        )

        self.assertEqual(
            result["baseline"]["installation_count"],
            100,
        )
        self.assertEqual(
            result["comparison"]["installation_count"],
            200,
        )
        self.assertAlmostEqual(
            result["percent_change"]["installation_count"],
            100.0,
        )

    def test_zero_baseline_returns_no_percent_change(self):
        rows = _sample_snapshot()["monthly_growth"]
        rows[0]["installation_count"] = 0

        result = compare_periods(rows)

        self.assertIsNone(
            result["percent_change"]["installation_count"]
        )


class ChannelHighlightTests(unittest.TestCase):

    def test_channel_leaders_use_canonical_measures(self):
        result = channel_highlights(
            _sample_snapshot()[
                "acquisition_channel_performance"
            ]
        )

        self.assertEqual(
            result[
                "highest_install_volume"
            ]["acquisition_channel"],
            "paid_search",
        )
        self.assertEqual(
            result[
                "highest_signup_conversion"
            ]["acquisition_channel"],
            "referral",
        )
        self.assertEqual(
            result[
                "lowest_cost_per_install"
            ]["acquisition_channel"],
            "referral",
        )
        self.assertEqual(
            result[
                "highest_marketing_spend"
            ]["acquisition_channel"],
            "paid_search",
        )


class Step2OutputTests(unittest.TestCase):

    def test_findings_report_identifies_synthetic_data(self):
        report = render_findings_report(
            _sample_snapshot()
        )

        self.assertIn(
            "synthetic",
            report.lower(),
        )
        self.assertIn(
            "reporting.*",
            report,
        )

    def test_export_creates_expected_files(self):
        snapshot = _sample_snapshot()

        with tempfile.TemporaryDirectory() as directory:
            paths = export_growth_acquisition_snapshot(
                snapshot,
                directory,
            )

            expected = {
                "monthly_growth",
                "funnel_summary",
                "acquisition_channel_performance",
                "platform_funnel_performance",
                "country_funnel_performance",
                "findings",
                "manifest",
            }

            self.assertEqual(
                set(paths),
                expected,
            )

            for path in paths.values():
                self.assertTrue(
                    Path(path).exists()
                )

    def test_manifest_preserves_lineage(self):
        snapshot = _sample_snapshot()

        with tempfile.TemporaryDirectory() as directory:
            paths = export_growth_acquisition_snapshot(
                snapshot,
                directory,
            )

            manifest = json.loads(
                Path(paths["manifest"]).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["ingestion_batch_id"],
                1,
            )
            self.assertEqual(
                manifest["analytics_build_run_id"],
                1,
            )
            self.assertEqual(
                manifest["source_schema"],
                "reporting",
            )
            self.assertTrue(
                manifest["synthetic_data"]
            )


if __name__ == "__main__":
    unittest.main()
