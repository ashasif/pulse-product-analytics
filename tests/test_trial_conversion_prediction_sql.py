"""Tests for the Phase 6 row-level trial-conversion reporting contract."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = (
    ROOT
    / "sql"
    / "reporting"
    / "016_create_trial_conversion_prediction_base.sql"
)


class TrialConversionPredictionSqlTests(unittest.TestCase):
    """Protect canonical label semantics and leakage boundaries."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.sql = SQL_PATH.read_text(
            encoding="utf-8"
        ).lower()

    def test_creates_row_level_prediction_base(self):
        self.assertIn(
            "create or replace view "
            "reporting.vw_trial_conversion_prediction_base",
            self.sql,
        )

    def test_uses_canonical_observation_cutoff(self):
        self.assertIn(
            "reporting.vw_observation_cutoff",
            self.sql,
        )
        self.assertIn(
            "s.trial_ends_at "
            "<= c.observation_cutoff_at",
            " ".join(self.sql.split()),
        )

    def test_uses_existing_paid_conversion_semantics(self):
        compact = " ".join(
            self.sql.split()
        )
        self.assertIn(
            "s.subscription_started_at is not null",
            compact,
        )
        self.assertIn(
            "s.subscription_started_at "
            "<= c.observation_cutoff_at",
            compact,
        )

    def test_does_not_create_new_metric_definition(self):
        self.assertNotIn(
            "insert into reporting.metric_definitions",
            self.sql,
        )
        self.assertNotIn(
            "update reporting.metric_definitions",
            self.sql,
        )

    def test_does_not_expose_post_outcome_state_fields(self):
        for field in (
            "current_period_start_at",
            "current_period_end_at",
            "cancellation_requested_at",
            "expired_at",
            "auto_renew",
            "end_reason",
        ):
            self.assertNotIn(
                field,
                self.sql,
            )


if __name__ == "__main__":
    unittest.main()