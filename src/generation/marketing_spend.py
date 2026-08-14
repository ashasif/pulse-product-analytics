"""Synthetic marketing-spend generation for Pulse."""

from datetime import date, datetime, timedelta
from math import exp
from pathlib import Path
import random

from src.generation.installations import (
    DEFAULT_SIMULATION_CONFIG,
    load_installation_dimensions,
    load_simulation_config,
)
from src.generation.randomness import get_substream_seed


VALID_SPEND_TYPES = {
    "zero_direct",
    "paid_media",
    "indirect",
}


def _validate_probability(
    value: float,
    name: str,
) -> float:
    """Validate a probability in the inclusive range [0, 1]."""

    if not isinstance(value, (int, float)):
        raise TypeError(
            f"{name} must be numeric"
        )

    value = float(value)

    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"{name} must be between 0 and 1"
        )

    return value


def _validate_positive_number(
    value: float,
    name: str,
    *,
    allow_zero: bool = False,
) -> float:
    """Validate a numeric configuration value."""

    if not isinstance(value, (int, float)):
        raise TypeError(
            f"{name} must be numeric"
        )

    value = float(value)

    if allow_zero:
        if value < 0.0:
            raise ValueError(
                f"{name} must be non-negative"
            )
    elif value <= 0.0:
        raise ValueError(
            f"{name} must be greater than zero"
        )

    return value


