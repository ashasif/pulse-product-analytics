"""Tests for Pulse Phase 4 Step 3 analysis."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.analysis.engagement_monetisation import (
    STEP3_SUPPORTED_METRICS,
    build_engagement_monetisation_snapshot,
    export_engagement_monetisation_snapshot,
    feature_highlight,
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
        "monthly_engagement": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "month_start": date(2026, 1, 1),
                "average_registered_dau": Decimal("100"),
                "peak_registered_dau": 150,
                "session_count": 1000,
                "feature_use_event_count": 4000,
                "paywall_view_count": 200,
                "trial_start_count": 50,
                "paid_subscription_start_count": 20,
            }
        ],
        "feature_engagement": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "feature_name": "ai_assistant",
                "feature_use_event_count": 3000,
                "feature_use_event_share": Decimal("0.75"),
            },
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "feature_name": "focus_sessions",
                "feature_use_event_count": 1000,
                "feature_use_event_share": Decimal("0.25"),
            },
        ],
        "revenue_summary": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "payment_attempt_count": 100,
                "successful_payment_count": 95,
                "failed_payment_count": 5,
                "payment_failure_rate": Decimal("0.05"),
                "successful_payment_revenue_gbp":
                    Decimal("2000.00"),
                "renewal_attempt_count": 50,
                "successful_renewal_count": 40,
                "failed_renewal_count": 10,
                "renewal_success_rate": Decimal("0.80"),
                "renewal_revenue_gbp": Decimal("1000.00"),
            }
        ],
        "monthly_revenue": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "month_start": date(2026, 1, 1),
                "payment_attempt_count": 100,
                "successful_payment_count": 95,
                "failed_payment_count": 5,
                "payment_failure_rate": Decimal("0.05"),
                "successful_payment_revenue_gbp":
                    Decimal("2000.00"),
                "renewal_attempt_count": 50,
                "successful_renewal_count": 40,
                "renewal_success_rate": Decimal("0.80"),
            }
        ],
        "trial_conversion_summary": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "trial_count": 100,
                "mature_trial_count": 90,
                "immature_trial_count": 10,
                "mature_trial_paid_conversion_count": 36,
                "trial_to_paid_conversion_rate":
                    Decimal("0.40"),
            }
        ],
        "retention_summary": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "paid_subscription_count": 100,
                "eligible_d30_count": 90,
                "retained_d30_count": 72,
                "paid_retention_d30": Decimal("0.80"),
                "eligible_d90_count": 80,
                "retained_d90_count": 48,
                "paid_retention_d90": Decimal("0.60"),
                "eligible_d180_count": 60,
                "retained_d180_count": 24,
                "paid_retention_d180": Decimal("0.40"),
                "eligible_d365_count": 30,
                "retained_d365_count": 6,
                "paid_retention_d365": Decimal("0.20"),
            }
        ],
        "retention_by_billing_period": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "billing_period": "monthly",
                "paid_subscription_count": 80,
                "eligible_d30_count": 70,
                "retained_d30_count": 50,
                "paid_retention_d30": Decimal("0.714286"),
                "eligible_d90_count": 60,
                "retained_d90_count": 30,
                "paid_retention_d90": Decimal("0.50"),
                "eligible_d180_count": 40,
                "retained_d180_count": 15,
                "paid_retention_d180": Decimal("0.375"),
                "eligible_d365_count": 20,
                "retained_d365_count": 3,
                "paid_retention_d365": Decimal("0.15"),
            }
        ],
        "retention_by_acquisition_channel": [
            {
                "ingestion_batch_id": 1,
                "analytics_build_run_id": 1,
                "acquisition_channel": "referral",
                "paid_subscription_count": 20,
                "eligible_d30_count": 18,
                "retained_d30_count": 15,
                "paid_retention_d30": Decimal("0.833333"),
                "eligible_d90_count": 15,
                "retained_d90_count": 10,
                "paid_retention_d90": Decimal("0.666667"),
                "eligible_d180_count": 10,
                "retained_d180_count": 5,
                "paid_retention_d180": Decimal("0.50"),
                "eligible_d365_count": 5,
                "retained_d365_count": 1,
                "paid_retention_d365": Decimal("0.20"),
            }
        ],
    }


class Step3QueryContractTests(unittest.TestCase):

    @patch(
        "src.analysis.engagement_monetisation."
        "fetch_reporting_rows"
    )
    @patch(
        "src.analysis.engagement_monetisation."
        "get_reporting_context"
    )
    @patch(
        "src.analysis.engagement_monetisation."
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
            [],
            [],
            [],
        ]

        build_engagement_monetisation_snapshot()

        require_metrics.assert_called_once()

        self.assertEqual(
            tuple(require_metrics.call_args.args[0]),
            STEP3_SUPPORTED_METRICS,
        )

    @patch(
        "src.analysis.engagement_monetisation."
        "fetch_reporting_rows"
    )
    @patch(
        "src.analysis.engagement_monetisation."
        "get_reporting_context"
    )
    @patch(
        "src.analysis.engagement_monetisation."
        "require_supported_metrics"
    )
    def test_all_step3_queries_use_reporting_only(
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
            [],
            [],
            [],
        ]

        build_engagement_monetisation_snapshot()

        self.assertEqual(
            fetch_rows.call_count,
            8,
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


class FeatureHighlightTests(unittest.TestCase):

    def test_highest_volume_feature_is_selected(self):
        result = feature_highlight(
            _sample_snapshot()["feature_engagement"]
        )

        self.assertEqual(
            result["feature_name"],
            "ai_assistant",
        )


class Step3OutputTests(unittest.TestCase):

    def test_report_preserves_revenue_terminology(self):
        report = render_findings_report(
            _sample_snapshot()
        )

        self.assertIn(
            "successful billed payment collection",
            report.lower(),
        )
        self.assertIn(
            "not accounting-recognised revenue",
            report.lower(),
        )

    def test_report_preserves_maturity_rule(self):
        report = render_findings_report(
            _sample_snapshot()
        )

        self.assertIn(
            "mature",
            report.lower(),
        )
        self.assertIn(
            "immature",
            report.lower(),
        )

    def test_report_does_not_invent_mau(self):
        report = render_findings_report(
            _sample_snapshot()
        )

        self.assertIn(
            "not monthly active users",
            report.lower(),
        )

    def test_export_creates_expected_outputs(self):
        snapshot = _sample_snapshot()

        with tempfile.TemporaryDirectory() as directory:
            paths = export_engagement_monetisation_snapshot(
                snapshot,
                directory,
            )

            expected = {
                "monthly_engagement",
                "feature_engagement",
                "revenue_summary",
                "monthly_revenue",
                "trial_conversion_summary",
                "retention_summary",
                "retention_by_billing_period",
                "retention_by_acquisition_channel",
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

    def test_manifest_preserves_reporting_lineage(self):
        snapshot = _sample_snapshot()

        with tempfile.TemporaryDirectory() as directory:
            paths = export_engagement_monetisation_snapshot(
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
