"""Tests for Pulse Phase 4 portfolio evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

from src.analysis.portfolio_evidence import (
    PortfolioEvidenceError,
    build_portfolio_evidence,
    validate_phase4_lineage,
)


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


def _build_fixture(root):
    for step in (2, 3, 4):
        (root / f"step{step}").mkdir(
            parents=True,
            exist_ok=True,
        )

    common = {
        "ingestion_batch_id": 1,
        "analytics_build_run_id": 1,
        "observation_cutoff_at":
            "2026-07-01T00:59:36+01:00",
        "source_schema": "reporting",
        "synthetic_data": True,
    }

    for step in (2, 3):
        (
            root
            / f"step{step}"
            / "analysis_manifest.json"
        ).write_text(
            json.dumps(common),
            encoding="utf-8",
        )

    step4 = dict(common)
    step4["experiment_interpretation"] = (
        "descriptive_only"
    )

    (
        root
        / "step4"
        / "analysis_manifest.json"
    ).write_text(
        json.dumps(step4),
        encoding="utf-8",
    )

    _write_csv(
        root
        / "step2"
        / "acquisition_channel_performance.csv",
        [
            {
                "acquisition_channel": "referral",
                "install_to_signup_rate": "0.70",
            },
            {
                "acquisition_channel": "paid_search",
                "install_to_signup_rate": "0.60",
            },
        ],
    )

    _write_csv(
        root / "step3" / "retention_summary.csv",
        [
            {
                "paid_retention_d30": "0.73",
                "paid_retention_d90": "0.51",
                "paid_retention_d180": "0.38",
                "paid_retention_d365": "0.10",
            }
        ],
    )

    _write_csv(
        root / "step3" / "feature_engagement.csv",
        [
            {
                "feature_name": "ai_assistant",
                "feature_use_event_share": "0.60",
            },
            {
                "feature_name": "smart_tasks",
                "feature_use_event_share": "0.40",
            },
        ],
    )

    _write_csv(
        root
        / "step4"
        / "experiment_descriptive_comparisons.csv",
        [
            {
                "experiment_id": "exp_1",
                "trial_start_conversion_7d_difference_pp":
                    "1.20",
                "paid_conversion_14d_difference_pp":
                    "0.40",
            },
            {
                "experiment_id": "exp_2",
                "trial_start_conversion_7d_difference_pp":
                    "-0.80",
                "paid_conversion_14d_difference_pp":
                    "0.10",
            },
        ],
    )

    (
        root
        / "step4"
        / "business_synthesis.md"
    ).write_text(
        "# Business synthesis\n\nSynthetic findings.",
        encoding="utf-8",
    )


class Phase4LineageTests(unittest.TestCase):

    def test_matching_lineage_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _build_fixture(root)

            result = validate_phase4_lineage(root)

            self.assertEqual(
                result["analytics_build_run_id"],
                1,
            )

    def test_mismatched_build_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _build_fixture(root)

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
                PortfolioEvidenceError
            ):
                validate_phase4_lineage(root)

    def test_non_reporting_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _build_fixture(root)

            path = (
                root
                / "step2"
                / "analysis_manifest.json"
            )

            manifest = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )

            manifest["source_schema"] = "analytics"

            path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )

            with self.assertRaises(
                PortfolioEvidenceError
            ):
                validate_phase4_lineage(root)


class PortfolioGenerationTests(unittest.TestCase):

    def test_portfolio_outputs_are_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "phase4"
            output = Path(directory) / "portfolio"

            _build_fixture(root)

            paths = build_portfolio_evidence(
                root,
                output,
            )

            self.assertEqual(
                len(paths),
                6,
            )

            for path in paths.values():
                self.assertTrue(
                    path.exists()
                )

    def test_charts_are_valid_svg_documents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "phase4"
            output = Path(directory) / "portfolio"

            _build_fixture(root)

            paths = build_portfolio_evidence(
                root,
                output,
            )

            for key in (
                "acquisition_chart",
                "retention_chart",
                "feature_chart",
                "experiment_chart",
            ):
                text = paths[key].read_text(
                    encoding="utf-8"
                )

                self.assertTrue(
                    text.startswith("<svg")
                )

                self.assertIn(
                    "</svg>",
                    text,
                )

    def test_manifest_preserves_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "phase4"
            output = Path(directory) / "portfolio"

            _build_fixture(root)

            paths = build_portfolio_evidence(
                root,
                output,
            )

            manifest = json.loads(
                paths["manifest"].read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                manifest["source_schema"],
                "reporting",
            )

            self.assertEqual(
                manifest["analytics_build_run_id"],
                1,
            )

            self.assertEqual(
                manifest["experiment_interpretation"],
                "descriptive_only",
            )

            self.assertTrue(
                manifest["synthetic_data"]
            )

    def test_summary_mentions_synthetic_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "phase4"
            output = Path(directory) / "portfolio"

            _build_fixture(root)

            paths = build_portfolio_evidence(
                root,
                output,
            )

            text = paths["summary"].read_text(
                encoding="utf-8"
            ).lower()

            self.assertIn(
                "synthetic",
                text,
            )


if __name__ == "__main__":
    unittest.main()
