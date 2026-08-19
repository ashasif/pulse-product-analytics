from __future__ import annotations

import unittest

from src.app import app


class AppSmokeTests(unittest.TestCase):

    def test_streamlit_application_exposes_main(self):
        self.assertTrue(
            callable(app.main)
        )


if __name__ == "__main__":
    unittest.main()