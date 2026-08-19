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
            list(app.PAGE_REGISTRY),
            [
                "Executive Overview",
                "Growth & Acquisition",
                "Engagement & Monetisation",
                "Retention & Lifecycle",
            ],
        )

        for renderer in app.PAGE_REGISTRY.values():
            self.assertTrue(
                callable(renderer)
            )


if __name__ == "__main__":
    unittest.main()