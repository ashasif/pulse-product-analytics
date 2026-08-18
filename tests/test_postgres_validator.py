from __future__ import annotations

from collections import Counter
import unittest

from src.validation.postgres_validator import (
    build_validation_checks,
    validate_raw_batch,
)


class FakeCursor:
    def __init__(
        self,
        *,
        existing_success: bool = False,
        fail_first_check: bool = False,
    ):
        self.existing_success = existing_success
        self.fail_first_check = fail_first_check

        self.current_row = None
        self.validation_select_count = 0
        self.check_result_inserts = 0

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False

    def execute(
        self,
        query,
        params=None,
    ):
        normalized = " ".join(
            str(query).lower().split()
        )

        if (
            normalized.startswith(
                "select snapshot_id, status "
                "from raw.ingestion_batches"
            )
        ):
            self.current_row = (
                "raw_" + ("a" * 64),
                "succeeded",
            )
            return

        if (
            "from validation.validation_runs"
            in normalized
            and "status = 'succeeded'"
            in normalized
            and normalized.startswith("select")
        ):
            if self.existing_success:
                self.current_row = (
                    7,
                    71,
                    71,
                    71,
                    0,
                )
            else:
                self.current_row = None
            return

        if (
            normalized.startswith(
                "insert into "
                "validation.validation_runs"
            )
            and "returning validation_run_id"
            in normalized
        ):
            self.current_row = (42,)
            return

        if normalized.startswith(
            "insert into validation.check_results"
        ):
            self.check_result_inserts += 1
            self.current_row = None
            return

        if normalized.startswith(
            "update validation.validation_runs"
        ):
            self.current_row = None
            return

        if normalized.startswith("select"):
            self.validation_select_count += 1

            if (
                self.fail_first_check
                and self.validation_select_count == 1
            ):
                self.current_row = (2,)
            else:
                self.current_row = (0,)
            return

        self.current_row = None

    def fetchone(self):
        return self.current_row


class FakeConnection:
    def __init__(
        self,
        *,
        existing_success: bool = False,
        fail_first_check: bool = False,
    ):
        self.fake_cursor = FakeCursor(
            existing_success=existing_success,
            fail_first_check=fail_first_check,
        )
        self.commit_count = 0
        self.rollback_count = 0
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True


class ValidationCatalogueTests(
    unittest.TestCase
):

    def test_catalogue_contains_71_checks(self):
        checks = build_validation_checks()

        self.assertEqual(
            len(checks),
            71,
        )

    def test_check_names_are_unique(self):
        checks = build_validation_checks()

        names = [
            check.name
            for check in checks
        ]

        self.assertEqual(
            len(names),
            len(set(names)),
        )

    def test_all_validation_categories_exist(self):
        categories = {
            check.category
            for check in build_validation_checks()
        }

        self.assertEqual(
            categories,
            {
                "reconciliation",
                "uniqueness",
                "referential_integrity",
                "chronology",
                "domain",
                "nullability",
            },
        )

    def test_expected_category_counts(self):
        counts = Counter(
            check.category
            for check in build_validation_checks()
        )

        self.assertEqual(
            counts,
            {
                "reconciliation": 18,
                "uniqueness": 13,
                "referential_integrity": 13,
                "chronology": 11,
                "nullability": 8,
                "domain": 8,
            },
        )

    def test_every_dataset_has_nullability_and_domain_checks(
        self,
    ):
        checks = build_validation_checks()

        nullability = {
            check.dataset_name
            for check in checks
            if check.category
                == "nullability"
        }

        domain = {
            check.dataset_name
            for check in checks
            if check.category == "domain"
        }

        expected = {
            "installations",
            "users",
            "product_events",
            "subscriptions",
            "subscription_transactions",
            "experiment_assignments",
            "marketing_spend",
            "app_releases",
        }

        self.assertEqual(
            nullability,
            expected,
        )
        self.assertEqual(
            domain,
            expected,
        )

    def test_check_queries_are_read_only(self):
        forbidden = (
            "insert into raw.",
            "update raw.",
            "delete from raw.",
            "truncate raw.",
            "drop table raw.",
            "insert into staging.",
            "update staging.",
            "delete from staging.",
        )

        for check in build_validation_checks():
            lowered = check.query.lower()

            for token in forbidden:
                self.assertNotIn(
                    token,
                    lowered,
                )


class ValidationRunnerTests(
    unittest.TestCase
):

    def test_successful_run_persists_every_check(
        self,
    ):
        connection = FakeConnection()

        result = validate_raw_batch(
            1,
            connection=connection,
        )

        self.assertEqual(
            result.status,
            "succeeded",
        )
        self.assertEqual(
            result.validation_run_id,
            42,
        )
        self.assertEqual(
            result.expected_check_count,
            71,
        )
        self.assertEqual(
            result.passed_check_count,
            71,
        )
        self.assertEqual(
            result.failed_check_count,
            0,
        )
        self.assertFalse(
            result.already_validated
        )
        self.assertEqual(
            connection.fake_cursor
            .check_result_inserts,
            71,
        )
        self.assertEqual(
            connection.commit_count,
            1,
        )

    def test_business_validation_failure_is_audited(
        self,
    ):
        connection = FakeConnection(
            fail_first_check=True,
        )

        result = validate_raw_batch(
            1,
            connection=connection,
        )

        self.assertEqual(
            result.status,
            "failed",
        )
        self.assertEqual(
            result.passed_check_count,
            70,
        )
        self.assertEqual(
            result.failed_check_count,
            1,
        )
        self.assertEqual(
            len(result.failures),
            1,
        )
        self.assertEqual(
            connection.fake_cursor
            .check_result_inserts,
            71,
        )
        self.assertEqual(
            connection.commit_count,
            1,
        )

    def test_successful_run_is_idempotent(self):
        connection = FakeConnection(
            existing_success=True,
        )

        result = validate_raw_batch(
            1,
            connection=connection,
        )

        self.assertEqual(
            result.validation_run_id,
            7,
        )
        self.assertEqual(
            result.status,
            "succeeded",
        )
        self.assertTrue(
            result.already_validated
        )
        self.assertEqual(
            connection.fake_cursor
            .check_result_inserts,
            0,
        )
        self.assertEqual(
            connection.rollback_count,
            1,
        )

    def test_validation_does_not_close_supplied_connection(
        self,
    ):
        connection = FakeConnection()

        validate_raw_batch(
            1,
            connection=connection,
        )

        self.assertFalse(
            connection.closed
        )


if __name__ == "__main__":
    unittest.main()
