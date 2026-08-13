"""Synthetic product-event generation for Pulse."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isclose, log
from pathlib import Path
import random
import tomllib
from typing import Any

from src.generation.randomness import get_substream_seed


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_SIMULATION_CONFIG = (
    PROJECT_ROOT
    / "config"
    / "simulation.toml"
)


LIFECYCLE_EVENT_NAMES = (
    "app_install",
    "signup",
    "onboarding_started",
    "onboarding_completed",
)


USAGE_EVENT_NAMES = (
    "session_started",
    "feature_used",
    "paywall_viewed",
)


EVENT_SORT_PRIORITY = {
    "app_install": 0,
    "signup": 1,
    "onboarding_started": 2,
    "onboarding_completed": 3,
    "session_started": 4,
    "feature_used": 5,
    "paywall_viewed": 6,
}


def load_simulation_config(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict[str, Any]:
    """Load the main Pulse simulation configuration."""

    with config_path.open("rb") as file:
        return tomllib.load(file)


def _parse_utc_timestamp(
    value: str,
) -> datetime:
    """Parse an ISO-8601 timestamp as a UTC-aware datetime."""

    timestamp = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(
            tzinfo=timezone.utc,
        )

    return timestamp.astimezone(
        timezone.utc
    )


def get_snapshot_at(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> datetime:
    """Return the configured dataset snapshot timestamp."""

    config = load_simulation_config(
        config_path
    )

    return _parse_utc_timestamp(
        config["simulation"]["snapshot_at"]
    )


def _validate_probability(
    value: float,
    name: str,
) -> None:
    """Validate a probability."""

    if not 0.0 <= value <= 1.0:
        raise ValueError(
            f"{name} must be between 0 and 1"
        )


def _validate_weights(
    weights: dict[str, float],
    name: str,
) -> None:
    """Validate a named probability distribution."""

    if not weights:
        raise ValueError(
            f"{name} must not be empty"
        )

    if any(
        weight < 0
        for weight in weights.values()
    ):
        raise ValueError(
            f"{name} contains a negative weight"
        )

    if not isclose(
        sum(weights.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            f"{name} weights must sum to 1"
        )


def _validate_parallel_distribution(
    values: list[Any],
    weights: list[float],
    name: str,
) -> None:
    """Validate values and corresponding weights."""

    if not values:
        raise ValueError(
            f"{name} values must not be empty"
        )

    if len(values) != len(weights):
        raise ValueError(
            f"{name} must have the same number "
            "of values and weights"
        )

    if any(
        weight < 0
        for weight in weights
    ):
        raise ValueError(
            f"{name} contains a negative weight"
        )

    if not isclose(
        sum(weights),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            f"{name} weights must sum to 1"
        )


def load_product_event_config(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict[str, Any]:
    """Load and validate product-event assumptions."""

    config = load_simulation_config(
        config_path
    )

    event_config = config[
        "product_events"
    ]

    minimum_delay = event_config[
        "first_session_delay_seconds_min"
    ]

    maximum_delay = event_config[
        "first_session_delay_seconds_max"
    ]

    if minimum_delay < 0:
        raise ValueError(
            "first_session_delay_seconds_min "
            "must be non-negative"
        )

    if maximum_delay < minimum_delay:
        raise ValueError(
            "first_session_delay_seconds_max "
            "must be >= minimum"
        )

    if (
        event_config["activity_time_alpha"]
        <= 0
    ):
        raise ValueError(
            "activity_time_alpha must be "
            "greater than zero"
        )

    if (
        event_config["activity_time_beta"]
        <= 0
    ):
        raise ValueError(
            "activity_time_beta must be "
            "greater than zero"
        )

    if not (
        0
        < event_config["maturity_exponent"]
        <= 1
    ):
        raise ValueError(
            "maturity_exponent must be in (0, 1]"
        )

    if (
        event_config[
            "minimum_return_gap_minutes"
        ]
        < 0
    ):
        raise ValueError(
            "minimum_return_gap_minutes "
            "must be non-negative"
        )

    feature_gap_min = event_config[
        "feature_gap_seconds_min"
    ]

    feature_gap_max = event_config[
        "feature_gap_seconds_max"
    ]

    if (
        feature_gap_min <= 0
        or feature_gap_max < feature_gap_min
    ):
        raise ValueError(
            "Feature gap settings are invalid"
        )

    paywall_delay_min = event_config[
        "paywall_delay_seconds_min"
    ]

    paywall_delay_max = event_config[
        "paywall_delay_seconds_max"
    ]

    if (
        paywall_delay_min <= 0
        or paywall_delay_max
        < paywall_delay_min
    ):
        raise ValueError(
            "Paywall delay settings are invalid"
        )

    anonymous = event_config[
        "anonymous"
    ]

    _validate_parallel_distribution(
        anonymous["session_counts"],
        anonymous["session_count_weights"],
        "anonymous session count",
    )

    _validate_parallel_distribution(
        anonymous["feature_counts"],
        anonymous["feature_count_weights"],
        "anonymous feature count",
    )

    _validate_probability(
        anonymous[
            "paywall_probability_per_session"
        ],
        (
            "anonymous "
            "paywall_probability_per_session"
        ),
    )

    if (
        anonymous["retention_days_max"]
        <= 0
    ):
        raise ValueError(
            "anonymous retention_days_max "
            "must be greater than zero"
        )

    engagement_weights = event_config[
        "engagement_weights"
    ]

    _validate_weights(
        engagement_weights[
            "onboarding_completed"
        ],
        "onboarding_completed engagement",
    )

    _validate_weights(
        engagement_weights[
            "onboarding_incomplete"
        ],
        "onboarding_incomplete engagement",
    )

    expected_tiers = set(
        engagement_weights[
            "onboarding_completed"
        ]
    )

    if (
        set(
            engagement_weights[
                "onboarding_incomplete"
            ]
        )
        != expected_tiers
    ):
        raise ValueError(
            "Completed and incomplete "
            "engagement tiers must match"
        )

    engagement = event_config[
        "engagement"
    ]

    if set(engagement) != expected_tiers:
        raise ValueError(
            "Engagement settings must match "
            "engagement-weight tiers"
        )

    for tier_name, tier in (
        engagement.items()
    ):

        if (
            tier["session_count_mean"]
            <= 0
        ):
            raise ValueError(
                f"{tier_name} session_count_mean "
                "must be greater than zero"
            )

        if (
            tier["session_count_std"]
            < 0
        ):
            raise ValueError(
                f"{tier_name} session_count_std "
                "must be non-negative"
            )

        if (
            tier["session_count_max"]
            < 1
        ):
            raise ValueError(
                f"{tier_name} session_count_max "
                "must be at least 1"
            )

        if (
            tier["retention_days_median"]
            <= 0
        ):
            raise ValueError(
                f"{tier_name} "
                "retention_days_median "
                "must be positive"
            )

        if (
            tier["retention_days_sigma"]
            < 0
        ):
            raise ValueError(
                f"{tier_name} "
                "retention_days_sigma "
                "must be non-negative"
            )

        if (
            tier[
                "features_per_session_mean"
            ]
            <= 0
        ):
            raise ValueError(
                f"{tier_name} "
                "features_per_session_mean "
                "must be positive"
            )

        if (
            tier[
                "features_per_session_std"
            ]
            < 0
        ):
            raise ValueError(
                f"{tier_name} "
                "features_per_session_std "
                "must be non-negative"
            )

        if (
            tier[
                "features_per_session_max"
            ]
            < 1
        ):
            raise ValueError(
                f"{tier_name} "
                "features_per_session_max "
                "must be at least 1"
            )

        _validate_probability(
            tier[
                "paywall_probability_per_session"
            ],
            (
                f"{tier_name} "
                "paywall_probability_per_session"
            ),
        )

    _validate_weights(
        event_config["feature_mix"],
        "feature_mix",
    )

    return event_config


def _event_row(
    *,
    event_name: str,
    occurred_at: datetime,
    installation: dict[str, Any],
    user_id: str | None,
    session_id: str | None = None,
    feature_name: str | None = None,
) -> dict[str, Any]:
    """Build a product-event row."""

    return {
        "event_id": None,
        "event_name": event_name,
        "occurred_at": occurred_at,
        "installation_id": (
            installation["installation_id"]
        ),
        "anonymous_id": (
            installation["anonymous_id"]
        ),
        "user_id": user_id,
        "session_id": session_id,
        "feature_name": feature_name,
    }


def _identity_for_event(
    user: dict[str, Any] | None,
    occurred_at: datetime,
) -> str | None:
    """
    Return registered identity only from signup onward.

    anonymous_id remains available throughout.
    """

    if user is None:
        return None

    if (
        occurred_at
        < user["signed_up_at"]
    ):
        return None

    return user["user_id"]


def _build_user_map(
    installations: list[dict[str, Any]],
    users: list[dict[str, Any]],
    snapshot_at: datetime,
) -> dict[str, dict[str, Any]]:
    """
    Validate relationships between users and installations.

    One installation may create at most one registered user.
    """

    installations_by_id = {
        row["installation_id"]: row
        for row in installations
    }

    if (
        len(installations_by_id)
        != len(installations)
    ):
        raise ValueError(
            "installation_id values "
            "must be unique"
        )

    users_by_installation: dict[
        str,
        dict[str, Any],
    ] = {}

    for user in users:

        installation_id = user[
            "installation_id"
        ]

        if (
            installation_id
            in users_by_installation
        ):
            raise ValueError(
                "Only one user may be linked "
                "to an installation"
            )

        if (
            installation_id
            not in installations_by_id
        ):
            raise ValueError(
                "User references unknown "
                f"installation: {installation_id}"
            )

        installation = installations_by_id[
            installation_id
        ]

        if (
            user["anonymous_id"]
            != installation["anonymous_id"]
        ):
            raise ValueError(
                "anonymous_id mismatch for "
                f"installation {installation_id}"
            )

        signed_up_at = user[
            "signed_up_at"
        ]

        if (
            signed_up_at
            < installation["installed_at"]
        ):
            raise ValueError(
                "Signup occurs before install "
                f"for {installation_id}"
            )

        if signed_up_at >= snapshot_at:
            raise ValueError(
                "Signup occurs at/after snapshot "
                f"for {installation_id}"
            )

        onboarding_started_at = user[
            "onboarding_started_at"
        ]

        onboarding_completed_at = user[
            "onboarding_completed_at"
        ]

        if (
            onboarding_started_at is not None
            and onboarding_started_at
            < signed_up_at
        ):
            raise ValueError(
                "Onboarding starts before signup "
                f"for {installation_id}"
            )

        if (
            onboarding_completed_at is not None
            and onboarding_started_at is None
        ):
            raise ValueError(
                "Onboarding completes without "
                f"start for {installation_id}"
            )

        if (
            onboarding_completed_at is not None
            and onboarding_completed_at
            < onboarding_started_at
        ):
            raise ValueError(
                "Onboarding completes before "
                f"start for {installation_id}"
            )

        for timestamp in (
            onboarding_started_at,
            onboarding_completed_at,
        ):
            if (
                timestamp is not None
                and timestamp >= snapshot_at
            ):
                raise ValueError(
                    "Lifecycle timestamp occurs "
                    "at/after snapshot for "
                    f"{installation_id}"
                )

        users_by_installation[
            installation_id
        ] = user

    return users_by_installation


def _append_lifecycle_events(
    *,
    events: list[dict[str, Any]],
    installation: dict[str, Any],
    user: dict[str, Any] | None,
) -> None:
    """
    Append lifecycle events from entity timestamps.

    These timestamps are never randomly generated here.
    """

    events.append(
        _event_row(
            event_name="app_install",
            occurred_at=(
                installation["installed_at"]
            ),
            installation=installation,
            user_id=None,
        )
    )

    if user is None:
        return

    events.append(
        _event_row(
            event_name="signup",
            occurred_at=user["signed_up_at"],
            installation=installation,
            user_id=user["user_id"],
        )
    )

    if (
        user["onboarding_started_at"]
        is not None
    ):
        events.append(
            _event_row(
                event_name=(
                    "onboarding_started"
                ),
                occurred_at=(
                    user[
                        "onboarding_started_at"
                    ]
                ),
                installation=installation,
                user_id=user["user_id"],
            )
        )

    if (
        user["onboarding_completed_at"]
        is not None
    ):
        events.append(
            _event_row(
                event_name=(
                    "onboarding_completed"
                ),
                occurred_at=(
                    user[
                        "onboarding_completed_at"
                    ]
                ),
                installation=installation,
                user_id=user["user_id"],
            )
        )


def _choose_engagement_tier(
    *,
    user: dict[str, Any],
    event_config: dict[str, Any],
    rng: random.Random,
) -> str:
    """Assign a latent engagement tier."""

    if (
        user["onboarding_completed_at"]
        is not None
    ):
        group = "onboarding_completed"
    else:
        group = "onboarding_incomplete"

    weights = event_config[
        "engagement_weights"
    ][group]

    names = list(weights)

    probabilities = [
        weights[name]
        for name in names
    ]

    return rng.choices(
        names,
        weights=probabilities,
        k=1,
    )[0]


def _sample_registered_session_count(
    *,
    tier: dict[str, Any],
    available_days: float,
    retention_days: float,
    maturity_exponent: float,
    rng: random.Random,
) -> int:
    """
    Sample total sessions.

    Recent cohorts receive fewer observed sessions because they
    have had less time before the snapshot.
    """

    raw_count = round(
        rng.gauss(
            tier["session_count_mean"],
            tier["session_count_std"],
        )
    )

    raw_count = max(
        1,
        min(
            int(raw_count),
            int(
                tier["session_count_max"]
            ),
        ),
    )

    maturity_fraction = min(
        1.0,
        max(
            0.0,
            available_days
            / retention_days,
        ),
    )

    maturity_multiplier = (
        maturity_fraction
        ** maturity_exponent
    )

    return max(
        1,
        round(
            raw_count
            * maturity_multiplier
        ),
    )


def _build_session_timestamps(
    *,
    installation: dict[str, Any],
    user: dict[str, Any] | None,
    event_config: dict[str, Any],
    engagement_tier: str | None,
    latest_event_at: datetime,
    session_count_rng: random.Random,
    session_timing_rng: random.Random,
) -> list[datetime]:
    """Generate chronologically valid session starts."""

    installed_at = installation[
        "installed_at"
    ]

    available_first_seconds = max(
        0.0,
        (
            latest_event_at
            - installed_at
        ).total_seconds(),
    )

    max_first_delay = int(
        min(
            event_config[
                "first_session_delay_seconds_max"
            ],
            available_first_seconds,
        )
    )

    min_first_delay = int(
        min(
            event_config[
                "first_session_delay_seconds_min"
            ],
            max_first_delay,
        )
    )

    first_delay_seconds = (
        session_timing_rng.randint(
            min_first_delay,
            max_first_delay,
        )
    )

    first_session_at = (
        installed_at
        + timedelta(
            seconds=first_delay_seconds
        )
    )

    if first_session_at > latest_event_at:
        return []

    available_days = max(
        0.0,
        (
            latest_event_at
            - first_session_at
        ).total_seconds()
        / 86_400,
    )

    if user is None:

        anonymous = event_config[
            "anonymous"
        ]

        requested_count = (
            session_count_rng.choices(
                anonymous["session_counts"],
                weights=anonymous[
                    "session_count_weights"
                ],
                k=1,
            )[0]
        )

        retention_days = min(
            float(
                anonymous[
                    "retention_days_max"
                ]
            ),
            available_days,
        )

    else:

        tier = event_config[
            "engagement"
        ][engagement_tier]

        retention_days = (
            session_count_rng.lognormvariate(
                log(
                    tier[
                        "retention_days_median"
                    ]
                ),
                tier[
                    "retention_days_sigma"
                ],
            )
        )

        requested_count = (
            _sample_registered_session_count(
                tier=tier,
                available_days=available_days,
                retention_days=retention_days,
                maturity_exponent=(
                    event_config[
                        "maturity_exponent"
                    ]
                ),
                rng=session_count_rng,
            )
        )

        retention_days = min(
            retention_days,
            available_days,
        )

    if (
        requested_count <= 1
        or retention_days <= 0
    ):
        return [
            first_session_at
        ]

    active_window_seconds = max(
        1,
        int(
            retention_days
            * 86_400
        ),
    )

    candidates = []

    for _ in range(
        requested_count - 1
    ):

        activity_fraction = (
            session_timing_rng.betavariate(
                event_config[
                    "activity_time_alpha"
                ],
                event_config[
                    "activity_time_beta"
                ],
            )
        )

        offset_seconds = max(
            1,
            int(
                activity_fraction
                * active_window_seconds
            ),
        )

        candidates.append(
            first_session_at
            + timedelta(
                seconds=offset_seconds
            )
        )

    candidates.sort()

    minimum_gap = timedelta(
        minutes=event_config[
            "minimum_return_gap_minutes"
        ]
    )

    sessions = [
        first_session_at
    ]

    for candidate in candidates:

        minimum_allowed = (
            sessions[-1]
            + minimum_gap
        )

        candidate = max(
            candidate,
            minimum_allowed,
        )

        if candidate > latest_event_at:
            break

        sessions.append(
            candidate
        )

    return sessions


def _feature_count_for_session(
    *,
    user: dict[str, Any] | None,
    event_config: dict[str, Any],
    engagement_tier: str | None,
    rng: random.Random,
) -> int:
    """Sample feature interactions within one session."""

    if user is None:

        anonymous = event_config[
            "anonymous"
        ]

        return int(
            rng.choices(
                anonymous[
                    "feature_counts"
                ],
                weights=anonymous[
                    "feature_count_weights"
                ],
                k=1,
            )[0]
        )

    tier = event_config[
        "engagement"
    ][engagement_tier]

    count = round(
        rng.gauss(
            tier[
                "features_per_session_mean"
            ],
            tier[
                "features_per_session_std"
            ],
        )
    )

    return max(
        1,
        min(
            int(count),
            int(
                tier[
                    "features_per_session_max"
                ]
            ),
        ),
    )


def _paywall_probability(
    *,
    user: dict[str, Any] | None,
    event_config: dict[str, Any],
    engagement_tier: str | None,
) -> float:
    """Return the paywall probability for a session."""

    if user is None:
        return float(
            event_config[
                "anonymous"
            ][
                "paywall_probability_per_session"
            ]
        )

    return float(
        event_config[
            "engagement"
        ][engagement_tier][
            "paywall_probability_per_session"
        ]
    )


def _append_behavioral_events(
    *,
    events: list[dict[str, Any]],
    installation: dict[str, Any],
    user: dict[str, Any] | None,
    event_config: dict[str, Any],
    engagement_tier: str | None,
    latest_event_at: datetime,
    session_timestamps: list[datetime],
    feature_count_rng: random.Random,
    feature_name_rng: random.Random,
    feature_timing_rng: random.Random,
    paywall_occurrence_rng: random.Random,
    paywall_timing_rng: random.Random,
) -> None:
    """Append session, feature-use and paywall events."""

    feature_mix = event_config[
        "feature_mix"
    ]

    feature_names = list(
        feature_mix
    )

    feature_weights = [
        feature_mix[name]
        for name in feature_names
    ]

    installation_suffix = (
        installation[
            "installation_id"
        ].removeprefix(
            "inst_"
        )
    )

    for session_number, session_at in (
        enumerate(
            session_timestamps,
            start=1,
        )
    ):

        session_id = (
            f"sess_"
            f"{installation_suffix}_"
            f"{session_number:04d}"
        )

        events.append(
            _event_row(
                event_name=(
                    "session_started"
                ),
                occurred_at=session_at,
                installation=installation,
                user_id=(
                    _identity_for_event(
                        user,
                        session_at,
                    )
                ),
                session_id=session_id,
            )
        )

        feature_count = (
            _feature_count_for_session(
                user=user,
                event_config=event_config,
                engagement_tier=(
                    engagement_tier
                ),
                rng=feature_count_rng,
            )
        )

        feature_times = []

        elapsed_seconds = 0

        for _ in range(
            feature_count
        ):

            elapsed_seconds += (
                feature_timing_rng.randint(
                    event_config[
                        "feature_gap_seconds_min"
                    ],
                    event_config[
                        "feature_gap_seconds_max"
                    ],
                )
            )

            feature_at = (
                session_at
                + timedelta(
                    seconds=(
                        elapsed_seconds
                    )
                )
            )

            if (
                feature_at
                > latest_event_at
            ):
                break

            feature_name = (
                feature_name_rng.choices(
                    feature_names,
                    weights=feature_weights,
                    k=1,
                )[0]
            )

            feature_times.append(
                feature_at
            )

            events.append(
                _event_row(
                    event_name=(
                        "feature_used"
                    ),
                    occurred_at=feature_at,
                    installation=installation,
                    user_id=(
                        _identity_for_event(
                            user,
                            feature_at,
                        )
                    ),
                    session_id=session_id,
                    feature_name=(
                        feature_name
                    ),
                )
            )

        probability = (
            _paywall_probability(
                user=user,
                event_config=event_config,
                engagement_tier=(
                    engagement_tier
                ),
            )
        )

        if (
            paywall_occurrence_rng.random()
            >= probability
        ):
            continue

        paywall_at = (
            session_at
            + timedelta(
                seconds=(
                    paywall_timing_rng.randint(
                        event_config[
                            "paywall_delay_seconds_min"
                        ],
                        event_config[
                            "paywall_delay_seconds_max"
                        ],
                    )
                )
            )
        )

        if feature_times:

            paywall_at = max(
                paywall_at,
                (
                    feature_times[-1]
                    + timedelta(
                        seconds=10
                    )
                ),
            )

        if paywall_at > latest_event_at:
            continue

        events.append(
            _event_row(
                event_name=(
                    "paywall_viewed"
                ),
                occurred_at=paywall_at,
                installation=installation,
                user_id=(
                    _identity_for_event(
                        user,
                        paywall_at,
                    )
                ),
                session_id=session_id,
            )
        )


def generate_product_events(
    installations: list[dict[str, Any]],
    users: list[dict[str, Any]],
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> list[dict[str, Any]]:
    """
    Generate deterministic lifecycle and behavioural events.

    Lifecycle timestamps are copied exactly from installations/users.
    Randomness is used only for behavioural activity.
    """

    if not installations:
        return []

    event_config = (
        load_product_event_config(
            config_path
        )
    )

    snapshot_at = get_snapshot_at(
        config_path
    )

    latest_event_at = (
        snapshot_at
        - timedelta(
            microseconds=1
        )
    )

    users_by_installation = (
        _build_user_map(
            installations=installations,
            users=users,
            snapshot_at=snapshot_at,
        )
    )

    engagement_rng = random.Random(
        get_substream_seed(
            "product_events",
            "engagement_tier",
        )
    )

    session_count_rng = random.Random(
        get_substream_seed(
            "product_events",
            "session_count",
        )
    )

    session_timing_rng = random.Random(
        get_substream_seed(
            "product_events",
            "session_timing",
        )
    )

    feature_count_rng = random.Random(
        get_substream_seed(
            "product_events",
            "feature_count",
        )
    )

    feature_name_rng = random.Random(
        get_substream_seed(
            "product_events",
            "feature_name",
        )
    )

    feature_timing_rng = random.Random(
        get_substream_seed(
            "product_events",
            "feature_timing",
        )
    )

    paywall_occurrence_rng = (
        random.Random(
            get_substream_seed(
                "product_events",
                "paywall_occurrence",
            )
        )
    )

    paywall_timing_rng = random.Random(
        get_substream_seed(
            "product_events",
            "paywall_timing",
        )
    )

    events: list[
        dict[str, Any]
    ] = []

    for installation in installations:

        if (
            installation["installed_at"]
            >= snapshot_at
        ):
            raise ValueError(
                "Installation occurs at/after "
                "the dataset snapshot"
            )

        user = (
            users_by_installation.get(
                installation[
                    "installation_id"
                ]
            )
        )

        _append_lifecycle_events(
            events=events,
            installation=installation,
            user=user,
        )

        if user is None:
            engagement_tier = None
        else:
            engagement_tier = (
                _choose_engagement_tier(
                    user=user,
                    event_config=event_config,
                    rng=engagement_rng,
                )
            )

        session_timestamps = (
            _build_session_timestamps(
                installation=installation,
                user=user,
                event_config=event_config,
                engagement_tier=(
                    engagement_tier
                ),
                latest_event_at=(
                    latest_event_at
                ),
                session_count_rng=(
                    session_count_rng
                ),
                session_timing_rng=(
                    session_timing_rng
                ),
            )
        )

        _append_behavioral_events(
            events=events,
            installation=installation,
            user=user,
            event_config=event_config,
            engagement_tier=(
                engagement_tier
            ),
            latest_event_at=(
                latest_event_at
            ),
            session_timestamps=(
                session_timestamps
            ),
            feature_count_rng=(
                feature_count_rng
            ),
            feature_name_rng=(
                feature_name_rng
            ),
            feature_timing_rng=(
                feature_timing_rng
            ),
            paywall_occurrence_rng=(
                paywall_occurrence_rng
            ),
            paywall_timing_rng=(
                paywall_timing_rng
            ),
        )

    events.sort(
        key=lambda row: (
            row["occurred_at"],
            row["installation_id"],
            EVENT_SORT_PRIORITY[
                row["event_name"]
            ],
            row["session_id"] or "",
            row["feature_name"] or "",
        )
    )

    for event_number, event in (
        enumerate(
            events,
            start=1,
        )
    ):
        event["event_id"] = (
            f"evt_{event_number:010d}"
        )

    return events