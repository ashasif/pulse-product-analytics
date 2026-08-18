from __future__ import annotations

import re
import unittest

from src.ingestion.staging_promoter import (
    PROMOTION_ORDER,
    build_insert_statement,
    business_columns,
)


class StagingPromotionContractTests(
    unittest.TestCase
):

    def test_exactly_eight_datasets_are_promoted(self):
        self.assertEqual(
            len(PROMOTION_ORDER),
            8,
        )

    def test_installations_are_promoted_first(self):
        self.assertEqual(
            PROMOTION_ORDER[0],
            "installations",
        )

    def test_users_are_promoted_before_dependants(self):
        users_position = (
            PROMOTION_ORDER.index("users")
        )

        for dependent in (
            "product_events",
            "subscriptions",
            "subscription_transactions",
            "experiment_assignments",
        ):
            self.assertLess(
                users_position,
                PROMOTION_ORDER.index(
                    dependent
                ),
            )

    def test_subscriptions_precede_transactions(self):
        self.assertLess(
            PROMOTION_ORDER.index(
                "subscriptions"
            ),
            PROMOTION_ORDER.index(
                "subscription_transactions"
            ),
        )

    def test_business_columns_come_from_approved_schema(self):
        self.assertEqual(
            business_columns(
                "installations"
            ),
            (
                "installation_id",
                "anonymous_id",
                "installed_at",
                "platform",
                "acquisition_channel",
                "country_code",
            ),
        )

    def test_insert_statement_is_insert_select(self):
        sql = build_insert_statement(
            "users"
        ).lower()

        self.assertIn(
            "insert into staging.users",
            sql,
        )

        self.assertIn(
            "from raw.users as r",
            sql,
        )

    def test_insert_statement_preserves_raw_lineage(self):
        sql = build_insert_statement(
            "product_events"
        ).lower()

        required = (
            "ingestion_batch_id",
            "source_file",
            "source_row_number",
            "raw_ingested_at",
            "row_hash",
            "validation_run_id",
        )

        for column in required:
            self.assertIn(
                column,
                sql,
            )

        self.assertIn(
            "r.ingested_at",
            sql,
        )

    def test_insert_is_batch_scoped(self):
        sql = build_insert_statement(
            "subscriptions"
        ).lower()

        self.assertRegex(
            sql,
            re.compile(
                r"where\s+r\.ingestion_batch_id\s*"
                r"=\s*%s"
            ),
        )

    def test_insert_is_deterministically_ordered(self):
        sql = build_insert_statement(
            "app_releases"
        ).lower()

        self.assertRegex(
            sql,
            re.compile(
                r"order\s+by\s+"
                r"r\.source_row_number"
            ),
        )

    def test_promoter_never_mutates_raw(self):
        for dataset in PROMOTION_ORDER:
            sql = build_insert_statement(
                dataset
            ).lower()

            forbidden = (
                "insert into raw.",
                "update raw.",
                "delete from raw.",
                "truncate raw.",
            )

            for token in forbidden:
                self.assertNotIn(
                    token,
                    sql,
                )


if __name__ == "__main__":
    unittest.main()