def load_marketing_spend_config(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict:
    """Load and validate Pulse marketing-spend assumptions."""

    config = load_simulation_config(
        config_path
    )

    marketing = config[
        "marketing_spend"
    ]

    grain = marketing[
        "grain"
    ]

    if grain != "weekly":
        raise ValueError(
            "Unsupported marketing_spend "
            f"grain: {grain}"
        )

    currency = marketing[
        "currency"
    ]

    if currency != "GBP":
        raise ValueError(
            "marketing_spend currency must be GBP"
        )

    growth_model = marketing[
        "growth_model"
    ]

    if growth_model != "linear":
        raise ValueError(
            "Unsupported marketing growth model: "
            f"{growth_model}"
        )

    growth_start = _validate_positive_number(
        marketing[
            "growth_start_multiplier"
        ],
        (
            "marketing_spend."
            "growth_start_multiplier"
        ),
    )

    growth_end = _validate_positive_number(
        marketing[
            "growth_end_multiplier"
        ],
        (
            "marketing_spend."
            "growth_end_multiplier"
        ),
    )

    month_multipliers = tuple(
        _validate_positive_number(
            value,
            (
                "marketing_spend."
                "month_multipliers"
            ),
        )
        for value in marketing[
            "month_multipliers"
        ]
    )

    if len(month_multipliers) != 12:
        raise ValueError(
            "marketing_spend.month_multipliers "
            "must contain 12 values"
        )

    weekly_noise_sigma = (
        _validate_positive_number(
            marketing[
                "weekly_noise_sigma"
            ],
            (
                "marketing_spend."
                "weekly_noise_sigma"
            ),
            allow_zero=True,
        )
    )

    campaign_config = marketing[
        "campaigns"
    ]

    peak_months = tuple(
        campaign_config[
            "peak_months"
        ]
    )

    if not peak_months:
        raise ValueError(
            "marketing_spend.campaigns."
            "peak_months must not be empty"
        )

    if any(
        not isinstance(month, int)
        or not 1 <= month <= 12
        for month in peak_months
    ):
        raise ValueError(
            "marketing_spend campaign peak "
            "months must be integers 1-12"
        )

    if (
        len(set(peak_months))
        != len(peak_months)
    ):
        raise ValueError(
            "marketing_spend campaign peak "
            "months must be unique"
        )

    base_campaign_probability = (
        _validate_probability(
            campaign_config[
                "base_probability"
            ],
            (
                "marketing_spend.campaigns."
                "base_probability"
            ),
        )
    )

    peak_campaign_probability = (
        _validate_probability(
            campaign_config[
                "peak_probability"
            ],
            (
                "marketing_spend.campaigns."
                "peak_probability"
            ),
        )
    )

    if (
        peak_campaign_probability
        < base_campaign_probability
    ):
        raise ValueError(
            "Peak campaign probability must "
            "be at least the base probability"
        )

    campaign_multiplier_min = (
        _validate_positive_number(
            campaign_config[
                "multiplier_min"
            ],
            (
                "marketing_spend.campaigns."
                "multiplier_min"
            ),
        )
    )

    campaign_multiplier_max = (
        _validate_positive_number(
            campaign_config[
                "multiplier_max"
            ],
            (
                "marketing_spend.campaigns."
                "multiplier_max"
            ),
        )
    )

    if campaign_multiplier_min < 1.0:
        raise ValueError(
            "Campaign multiplier minimum "
            "must be at least 1.0"
        )

    if (
        campaign_multiplier_max
        < campaign_multiplier_min
    ):
        raise ValueError(
            "Campaign multiplier maximum "
            "must be >= minimum"
        )

    installation_dimensions = (
        load_installation_dimensions(
            config_path
        )
    )

    acquisition_channels = tuple(
        installation_dimensions[
            "acquisition_channel"
        ][
            "values"
        ]
    )

    configured_channels = marketing[
        "channels"
    ]

    if (
        set(configured_channels)
        != set(acquisition_channels)
    ):
        missing = sorted(
            set(acquisition_channels)
            - set(configured_channels)
        )

        extra = sorted(
            set(configured_channels)
            - set(acquisition_channels)
        )

        raise ValueError(
            "marketing_spend channels must "
            "exactly match installation "
            "acquisition channels; "
            f"missing={missing}, "
            f"extra={extra}"
        )

    validated_channels = {}

    for channel in acquisition_channels:
        channel_config = (
            configured_channels[
                channel
            ]
        )

        spend_type = channel_config[
            "spend_type"
        ]

        if (
            spend_type
            not in VALID_SPEND_TYPES
        ):
            raise ValueError(
                "Unsupported spend_type for "
                f"{channel}: {spend_type}"
            )

        base_weekly_spend = (
            _validate_positive_number(
                channel_config[
                    "base_weekly_spend_gbp"
                ],
                (
                    "marketing_spend.channels."
                    f"{channel}."
                    "base_weekly_spend_gbp"
                ),
                allow_zero=True,
            )
        )

        campaign_type = channel_config[
            "campaign_type"
        ]

        if (
            not isinstance(
                campaign_type,
                str,
            )
            or not campaign_type.strip()
        ):
            raise ValueError(
                "marketing_spend channel "
                f"{channel} needs a "
                "campaign_type"
            )

        validated_channel = {
            "spend_type": spend_type,
            "base_weekly_spend_gbp": (
                base_weekly_spend
            ),
            "campaign_type": (
                campaign_type
            ),
        }

        if spend_type == "zero_direct":
            if base_weekly_spend != 0.0:
                raise ValueError(
                    "zero_direct channel "
                    f"{channel} must have "
                    "zero spend"
                )

        elif spend_type == "paid_media":
            if base_weekly_spend <= 0.0:
                raise ValueError(
                    "paid_media channel "
                    f"{channel} must have "
                    "positive spend"
                )

            cpc_min = (
                _validate_positive_number(
                    channel_config[
                        "cpc_gbp_min"
                    ],
                    (
                        "marketing_spend."
                        "channels."
                        f"{channel}."
                        "cpc_gbp_min"
                    ),
                )
            )

            cpc_max = (
                _validate_positive_number(
                    channel_config[
                        "cpc_gbp_max"
                    ],
                    (
                        "marketing_spend."
                        "channels."
                        f"{channel}."
                        "cpc_gbp_max"
                    ),
                )
            )

            if cpc_max < cpc_min:
                raise ValueError(
                    "CPC maximum must be "
                    ">= minimum for "
                    f"{channel}"
                )

            ctr_min = (
                _validate_probability(
                    channel_config[
                        "ctr_min"
                    ],
                    (
                        "marketing_spend."
                        "channels."
                        f"{channel}.ctr_min"
                    ),
                )
            )

            ctr_max = (
                _validate_probability(
                    channel_config[
                        "ctr_max"
                    ],
                    (
                        "marketing_spend."
                        "channels."
                        f"{channel}.ctr_max"
                    ),
                )
            )

            if ctr_min <= 0.0:
                raise ValueError(
                    "CTR minimum must be "
                    f"> 0 for {channel}"
                )

            if ctr_max < ctr_min:
                raise ValueError(
                    "CTR maximum must be "
                    ">= minimum for "
                    f"{channel}"
                )

            validated_channel.update(
                {
                    "cpc_gbp_min": (
                        cpc_min
                    ),
                    "cpc_gbp_max": (
                        cpc_max
                    ),
                    "ctr_min": ctr_min,
                    "ctr_max": ctr_max,
                }
            )

        else:
            if base_weekly_spend <= 0.0:
                raise ValueError(
                    "indirect channel "
                    f"{channel} must have "
                    "positive spend"
                )

        validated_channels[
            channel
        ] = validated_channel

    return {
        "grain": grain,
        "currency": currency,
        "growth_model": growth_model,
        "growth_start_multiplier": (
            growth_start
        ),
        "growth_end_multiplier": (
            growth_end
        ),
        "weekly_noise_sigma": (
            weekly_noise_sigma
        ),
        "month_multipliers": (
            month_multipliers
        ),
        "campaigns": {
            "peak_months": (
                peak_months
            ),
            "base_probability": (
                base_campaign_probability
            ),
            "peak_probability": (
                peak_campaign_probability
            ),
            "multiplier_min": (
                campaign_multiplier_min
            ),
            "multiplier_max": (
                campaign_multiplier_max
            ),
        },
        "acquisition_channels": (
            acquisition_channels
        ),
        "channels": (
            validated_channels
        ),
    }


def build_weekly_periods(
    start_at: datetime,
    end_at: datetime,
) -> list[tuple[date, date]]:
    """Build inclusive seven-day periods."""

    if (
        start_at.tzinfo is None
        or end_at.tzinfo is None
    ):
        raise ValueError(
            "start_at and end_at must "
            "be timezone-aware"
        )

    if start_at >= end_at:
        raise ValueError(
            "start_at must be earlier "
            "than end_at"
        )

    periods = []

    current_start = (
        start_at.date()
    )

    final_date = (
        end_at.date()
    )

    while current_start <= final_date:
        current_end = min(
            current_start
            + timedelta(days=6),
            final_date,
        )

        periods.append(
            (
                current_start,
                current_end,
            )
        )

        current_start = (
            current_end
            + timedelta(days=1)
        )

    return periods


def _growth_multiplier(
    period_start: date,
    period_end: date,
    simulation_start: date,
    simulation_end: date,
    growth_start: float,
    growth_end: float,
) -> float:
    """Return linear growth at the period midpoint."""

    total_days = (
        simulation_end
        - simulation_start
    ).days

    if total_days <= 0:
        return growth_start

    start_offset = (
        period_start
        - simulation_start
    ).days

    end_offset = (
        period_end
        - simulation_start
    ).days

    midpoint_offset = (
        start_offset
        + end_offset
    ) / 2.0

    fraction = (
        midpoint_offset
        / total_days
    )

    return (
        growth_start
        + fraction
        * (
            growth_end
            - growth_start
        )
    )


def _mean_one_lognormal_multiplier(
    rng: random.Random,
    sigma: float,
) -> float:
    """
    Sample positive weekly noise.

    The distribution is centred so that
    its expected multiplier is close to 1.
    """

    if sigma == 0.0:
        return 1.0

    return exp(
        rng.normalvariate(
            -(sigma ** 2) / 2.0,
            sigma,
        )
    )


def generate_marketing_spend(
    start_at: datetime,
    end_at: datetime,
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
    budget_scale: float = 1.0,
) -> list[dict]:
    """
    Generate deterministic weekly marketing-spend records.

    budget_scale is an explicit dataset-size normalisation factor.

    It scales planned marketing budgets without reading or
    reverse-engineering realised installation counts.
    """

    if not isinstance(
        budget_scale,
        (int, float),
    ):
        raise TypeError(
            "budget_scale must be numeric"
        )

    budget_scale = float(
        budget_scale
    )

    if budget_scale <= 0.0:
        raise ValueError(
            "budget_scale must be "
            "greater than zero"
        )

    marketing = (
        load_marketing_spend_config(
            config_path
        )
    )

    periods = build_weekly_periods(
        start_at,
        end_at,
    )

    campaign_calendar_rng = (
        random.Random(
            get_substream_seed(
                "marketing_spend",
                "campaign_calendar",
            )
        )
    )

    campaign_intensity_rng = (
        random.Random(
            get_substream_seed(
                "marketing_spend",
                "campaign_intensity",
            )
        )
    )

    budget_noise_rngs = {
        channel: random.Random(
            get_substream_seed(
                "marketing_spend",
                (
                    "budget_noise:"
                    f"{channel}"
                ),
            )
        )
        for channel in marketing[
            "acquisition_channels"
        ]
    }

    paid_channels = tuple(
        channel
        for channel in marketing[
            "acquisition_channels"
        ]
        if (
            marketing[
                "channels"
            ][
                channel
            ][
                "spend_type"
            ]
            == "paid_media"
        )
    )

    cpc_rngs = {
        channel: random.Random(
            get_substream_seed(
                "marketing_spend",
                f"cpc:{channel}",
            )
        )
        for channel in paid_channels
    }

    ctr_rngs = {
        channel: random.Random(
            get_substream_seed(
                "marketing_spend",
                f"ctr:{channel}",
            )
        )
        for channel in paid_channels
    }

    rows = []

    simulation_start = (
        start_at.date()
    )

    simulation_end = (
        end_at.date()
    )

    campaign_config = (
        marketing[
            "campaigns"
        ]
    )

    for (
        period_start,
        period_end,
    ) in periods:

        active_days = (
            period_end
            - period_start
        ).days + 1

        partial_week_multiplier = (
            active_days / 7.0
        )

        midpoint = (
            period_start
            + timedelta(
                days=(
                    active_days - 1
                ) // 2
            )
        )

        growth_multiplier = (
            _growth_multiplier(
                period_start,
                period_end,
                simulation_start,
                simulation_end,
                marketing[
                    "growth_start_multiplier"
                ],
                marketing[
                    "growth_end_multiplier"
                ],
            )
        )

        month_multiplier = (
            marketing[
                "month_multipliers"
            ][
                midpoint.month - 1
            ]
        )

        in_peak_month = (
            midpoint.month
            in campaign_config[
                "peak_months"
            ]
        )

        campaign_probability = (
            campaign_config[
                "peak_probability"
            ]
            if in_peak_month
            else campaign_config[
                "base_probability"
            ]
        )

        campaign_active = (
            campaign_calendar_rng.random()
            < campaign_probability
        )

        if campaign_active:
            campaign_multiplier = (
                campaign_intensity_rng.uniform(
                    campaign_config[
                        "multiplier_min"
                    ],
                    campaign_config[
                        "multiplier_max"
                    ],
                )
            )

            paid_campaign_type = (
                "seasonal_push"
                if in_peak_month
                else "tactical_push"
            )

        else:
            campaign_multiplier = 1.0
            paid_campaign_type = None

        for channel in marketing[
            "acquisition_channels"
        ]:
            channel_config = (
                marketing[
                    "channels"
                ][
                    channel
                ]
            )

            spend_type = (
                channel_config[
                    "spend_type"
                ]
            )

            if spend_type == "zero_direct":
                spend = 0.0

                campaign_type = (
                    channel_config[
                        "campaign_type"
                    ]
                )

                impressions = None
                clicks = None

            else:
                noise_multiplier = (
                    _mean_one_lognormal_multiplier(
                        budget_noise_rngs[
                            channel
                        ],
                        marketing[
                            "weekly_noise_sigma"
                        ],
                    )
                )

                channel_campaign_multiplier = (
                    campaign_multiplier
                    if (
                        spend_type
                        == "paid_media"
                    )
                    else 1.0
                )

                spend = round(
                    channel_config[
                        "base_weekly_spend_gbp"
                    ]
                    * budget_scale
                    * growth_multiplier
                    * month_multiplier
                    * noise_multiplier
                    * (
                        channel_campaign_multiplier
                    )
                    * partial_week_multiplier,
                    2,
                )

                campaign_type = (
                    paid_campaign_type
                    if (
                        spend_type
                        == "paid_media"
                        and (
                            paid_campaign_type
                            is not None
                        )
                    )
                    else channel_config[
                        "campaign_type"
                    ]
                )

                if (
                    spend_type
                    == "paid_media"
                ):
                    cpc = (
                        cpc_rngs[
                            channel
                        ].uniform(
                            channel_config[
                                "cpc_gbp_min"
                            ],
                            channel_config[
                                "cpc_gbp_max"
                            ],
                        )
                    )

                    ctr = (
                        ctr_rngs[
                            channel
                        ].uniform(
                            channel_config[
                                "ctr_min"
                            ],
                            channel_config[
                                "ctr_max"
                            ],
                        )
                    )

                    clicks = max(
                        1,
                        int(
                            round(
                                spend
                                / cpc
                            )
                        ),
                    )

                    impressions = max(
                        clicks,
                        int(
                            round(
                                clicks
                                / ctr
                            )
                        ),
                    )

                else:
                    impressions = None
                    clicks = None

            rows.append(
                {
                    "marketing_spend_id": (
                        "mkt_"
                        f"{period_start:%Y%m%d}_"
                        f"{channel}"
                    ),
                    "period_start": (
                        period_start
                    ),
                    "period_end": (
                        period_end
                    ),
                    "acquisition_channel": (
                        channel
                    ),
                    "spend_type": (
                        spend_type
                    ),
                    "campaign_type": (
                        campaign_type
                    ),
                    "spend": (
                        spend
                    ),
                    "currency": (
                        marketing[
                            "currency"
                        ]
                    ),
                    "impressions": (
                        impressions
                    ),
                    "clicks": (
                        clicks
                    ),
                }
            )

    return rows