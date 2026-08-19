from __future__ import annotations

import unittest

from src.analysis.reporting_client import validate_reporting_sql
from src.app.queries import APP_QUERY_REGISTRY


class AppQueryTests(unittest.TestCase):

    def test_every_registered_query_satisfies_reporting_contract(self):
        self.assertGreater(
            len(APP_QUERY_REGISTRY),
            0,
        )

        for name, sql in APP_QUERY_REGISTRY.items():
            with self.subTest(query=name):
                self.assertEqual(
                    validate_reporting_sql(sql),
                    sql.strip(),
                )

    def test_registered_queries_reference_reporting_only(self):
        forbidden = (
            "raw.",
            "staging.",
            "validation.",
            "analytics.",
        )

        for name, sql in APP_QUERY_REGISTRY.items():
            lowered = sql.lower()

            with self.subTest(query=name):
                self.assertIn(
                    "reporting.",
                    lowered,
                )

                for token in forbidden:
                    self.assertNotIn(
                        token,
                        lowered,
                    )


if __name__ == "__main__":
    unittest.main()