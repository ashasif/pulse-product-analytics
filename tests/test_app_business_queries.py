from __future__ import annotations

import unittest

from src.analysis.reporting_client import validate_reporting_sql
from src.app.queries import APP_QUERY_REGISTRY


BUSINESS_QUERIES = {
    name: sql
    for name, sql in APP_QUERY_REGISTRY.items()
    if name not in {
        "reporting_context",
        "supported_metrics",
    }
}


class AppBusinessQueryTests(unittest.TestCase):

    def test_business_queries_are_reporting_only(self):
        self.assertGreaterEqual(
            len(BUSINESS_QUERIES),
            10,
        )

        for name, sql in BUSINESS_QUERIES.items():
            with self.subTest(query=name):
                validate_reporting_sql(sql)

                lowered = sql.lower()

                self.assertIn(
                    "reporting.",
                    lowered,
                )

                for forbidden in (
                    "raw.",
                    "staging.",
                    "validation.",
                    "analytics.",
                ):
                    self.assertNotIn(
                        forbidden,
                        lowered,
                    )

    def test_aggregated_rate_queries_do_not_average_rate_fields(self):
        for name in (
            "overview_funnel",
            "acquisition_channel",
            "platform_funnel",
            "monthly_revenue",
            "trial_conversion_channel",
            "retention_summary",
            "retention_channel",
        ):
            with self.subTest(query=name):
                sql = BUSINESS_QUERIES[name].lower()

                self.assertNotIn(
                    "avg(",
                    sql,
                )

    def test_trial_conversion_uses_mature_denominator(self):
        sql = BUSINESS_QUERIES[
            "trial_conversion_channel"
        ].lower()

        self.assertIn(
            "sum(mature_trial_count)",
            sql,
        )

        self.assertIn(
            "sum(mature_trial_paid_conversion_count)",
            sql,
        )

    def test_retention_uses_maturity_specific_denominators(self):
        sql = BUSINESS_QUERIES[
            "retention_summary"
        ].lower()

        for horizon in (
            "d30",
            "d90",
            "d180",
            "d365",
        ):
            with self.subTest(horizon=horizon):
                self.assertIn(
                    f"sum(mature_{horizon}_count)",
                    sql,
                )

                self.assertIn(
                    f"sum(retained_{horizon}_count)",
                    sql,
                )

    def test_revenue_query_uses_successful_payment_collection(self):
        sql = BUSINESS_QUERIES[
            "overview_revenue"
        ].lower()

        self.assertIn(
            "successful_payment_revenue_gbp",
            sql,
        )


if __name__ == "__main__":
    unittest.main()