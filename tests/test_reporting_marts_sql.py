from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REPORTING_SQL = ROOT / "sql" / "reporting"


class ReportingMartSqlTests(unittest.TestCase):

    def _read(self, filename):
        return (
            REPORTING_SQL / filename
        ).read_text(encoding="utf-8").lower()

    def test_step6b_sql_files_exist(self):
        expected = {
            "004_extend_metric_definitions.sql",
            "005_create_acquisition_engagement_views.sql",
            "006_create_retention_views.sql",
            "007_create_experiment_views.sql",
        }

        actual = {
            path.name
            for path in REPORTING_SQL.glob("*.sql")
        }

        self.assertTrue(expected.issubset(actual))

    def test_daily_views_preserve_build_lineage(self):
        sql = self._read(
            "003_create_foundation_views.sql"
        )

        self.assertIn("successful_builds", sql)
        self.assertIn("ingestion_batch_id", sql)
        self.assertIn("analytics_build_run_id", sql)
        self.assertIn("cross join analytics.dim_date", sql)

    def test_installation_funnel_is_installation_cohort_based(self):
        sql = self._read(
            "005_create_acquisition_engagement_views.sql"
        )

        self.assertIn(
            "reporting.vw_installation_cohort_funnel",
            sql,
        )
        self.assertIn("installed_date", sql)
        self.assertIn("install_to_signup_rate", sql)

    def test_signup_funnel_uses_registered_users_denominator(self):
        sql = self._read(
            "005_create_acquisition_engagement_views.sql"
        )

        self.assertIn(
            "reporting.vw_signup_cohort_funnel",
            sql,
        )
        self.assertIn("registered_user_count", sql)
        self.assertIn("onboarding_start_rate", sql)
        self.assertIn("onboarding_completion_rate", sql)

    def test_weekly_acquisition_matches_channel_and_period(self):
        sql = self._read(
            "005_create_acquisition_engagement_views.sql"
        )

        self.assertIn(
            "reporting.vw_weekly_acquisition_performance",
            sql,
        )
        self.assertIn(
            "i.acquisition_channel = m.acquisition_channel",
            sql,
        )
        self.assertIn(
            "i.installed_date between m.period_start and m.period_end",
            sql,
        )
        self.assertIn("cost_per_install_gbp", sql)

    def test_feature_engagement_uses_feature_used_events(self):
        sql = self._read(
            "005_create_acquisition_engagement_views.sql"
        )

        self.assertIn(
            "reporting.vw_daily_feature_engagement",
            sql,
        )
        self.assertIn(
            "where e.event_name = 'feature_used'",
            sql,
        )
        self.assertIn("feature_name", sql)

    def test_trial_conversion_excludes_immature_trials(self):
        sql = self._read(
            "006_create_retention_views.sql"
        )

        self.assertIn(
            "reporting.vw_trial_conversion_cohorts",
            sql,
        )
        self.assertIn("is_mature_trial", sql)
        self.assertIn("mature_trial_count", sql)
        self.assertIn("trial_to_paid_conversion_rate", sql)

    def test_retention_uses_observation_maturity(self):
        sql = self._read(
            "006_create_retention_views.sql"
        )

        self.assertIn(
            "reporting.vw_observation_cutoff",
            sql,
        )
        self.assertIn("eligible_d30", sql)
        self.assertIn("eligible_d90", sql)
        self.assertIn("eligible_d180", sql)
        self.assertIn("eligible_d365", sql)

    def test_retention_rates_use_expiry_after_threshold(self):
        sql = self._read(
            "006_create_retention_views.sql"
        )

        self.assertIn("retained_d30", sql)
        self.assertIn("retained_d90", sql)
        self.assertIn("retained_d180", sql)
        self.assertIn("retained_d365", sql)
        self.assertIn("s.expired_at is null", sql)

    def test_experiment_output_preserves_assignment_grain(self):
        sql = self._read(
            "007_create_experiment_views.sql"
        )

        self.assertIn(
            "reporting.vw_experiment_assignment_outcomes",
            sql,
        )
        self.assertIn("experiment_assignment_key", sql)
        self.assertIn("assignment_at", sql)
        self.assertIn("analysis_window_mature", sql)

    def test_experiment_revenue_requires_successful_payment(self):
        sql = self._read(
            "007_create_experiment_views.sql"
        )

        self.assertIn(
            "t.payment_status = 'succeeded'",
            sql,
        )
        self.assertIn(
            "successful_revenue_gbp_30d",
            sql,
        )

    def test_experiment_summary_does_not_add_significance_logic(self):
        sql = self._read(
            "007_create_experiment_views.sql"
        )

        self.assertIn(
            "reporting.vw_experiment_variant_summary",
            sql,
        )
        self.assertNotIn("p_value", sql)
        self.assertNotIn("statistical_significance", sql)

    def test_step6b_reporting_sql_does_not_read_raw_or_staging(self):
        combined = "\n".join(
            self._read(filename)
            for filename in (
                "003_create_foundation_views.sql",
                "004_extend_metric_definitions.sql",
                "005_create_acquisition_engagement_views.sql",
                "006_create_retention_views.sql",
                "007_create_experiment_views.sql",
            )
        )

        self.assertNotIn(" raw.", combined)
        self.assertNotIn(" staging.", combined)


if __name__ == "__main__":
    unittest.main()