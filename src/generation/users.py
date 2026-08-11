"""Synthetic registered-user and onboarding lifecycle generation for Pulse."""

from datetime import datetime, timedelta, timezone
from math import isclose
from pathlib import Path
import random

from src.generation.installations import (
    DEFAULT_SIMULATION_CONFIG,
    load_installation_dimensions,
    load_simulation_config,
)
from src.generation.randomness import get_substream_seed


def _validate_probability(value: float, name: str) -> float:
    """Validate and return a probability in the inclusive range [0, 1]."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")

    value = float(value)

    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")

    return value


def _validate_adjustments(
    adjustments: dict,
    dimension_values: dict,
    name: str,
) -> dict:
    """Validate probability adjustments against known dimension values."""
    validated = {}

    for dimension_name, values_to_adjustments in adjustments.items():
        if dimension_name not in dimension_values:
            raise ValueError(
                "Unknown lifecycle adjustment dimension: "
                f"{dimension_name}"
            )

        known_values = dimension_values[dimension_name]
        configured_values = set(values_to_adjustments)

        unknown_values = configured_values - known_values

        if unknown_values:
            raise ValueError(
                f"{name}.{dimension_name} contains "
                f"unknown values: {sorted(unknown_values)}"
            )

        validated_values = {}

        for dimension_value, adjustment in values_to_adjustments.items():
            if not isinstance(adjustment, (int, float)):
                raise TypeError(
                    f"{name}.{dimension_name}."
                    f"{dimension_value} must be numeric"
                )

            validated_values[dimension_value] = float(adjustment)

        validated[dimension_name] = validated_values

    return validated


def _validate_delay_distribution(
    distribution: dict,
    name: str,
) -> dict:
    """Validate weighted inclusive whole-minute delay ranges."""
    ranges = tuple(
        tuple(value)
        for value in distribution["ranges"]
    )

    weights = tuple(
        float(value)
        for value in distribution["weights"]
    )

    if not ranges:
        raise ValueError(
            f"{name} must contain at least one range"
        )

    if len(ranges) != len(weights):
        raise ValueError(
            f"{name} ranges and weights must have equal length"
        )

    for delay_range in ranges:
        if len(delay_range) != 2:
            raise ValueError(
                f"Every {name} range must contain [minimum, maximum]"
            )

        minimum, maximum = delay_range

        if not isinstance(minimum, int) or not isinstance(maximum, int):
            raise TypeError(
                f"{name} ranges must use whole minutes"
            )

        if minimum < 0 or maximum < minimum:
            raise ValueError(
                f"Invalid {name} range: {delay_range}"
            )

    if any(weight < 0 for weight in weights):
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

    return {
        "ranges": ranges,
        "weights": weights,
    }


def load_user_lifecycle_config(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict:
    """Load and validate registered-user lifecycle assumptions."""
    config = load_simulation_config(config_path)

    lifecycle = config["user_lifecycle"]

    installation_dimensions = load_installation_dimensions(
        config_path
    )

    dimension_values = {
        name: set(dimension["values"])
        for name, dimension in installation_dimensions.items()
    }

    signup_probability = _validate_probability(
        lifecycle["signup_probability"],
        "signup_probability",
    )

    onboarding_start_probability = _validate_probability(
        lifecycle[
            "onboarding_start_given_signup_probability"
        ],
        "onboarding_start_given_signup_probability",
    )

    onboarding_complete_probability = _validate_probability(
        lifecycle[
            "onboarding_complete_given_start_probability"
        ],
        "onboarding_complete_given_start_probability",
    )

    signup_adjustments = _validate_adjustments(
        lifecycle.get(
            "signup_probability_adjustments",
            {},
        ),
        dimension_values,
        "signup_probability_adjustments",
    )

    onboarding_start_adjustments = _validate_adjustments(
        lifecycle.get(
            "onboarding_start_probability_adjustments",
            {},
        ),
        dimension_values,
        "onboarding_start_probability_adjustments",
    )

    onboarding_complete_adjustments = _validate_adjustments(
        lifecycle.get(
            "onboarding_complete_probability_adjustments",
            {},
        ),
        dimension_values,
        "onboarding_complete_probability_adjustments",
    )

    probability_specs = (
        (
            "signup_probability",
            signup_probability,
            signup_adjustments,
        ),
        (
            "onboarding_start_given_signup_probability",
            onboarding_start_probability,
            onboarding_start_adjustments,
        ),
        (
            "onboarding_complete_given_start_probability",
            onboarding_complete_probability,
            onboarding_complete_adjustments,
        ),
    )

    for (
        probability_name,
        base_probability,
        adjustments,
    ) in probability_specs:
        minimum_probability = base_probability
        maximum_probability = base_probability

        for values_to_adjustments in adjustments.values():
            values = tuple(values_to_adjustments.values())

            if values:
                minimum_probability += min(
                    0.0,
                    min(values),
                )

                maximum_probability += max(
                    0.0,
                    max(values),
                )

        if (
            minimum_probability < 0.0
            or maximum_probability > 1.0
        ):
            raise ValueError(
                "Configured adjustments can push "
                f"{probability_name} outside [0, 1]"
            )

    return {
        "signup_probability": signup_probability,
        "onboarding_start_given_signup_probability": (
            onboarding_start_probability
        ),
        "onboarding_complete_given_start_probability": (
            onboarding_complete_probability
        ),
        "signup_probability_adjustments": signup_adjustments,
        "onboarding_start_probability_adjustments": (
            onboarding_start_adjustments
        ),
        "onboarding_complete_probability_adjustments": (
            onboarding_complete_adjustments
        ),
        "signup_delay_minutes": _validate_delay_distribution(
            lifecycle["signup_delay_minutes"],
            "signup_delay_minutes",
        ),
        "onboarding_start_delay_minutes": (
            _validate_delay_distribution(
                lifecycle[
                    "onboarding_start_delay_minutes"
                ],
                "onboarding_start_delay_minutes",
            )
        ),
        "onboarding_complete_delay_minutes": (
            _validate_delay_distribution(
                lifecycle[
                    "onboarding_complete_delay_minutes"
                ],
                "onboarding_complete_delay_minutes",
            )
        ),
    }


def _get_snapshot_at(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> datetime:
    """Return the configured UTC dataset snapshot timestamp."""
    config = load_simulation_config(config_path)

    snapshot_text = (
        config["simulation"]["snapshot_at"]
        .replace("Z", "+00:00")
    )

    snapshot_at = datetime.fromisoformat(snapshot_text)

    if snapshot_at.tzinfo is None:
        snapshot_at = snapshot_at.replace(
            tzinfo=timezone.utc
        )

    return snapshot_at


def _adjusted_probability(
    base_probability: float,
    adjustments: dict,
    installation: dict,
) -> float:
    """Apply additive dimension adjustments to a base probability."""
    probability = base_probability

    for (
        dimension_name,
        values_to_adjustments,
    ) in adjustments.items():
        probability += values_to_adjustments.get(
            installation[dimension_name],
            0.0,
        )

    return probability


def _sample_delay_minutes(
    distribution: dict,
    bucket_rng: random.Random,
    value_rng: random.Random,
) -> int:
    """Sample an inclusive whole-minute delay from weighted buckets."""
    selected_range = bucket_rng.choices(
        distribution["ranges"],
        weights=distribution["weights"],
        k=1,
    )[0]

    minimum, maximum = selected_range

    return value_rng.randint(
        minimum,
        maximum,
    )


def generate_users(
    installations: list[dict],
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> list[dict]:
    """
    Generate registered users and onboarding milestone timestamps.

    Only installations that have signed up by the configured snapshot
    become rows in the users entity.

    Installations that never sign up, or whose sampled signup occurs
    after the snapshot, remain anonymous visitors.
    """
    if not isinstance(installations, list):
        raise TypeError(
            "installations must be a list"
        )

    lifecycle = load_user_lifecycle_config(
        config_path
    )

    snapshot_at = _get_snapshot_at(
        config_path
    )

    signup_decision_rng = random.Random(
        get_substream_seed(
            "users",
            "signup_decision",
        )
    )

    signup_bucket_rng = random.Random(
        get_substream_seed(
            "users",
            "signup_delay_bucket",
        )
    )

    signup_delay_rng = random.Random(
        get_substream_seed(
            "users",
            "signup_delay_value",
        )
    )

    onboarding_start_decision_rng = random.Random(
        get_substream_seed(
            "users",
            "onboarding_start_decision",
        )
    )

    onboarding_start_bucket_rng = random.Random(
        get_substream_seed(
            "users",
            "onboarding_start_delay_bucket",
        )
    )

    onboarding_start_delay_rng = random.Random(
        get_substream_seed(
            "users",
            "onboarding_start_delay_value",
        )
    )

    onboarding_complete_decision_rng = random.Random(
        get_substream_seed(
            "users",
            "onboarding_complete_decision",
        )
    )

    onboarding_complete_bucket_rng = random.Random(
        get_substream_seed(
            "users",
            "onboarding_complete_delay_bucket",
        )
    )

    onboarding_complete_delay_rng = random.Random(
        get_substream_seed(
            "users",
            "onboarding_complete_delay_value",
        )
    )

    users = []

    for installation in installations:
        required_fields = (
            "installation_id",
            "anonymous_id",
            "installed_at",
            "platform",
            "acquisition_channel",
            "country_code",
        )

        missing_fields = [
            field
            for field in required_fields
            if field not in installation
        ]

        if missing_fields:
            raise ValueError(
                "Installation is missing required fields: "
                f"{missing_fields}"
            )

        installed_at = installation["installed_at"]

        if not isinstance(installed_at, datetime):
            raise TypeError(
                "installed_at must be a datetime"
            )

        if installed_at.tzinfo is None:
            raise ValueError(
                "installed_at must be timezone-aware"
            )

        signup_probability = _adjusted_probability(
            lifecycle["signup_probability"],
            lifecycle[
                "signup_probability_adjustments"
            ],
            installation,
        )

        if (
            signup_decision_rng.random()
            >= signup_probability
        ):
            continue

        signup_delay = _sample_delay_minutes(
            lifecycle["signup_delay_minutes"],
            signup_bucket_rng,
            signup_delay_rng,
        )

        signed_up_at = (
            installed_at
            + timedelta(minutes=signup_delay)
        )

        # Right censoring at the dataset snapshot.
        # The installation may eventually sign up, but has not
        # done so yet within the dataset observation period.
        if signed_up_at >= snapshot_at:
            continue

        onboarding_started_at = None
        onboarding_completed_at = None

        start_probability = _adjusted_probability(
            lifecycle[
                "onboarding_start_given_signup_probability"
            ],
            lifecycle[
                "onboarding_start_probability_adjustments"
            ],
            installation,
        )

        if (
            onboarding_start_decision_rng.random()
            < start_probability
        ):
            start_delay = _sample_delay_minutes(
                lifecycle[
                    "onboarding_start_delay_minutes"
                ],
                onboarding_start_bucket_rng,
                onboarding_start_delay_rng,
            )

            candidate_started_at = (
                signed_up_at
                + timedelta(minutes=start_delay)
            )

            if candidate_started_at < snapshot_at:
                onboarding_started_at = (
                    candidate_started_at
                )

                completion_probability = (
                    _adjusted_probability(
                        lifecycle[
                            "onboarding_complete_given_start_probability"
                        ],
                        lifecycle[
                            "onboarding_complete_probability_adjustments"
                        ],
                        installation,
                    )
                )

                if (
                    onboarding_complete_decision_rng.random()
                    < completion_probability
                ):
                    completion_delay = (
                        _sample_delay_minutes(
                            lifecycle[
                                "onboarding_complete_delay_minutes"
                            ],
                            onboarding_complete_bucket_rng,
                            onboarding_complete_delay_rng,
                        )
                    )

                    candidate_completed_at = (
                        onboarding_started_at
                        + timedelta(
                            minutes=completion_delay
                        )
                    )

                    if (
                        candidate_completed_at
                        < snapshot_at
                    ):
                        onboarding_completed_at = (
                            candidate_completed_at
                        )

        users.append(
            {
                "user_id": (
                    f"user_{len(users) + 1:08d}"
                ),
                "installation_id": (
                    installation[
                        "installation_id"
                    ]
                ),
                "anonymous_id": (
                    installation[
                        "anonymous_id"
                    ]
                ),
                "signed_up_at": signed_up_at,
                "onboarding_started_at": (
                    onboarding_started_at
                ),
                "onboarding_completed_at": (
                    onboarding_completed_at
                ),
            }
        )

    users.sort(
        key=lambda row: row["signed_up_at"]
    )

    return users
