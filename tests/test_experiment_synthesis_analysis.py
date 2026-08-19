"""Tests for Pulse Phase 4 Step 4 analysis."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.analysis.experiment_synthesis import (
    PriorAnalysisContractError,
    STEP4_SUPPORTED_METRICS,
    build_descriptive_comparisons,
    build_experiment_snapshot,
    export_experiment_synthesis,
    load_prior_business_context,
    render_experiment_findings,
)
from src.analysis.reporting_client import ReportingContext


def _context():
    return ReportingContext(
        ingestion_batch_id=1,
        analytics_build_run_id=1,
        observation_cutoff_at=datetime(
            2026,
            7,
            1,
            tzinfo=timezone.utc,
        ),
    )


def _variant(
    variant,
    paid,
    revenue,
):
    return {
        "ingestion_batch_id": 1,
        "analytics_build_run_id": 1,
        "experiment_key": 1,
        "experiment_id": "exp_1",
        "experiment_name": "Test Experiment",
        "primary_metric": "trial_start_conversion_7d",
        "secondary_metric": "overall_feature_use_7d",
        "commercial_metric": "paid_conversion_14d",
        "guardrail_metric": "cancellation_or_expiry_30d",
        "analysis_window_days": 30,
        "variant": variant,
        "assigned_user_count": 1000,
        "exposed_user_count": 950,
        "exposure_rate": Decimal("0.95"),
        "onboarding_completed_48h_count": 700,
        "onboarding_completion_48h_rate":
            Decimal("0.70"),
        "feature_used_7d_count": 800,
        "overall_feature_use_7d_rate":
            Decimal("0.80"),
        "trial_started_7d_count": 300,
        "trial_start_conversion_7d":
            Decimal("0.30"),
        "paid_started_14d_count": int(
            paid * 1000
        ),
        "paid_conversion_14d":
            Decimal(str(paid)),
        "successful_revenue_gbp_30d":
            Decimal(str(revenue * 1000)),
        "revenue_per_assigned_user_30d":
            Decimal(str(revenue)),
        "cancellation_or_expiry_30d_count": 100,
        "cancellation_or_expiry_30d_rate":
            Decimal("0.10"),
    }


def _sample_snapshot():
    variants = [
        _variant(
            "control",
            0.10,
            2.00,
        ),
        _variant(
            "treatment",
            0.12,
            2.30,
        ),
    ]

    maturity = [
        {
            "ingestion_batch_id": 1,
            "analytics_build_run_id": 1,
            "experiment_key": 1,
            "experiment_id": "exp_1",
            "experiment_name": "Test Experiment",
            "variant": "control",
            "assigned_user_count": 1000,
            "exposed_user_count": 950,
            "mature_analysis_window_count": 1000,
            "mature_analysis_window_rate":
                Decimal("1.0"),
        },
        {
            "ingestion_batch_id": 1,
            "analytics_build_run_id": 1,
            "experiment_key": 1,
            "experiment_id": "exp_1",
            "experiment_name": "Test Experiment",
            "variant": "treatment",
            "assigned_user_count": 1000,
            "exposed_user_count": 950,
            "mature_analysis_window_count": 1000,
            "mature_analysis_window_rate":
                Decimal("1.0"),
        },
    ]

    return {
        "context": _context(),
        "experiment_variant_summary": variants,
        "experiment_maturity_summary": maturity,
        "experiment_descriptive_comparisons":
            build_descriptive_comparisons(
                variants
            ),
    }


def _write_csv(path, rows):
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0].keys()),
        )
        writer.writeheader()
        writer.writerows(rows)


def _create_prior_outputs(root):
    step2 = root / "step2"
    step3 = root / "step3"

    step2.mkdir(
        parents=True,
        exist_ok=True,
    )
    step3.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest = {
        "ingestion_batch_id": 1,
        "analytics_build_run_id": 1,
        "observation_cutoff_at":
            _context().observation_cutoff_at.isoformat(),
        "source_schema": "reporting",
        "synthetic_data": True,
    }

    (step2 / "analysis_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    (step3 / "analysis_manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )

    _write_csv(
        step2 / "funnel_summary.csv",
        [
            {
                "installation_count": 1000,
                "install_to_signup_rate": 0.60,
            }
        ],
    )

    _write_csv(
        step2 / "acquisition_channel_performance.csv",
        [
            {
                "acquisition_channel": "referral",
                "install_to_signup_rate": 0.70,
                "cost_per_install_gbp": 1.00,
            },
            {
                "acquisition_channel": "paid_search",
                "install_to_signup_rate": 0.60,
                "cost_per_install_gbp": 3.00,
            },
        ],
    )

    _write_csv(
        step3 / "revenue_summary.csv",
        [
            {
                "payment_failure_rate": 0.05,
                "renewal_success_rate": 0.90,
                "successful_payment_revenue_gbp": 1000.00,
            }
        ],
    )

    _write_csv(
        step3 / "trial_conversion_summary.csv",
        [
            {
                "trial_to_paid_conversion_rate": 0.40,
            }
        ],
    )

    _write_csv(
        step3 / "retention_summary.csv",
        [
            {
                "eligible_d30_count": 90,
                "paid_retention_d30": 0.80,
                "eligible_d90_count": 80,
                "paid_retention_d90": 0.60,
                "eligible_d180_count": 60,
                "paid_retention_d180": 0.40,
                "eligible_d365_count": 30,
                "paid_retention_d365": 0.20,
            }
        ],
    )

    _write_csv(
        step3 / "feature_engagement.csv",
        [
            {
                "feature_name": "ai_assistant",
                "feature_use_event_count": 700,
                "feature_use_event_share": 0.70,
            },
            {
                "feature_name": "smart_tasks",
                "feature_use_event_count": 300,
                "feature_use_event_share": 0.30,
            },
        ],
    )

    _write_csv(
        step3
        / "retention_by_acquisition_channel.csv",
        [
            {
                "acquisition_channel": "referral",
                "paid_retention_d365": 0.25,
            },
            {
                "acquisition_channel": "paid_search",
                "paid_retention_d365": 0.15,
            },
        ],
    )


class Step4QueryContractTests(unittest.TestCase):

    @patch(
        "src.analysis.experiment_synthesis."
        "fetch_reporting_rows"
    )
    @patch(
        "src.analysis.experiment_synthesis."
        "get_reporting_context"
    )
    @patch(
        "src.analysis.experiment_synthesis."
        "require_supported_metrics"
    )
    def test_snapshot_enforces_metric_gate(
        self,
        require_metrics,
        context,
        fetch_rows,
    ):
        context.return_value = _context()
        fetch_rows.side_effect = [
            [],
            [],
        ]

        build_experiment_snapshot()

        require_metrics.assert_called_once()

        self.assertEqual(
            tuple(require_metrics.call_args.args[0]),
            STEP4_SUPPORTED_METRICS,
        )

    @patch(
        "src.analysis.experiment_synthesis."
        "fetch_reporting_rows"
    )
    @patch(
        "src.analysis.experiment_synthesis."
        "get_reporting_context"
    )
    @patch(
        "src.analysis.experiment_synthesis."
        "require_supported_metrics"
    )
    def test_step4_queries_use_reporting_only(
        self,
        require_metrics,
        context,
        fetch_rows,
    ):
        context.return_value = _context()
        fetch_rows.side_effect = [
            [],
            [],
        ]

        build_experiment_snapshot()

        self.assertEqual(
            fetch_rows.call_count,
            2,
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


class DescriptiveComparisonTests(unittest.TestCase):

    def test_control_is_used_as_reference(self):
        result = build_descriptive_comparisons(
            _sample_snapshot()[
                "experiment_variant_summary"
            ]
        )

        self.assertEqual(
            result[0]["reference_variant"],
            "control",
        )
        self.assertEqual(
            result[0]["comparison_variant"],
            "treatment",
        )

    def test_paid_conversion_difference_is_percentage_points(self):
        result = build_descriptive_comparisons(
            _sample_snapshot()[
                "experiment_variant_summary"
            ]
        )

        self.assertAlmostEqual(
            result[0][
                "paid_conversion_14d_difference_pp"
            ],
            2.0,
        )

    def test_comparison_is_labelled_descriptive_only(self):
        result = build_descriptive_comparisons(
            _sample_snapshot()[
                "experiment_variant_summary"
            ]
        )

        self.assertEqual(
            result[0]["interpretation"],
            "descriptive_only",
        )


class ExperimentReportTests(unittest.TestCase):

    def test_report_explicitly_rejects_causal_claims(self):
        report = render_experiment_findings(
            _sample_snapshot()
        ).lower()

        self.assertIn(
            "descriptive difference",
            report,
        )
        self.assertIn(
            "does **not** provide",
            report,
        )
        self.assertIn(
            "p-values",
            report,
        )
        self.assertIn(
            "causal lift",
            report,
        )


class PriorOutputContractTests(unittest.TestCase):

    def test_matching_prior_lineage_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            _create_prior_outputs(root)

            result = load_prior_business_context(
                root,
                _context(),
            )

            self.assertIn(
                "funnel_summary",
                result,
            )

    def test_mismatched_prior_build_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            _create_prior_outputs(root)

            path = (
                root
                / "step3"
                / "analysis_manifest.json"
            )

            manifest = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            manifest[
                "analytics_build_run_id"
            ] = 999

            path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            with self.assertRaises(
                PriorAnalysisContractError
            ):
                load_prior_business_context(
                    root,
                    _context(),
                )


class Step4OutputTests(unittest.TestCase):

    def test_export_creates_expected_outputs(self):
        snapshot = _sample_snapshot()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prior_root = root / "prior"

            _create_prior_outputs(prior_root)

            prior = load_prior_business_context(
                prior_root,
                _context(),
            )

            output = root / "output"

            paths = export_experiment_synthesis(
                snapshot,
                prior,
                output,
            )

            expected = {
                "experiment_variant_summary",
                "experiment_maturity_summary",
                "experiment_descriptive_comparisons",
                "experiment_findings",
                "business_synthesis",
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

    def test_manifest_preserves_descriptive_contract(self):
        snapshot = _sample_snapshot()

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prior_root = root / "prior"

            _create_prior_outputs(prior_root)

            prior = load_prior_business_context(
                prior_root,
                _context(),
            )

            paths = export_experiment_synthesis(
                snapshot,
                prior,
                root / "output",
            )

            manifest = json.loads(
                Path(paths["manifest"]).read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest[
                    "experiment_interpretation"
                ],
                "descriptive_only",
            )

            self.assertEqual(
                manifest["source_schema"],
                "reporting",
            )

            self.assertEqual(
                manifest[
                    "analytics_build_run_id"
                ],
                1,
            )


if __name__ == "__main__":
    unittest.main()
