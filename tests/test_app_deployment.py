from __future__ import annotations

import unittest
from datetime import datetime, timezone
from pathlib import Path

from src.app import app
from src.app.components import (
    format_observation_cutoff,
)


ROOT = Path(__file__).resolve().parents[1]


class AppDeploymentTests(unittest.TestCase):

    def test_streamlit_secrets_file_is_gitignored(self):
        gitignore = (
            ROOT / ".gitignore"
        ).read_text(encoding="utf-8-sig")

        self.assertIn(
            ".streamlit/secrets.toml",
            gitignore,
        )

    def test_streamlit_config_exists(self):
        self.assertTrue(
            (
                ROOT
                / ".streamlit"
                / "config.toml"
            ).is_file()
        )

    def test_methodology_page_is_registered(self):
        self.assertEqual(
            list(
                app.METHODOLOGY_PAGE_REGISTRY
            ),
            ["Methodology & Contracts"],
        )

    def test_complete_navigation_contains_seven_pages(self):
        self.assertEqual(
            app.PAGE_NAMES,
            [
                "Executive Overview",
                "Growth & Acquisition",
                "Engagement & Monetisation",
                "Retention & Lifecycle",
                "Experiments",
                "Predictive Decision Support",
                "Methodology & Contracts",
            ],
        )

    def test_cloud_utc_cutoff_renders_as_london_business_time(self):
        cutoff = datetime(
            2026,
            6,
            30,
            23,
            59,
            36,
            tzinfo=timezone.utc,
        )

        self.assertEqual(
            format_observation_cutoff(
                cutoff
            ),
            "2026-07-01 00:59:36 BST",
        )

    def test_deployment_documentation_exists(self):
        self.assertTrue(
            (
                ROOT
                / "docs"
                / "dashboard-user-guide.md"
            ).is_file()
        )

        self.assertTrue(
            (
                ROOT
                / "docs"
                / "deployment-readiness.md"
            ).is_file()
        )


if __name__ == "__main__":
    unittest.main()