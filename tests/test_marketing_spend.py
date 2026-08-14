"""Tests for the Pulse synthetic marketing-spend generator."""

from collections import defaultdict
from statistics import mean
import unittest

from src.generation.installations import (
    generate_installations,
    get_simulation_bounds,
)
from src.generation.marketing_spend import (
    build_weekly_periods,
    generate_marketing_spend,
    load_marketing_spend_config,
)


class MarketingSpendGeneratorTests(
    unittest.TestCase
):
    """Validate marketing-spend generation behaviour."""

    @classmethod
    def setUpClass(cls):
        """Create deterministic reusable samples."""

        (
            cls.start_at,
            cls.end_at,
        ) = get_simulation_bounds()

        cls.config = (
            load_marketing_spend_config()
        )

        cls.rows = (
            generate_marketing_spend(
                cls.start_at,
                cls.end_at,
            )
        )

        cls.periods = (
            build_weekly_periods(
                cls.start_at,
                cls.end_at,
            )
        )

    def test_configuration_matches_installation_channels(
        self,
    ):
        """Marketing channels must match acquisition channels."""

        self.assertEqual(
            set(
                self.config[
                    "acquisition_channels"
                ]
            ),
            set(
                self.config[
                    "channels"
                ]
            ),
        )

        self.assertEqual(
            self.config[
                "currency"
            ],
            "GBP",
        )

        self.assertEqual(
            self.config[
                "grain"
            ],
            "weekly",
        )

    def test_row_count_matches_week_channel_grain(
        self,
    ):
        """There should be one row per week per channel."""

        expected = (
            len(
                self.periods
            )
            * len(
                self.config[
                    "acquisition_channels"
                ]
            )
        )

        self.assertEqual(
            len(
                self.rows
            ),
            expected,
        )

    def test_marketing_spend_ids_are_unique(
        self,
    ):
        """Every marketing-spend row needs a unique ID."""

        identifiers = {
            row[
                "marketing_spend_id"
            ]
            for row in self.rows
        }

        self.assertEqual(
            len(
                identifiers
            ),
            len(
                self.rows
            ),
        )

    def test_week_channel_pairs_are_unique(
        self,
    ):
        """Weekly channel grain must contain no duplicates."""

        keys = {
            (
                row[
                    "period_start"
                ],
                row[
                    "acquisition_channel"
                ],
            )
            for row in self.rows
        }

        self.assertEqual(
            len(
                keys
            ),
            len(
                self.rows
            ),
        )

    def test_periods_are_chronological_and_bounded(
        self,
    ):
        """Periods must be ordered and remain in simulation."""

        period_starts = [
            row[
                "period_start"
            ]
            for row in self.rows
        ]

        self.assertEqual(
            period_starts,
            sorted(
                period_starts
            ),
        )

        self.assertTrue(
            all(
                self.start_at.date()
                <= row[
                    "period_start"
                ]
                <= row[
                    "period_end"
                ]
                <= self.end_at.date()
                for row in self.rows
            )
        )

    def test_every_period_has_full_channel_coverage(
        self,
    ):
        """Every week must include all acquisition channels."""

        expected_channels = set(
            self.config[
                "acquisition_channels"
            ]
        )

        channels_by_period = (
            defaultdict(
                set
            )
        )

        for row in self.rows:
            channels_by_period[
                row[
                    "period_start"
                ]
            ].add(
                row[
                    "acquisition_channel"
                ]
            )

        self.assertTrue(
            all(
                channels
                == expected_channels
                for channels
                in channels_by_period.values()
            )
        )

    def test_spend_is_non_negative_and_currency_is_gbp(
        self,
    ):
        """Spend cannot be negative and currency stays GBP."""

        self.assertTrue(
            all(
                row[
                    "spend"
                ] >= 0.0
                for row in self.rows
            )
        )

        self.assertTrue(
            all(
                row[
                    "currency"
                ] == "GBP"
                for row in self.rows
            )
        )

    def test_organic_has_zero_direct_spend(
        self,
    ):
        """Organic must not masquerade as paid acquisition."""

        organic_rows = [
            row
            for row in self.rows
            if (
                row[
                    "acquisition_channel"
                ]
                == "organic"
            )
        ]

        self.assertTrue(
            all(
                row[
                    "spend"
                ] == 0.0
                for row in organic_rows
            )
        )

        self.assertTrue(
            all(
                row[
                    "spend_type"
                ]
                == "zero_direct"
                and row[
                    "impressions"
                ] is None
                and row[
                    "clicks"
                ] is None
                for row in organic_rows
            )
        )

    def test_paid_media_has_valid_delivery_metrics(
        self,
    ):
        """Paid media requires valid spend and delivery."""

        paid_rows = [
            row
            for row in self.rows
            if (
                row[
                    "spend_type"
                ]
                == "paid_media"
            )
        ]

        self.assertGreater(
            len(
                paid_rows
            ),
            0,
        )

        self.assertTrue(
            all(
                row[
                    "spend"
                ] > 0.0
                for row in paid_rows
            )
        )

        self.assertTrue(
            all(
                isinstance(
                    row[
                        "clicks"
                    ],
                    int,
                )
                and isinstance(
                    row[
                        "impressions"
                    ],
                    int,
                )
                and (
                    0
                    < row[
                        "clicks"
                    ]
                    <= row[
                        "impressions"
                    ]
                )
                for row in paid_rows
            )
        )

    def test_paid_media_implied_cpc_and_ctr_are_sensible(
        self,
    ):
        """Media delivery must remain within its economics."""

        for row in self.rows:
            if (
                row[
                    "spend_type"
                ]
                != "paid_media"
            ):
                continue

            channel = row[
                "acquisition_channel"
            ]

            channel_config = (
                self.config[
                    "channels"
                ][
                    channel
                ]
            )

            implied_cpc = (
                row[
                    "spend"
                ]
                / row[
                    "clicks"
                ]
            )

            implied_ctr = (
                row[
                    "clicks"
                ]
                / row[
                    "impressions"
                ]
            )

            self.assertGreaterEqual(
                implied_cpc,
                (
                    channel_config[
                        "cpc_gbp_min"
                    ]
                    * 0.98
                ),
            )

            self.assertLessEqual(
                implied_cpc,
                (
                    channel_config[
                        "cpc_gbp_max"
                    ]
                    * 1.02
                ),
            )

            self.assertGreaterEqual(
                implied_ctr,
                (
                    channel_config[
                        "ctr_min"
                    ]
                    * 0.98
                ),
            )

            self.assertLessEqual(
                implied_ctr,
                (
                    channel_config[
                        "ctr_max"
                    ]
                    * 1.02
                ),
            )

    def test_indirect_channels_have_spend_without_media_delivery(
        self,
    ):
        """Content/referral should not invent ad metrics."""

        indirect_rows = [
            row
            for row in self.rows
            if (
                row[
                    "spend_type"
                ]
                == "indirect"
            )
        ]

        self.assertTrue(
            all(
                row[
                    "spend"
                ] > 0.0
                for row in indirect_rows
            )
        )

        self.assertTrue(
            all(
                row[
                    "impressions"
                ] is None
                and row[
                    "clicks"
                ] is None
                for row in indirect_rows
            )
        )

    def test_campaign_variation_exists(
        self,
    ):
        """Paid media should contain always-on and campaign weeks."""

        campaign_types = {
            row[
                "campaign_type"
            ]
            for row in self.rows
            if (
                row[
                    "spend_type"
                ]
                == "paid_media"
            )
        }

        self.assertTrue(
            {
                "always_on_social",
                "always_on_search",
            }.issubset(
                campaign_types
            )
        )

        self.assertTrue(
            {
                "seasonal_push",
                "tactical_push",
            }
            & campaign_types
        )

    def test_paid_spend_grows_over_time(
        self,
    ):
        """Equivalent later periods need more investment."""

        early_spend = sum(
            row[
                "spend"
            ]
            for row in self.rows
            if (
                row[
                    "spend_type"
                ]
                == "paid_media"
                and row[
                    "period_start"
                ].year == 2024
                and row[
                    "period_start"
                ].month <= 6
            )
        )

        late_spend = sum(
            row[
                "spend"
            ]
            for row in self.rows
            if (
                row[
                    "spend_type"
                ]
                == "paid_media"
                and row[
                    "period_start"
                ].year == 2026
                and row[
                    "period_start"
                ].month <= 6
            )
        )

        self.assertGreater(
            late_spend,
            early_spend,
        )

    def test_seasonality_is_visible_in_paid_spend(
        self,
    ):
        """January should exceed July in comparable 2025 weeks."""

        january = [
            row[
                "spend"
            ]
            for row in self.rows
            if (
                row[
                    "spend_type"
                ]
                == "paid_media"
                and row[
                    "period_start"
                ].year == 2025
                and row[
                    "period_start"
                ].month == 1
            )
        ]

        july = [
            row[
                "spend"
            ]
            for row in self.rows
            if (
                row[
                    "spend_type"
                ]
                == "paid_media"
                and row[
                    "period_start"
                ].year == 2025
                and row[
                    "period_start"
                ].month == 7
            )
        ]

        self.assertGreater(
            mean(
                january
            ),
            mean(
                july
            ),
        )

    def test_generation_is_reproducible(
        self,
    ):
        """Same configuration and seeds reproduce identical rows."""

        second = (
            generate_marketing_spend(
                self.start_at,
                self.end_at,
            )
        )

        self.assertEqual(
            self.rows,
            second,
        )

    def test_marketing_generation_does_not_change_installations(
        self,
    ):
        """Marketing RNG must remain independent of installs."""

        before = (
            generate_installations(
                count=250,
                start_at=self.start_at,
                end_at=self.end_at,
            )
        )

        generate_marketing_spend(
            self.start_at,
            self.end_at,
        )

        after = (
            generate_installations(
                count=250,
                start_at=self.start_at,
                end_at=self.end_at,
            )
        )

        self.assertEqual(
            before,
            after,
        )

    def test_budget_scale_changes_budget_without_changing_grain(
        self,
    ):
        """Scaling budget must not create additional rows."""

        doubled = (
            generate_marketing_spend(
                self.start_at,
                self.end_at,
                budget_scale=2.0,
            )
        )

        self.assertEqual(
            len(
                doubled
            ),
            len(
                self.rows
            ),
        )

        base_total = sum(
            row[
                "spend"
            ]
            for row in self.rows
        )

        doubled_total = sum(
            row[
                "spend"
            ]
            for row in doubled
        )

        self.assertAlmostEqual(
            doubled_total
            / base_total,
            2.0,
            delta=0.001,
        )


if __name__ == "__main__":
    unittest.main()