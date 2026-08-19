from __future__ import annotations

import unittest

from src.app import app


class AppSmokeTests(unittest.TestCase):

    def test_streamlit_application_exposes_main(self):
        self.assertTrue(
            callable(app.main)
        )

    def test_business_page_registry_is_complete(self):
        self.assertEqual(
            list(app.BUSINESS_PAGE_REGISTRY),
            [
                "Executive Overview",
                "Growth & Acquisition",
                "Engagement & Monetisation",
                "Retention & Lifecycle",
            ],
        )

        for renderer in (
            app.BUSINESS_PAGE_REGISTRY.values()
        ):
            self.assertTrue(
                callable(renderer)
            )

    def test_frozen_page_registry_is_complete(self):
        self.assertEqual(
            list(app.FROZEN_PAGE_REGISTRY),
            [
                "Experiments",
                "Predictive Decision Support",
            ],
        )

        for renderer in (
            app.FROZEN_PAGE_REGISTRY.values()
        ):
            self.assertTrue(
                callable(renderer)
            )

    def test_complete_navigation_contains_six_pages(self):
        self.assertEqual(
            app.PAGE_NAMES,
            [
                "Executive Overview",
                "Growth & Acquisition",
                "Engagement & Monetisation",
                "Retention & Lifecycle",
                "Experiments",
                "Predictive Decision Support",
            ],
        )


if __name__ == "__main__":
    unittest.main()