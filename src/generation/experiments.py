"""Synthetic product-experiment assignment generation for Pulse."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import isclose
from pathlib import Path
import random
from typing import Any

from src.generation.installations import (
    DEFAULT_SIMULATION_CONFIG,
    load_simulation_config,
)
from src.generation.randomness import get_substream_seed


ALLOWED_ELIGIBILITY_RULES = {
    "paywall_viewers",
    "new_signups",
    "onboarded_session_users",
}

RULE_TRIGGER_EXPECTATIONS = {
    "paywall_viewers": (
        "paywall_viewed",
        "paywall_viewed",
    ),
    "new_signups": (
        "signup",
        "onboarding_started",
    ),
    "onboarded_session_users": (
        "session_started",
        "session_started",
    ),
}

EXPECTED_VARIANTS = {
    "control",
    "treatment",
}


def _parse_utc_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp as a timezone-aware UTC datetime."""
    timestamp = datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(
            tzinfo=timezone.utc
        )

    return timestamp.astimezone(timezone.utc)


def get_experiment_snapshot_at(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> datetime:
    """Return the configured dataset snapshot timestamp."""
    config = load_simulation_config(config_path)

    return _parse_utc_timestamp(
        config["simulation"]["snapshot_at"]
    )


def _validate_non_empty_string(
    value: Any,
    name: str,
) -> str:
    """Validate and return a non-empty string."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")

    if not value.strip():
        raise ValueError(
            f"{name} must be a non-empty string"
        )

    return value


def _validate_allocation(
    variants: list[str],
    allocation: list[Any],
    experiment_id: str,
) -> list[float]:
    """Validate experiment allocation probabilities."""
    if not isinstance(allocation, list):
        raise TypeError(
            f"{experiment_id}.allocation must be a list"
        )

    if len(allocation) != len(variants):
        raise ValueError(
            f"{experiment_id}.allocation must have "
            "one probability per variant"
        )

    validated: list[float] = []

    for probability in allocation:
        if not isinstance(
            probability,
            (int, float),
        ):
            raise TypeError(
                f"{experiment_id}.allocation values "
                "must be numeric"
            )

        probability = float(probability)

        if probability <= 0.0:
            raise ValueError(
                f"{experiment_id}.allocation values "
                "must be greater than zero"
            )

        validated.append(probability)

    if not isclose(
        sum(validated),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(
            f"{experiment_id}.allocation must sum to 1"
        )

    return validated


def load_experiment_config(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict[str, Any]:
    """
    Load and validate product-experiment configuration.

    Returned experiment start/end values are converted to UTC datetimes.
    """
    config = load_simulation_config(config_path)

    if "experiments" not in config:
        raise ValueError(
            "simulation.toml is missing [experiments]"
        )

    experiment_config = config["experiments"]

    definitions = experiment_config.get(
        "definitions"
    )

    if not isinstance(definitions, list):
        raise TypeError(
            "experiments.definitions must be a list"
        )

    if not definitions:
        raise ValueError(
            "experiments.definitions must not be empty"
        )

    snapshot_at = get_experiment_snapshot_at(
        config_path
    )

    seen_experiment_ids: set[str] = set()
    validated_definitions: list[
        dict[str, Any]
    ] = []

    required_string_fields = (
        "experiment_id",
        "experiment_name",
        "eligibility_rule",
        "assignment_trigger",
        "exposure_trigger",
        "hypothesis",
        "primary_metric",
        "secondary_metric",
        "commercial_metric",
        "guardrail_metric",
        "randomization_unit",
    )

    for definition in definitions:
        if not isinstance(definition, dict):
            raise TypeError(
                "Each experiment definition must "
                "be a table"
            )

        for field in required_string_fields:
            if field not in definition:
                raise ValueError(
                    f"Experiment is missing: {field}"
                )

            _validate_non_empty_string(
                definition[field],
                field,
            )

        experiment_id = definition[
            "experiment_id"
        ]

        if experiment_id in seen_experiment_ids:
            raise ValueError(
                f"Duplicate experiment_id: "
                f"{experiment_id}"
            )

        seen_experiment_ids.add(
            experiment_id
        )

        if (
            definition["randomization_unit"]
            != "user"
        ):
            raise ValueError(
                f"{experiment_id}.randomization_unit "
                "must be 'user'"
            )

        eligibility_rule = definition[
            "eligibility_rule"
        ]

        if (
            eligibility_rule
            not in ALLOWED_ELIGIBILITY_RULES
        ):
            raise ValueError(
                f"Unsupported eligibility_rule: "
                f"{eligibility_rule}"
            )

        expected_assignment_trigger, (
            expected_exposure_trigger
        ) = RULE_TRIGGER_EXPECTATIONS[
            eligibility_rule
        ]

        if (
            definition["assignment_trigger"]
            != expected_assignment_trigger
        ):
            raise ValueError(
                f"{experiment_id}.assignment_trigger "
                f"must be "
                f"{expected_assignment_trigger}"
            )

        if (
            definition["exposure_trigger"]
            != expected_exposure_trigger
        ):
            raise ValueError(
                f"{experiment_id}.exposure_trigger "
                f"must be "
                f"{expected_exposure_trigger}"
            )

        if "start_at" not in definition:
            raise ValueError(
                f"{experiment_id} is missing start_at"
            )

        if "end_at" not in definition:
            raise ValueError(
                f"{experiment_id} is missing end_at"
            )

        start_at = _parse_utc_timestamp(
            definition["start_at"]
        )
        end_at = _parse_utc_timestamp(
            definition["end_at"]
        )

        if start_at >= end_at:
            raise ValueError(
                f"{experiment_id}.start_at must "
                "be before end_at"
            )

        if end_at > snapshot_at:
            raise ValueError(
                f"{experiment_id}.end_at must not "
                "be after the dataset snapshot"
            )

        variants = definition.get("variants")

        if not isinstance(variants, list):
            raise TypeError(
                f"{experiment_id}.variants "
                "must be a list"
            )

        if len(variants) != 2:
            raise ValueError(
                f"{experiment_id} must have exactly "
                "two variants"
            )

        if set(variants) != EXPECTED_VARIANTS:
            raise ValueError(
                f"{experiment_id}.variants must "
                "contain control and treatment"
            )

        allocation = _validate_allocation(
            variants,
            definition.get("allocation"),
            experiment_id,
        )

        analysis_window_days = definition.get(
            "analysis_window_days"
        )

        if (
            not isinstance(
                analysis_window_days,
                int,
            )
            or analysis_window_days <= 0
        ):
            raise ValueError(
                f"{experiment_id}."
                "analysis_window_days must be "
                "a positive integer"
            )

        validated = dict(definition)

        validated["start_at"] = start_at
        validated["end_at"] = end_at
        validated["allocation"] = allocation

        validated_definitions.append(
            validated
        )

    return {
        "definitions": validated_definitions,
    }


def _validate_users(
    users: list[dict[str, Any]],
    snapshot_at: datetime,
) -> dict[str, dict[str, Any]]:
    """Validate registered-user inputs."""
    if not isinstance(users, list):
        raise TypeError(
            "users must be a list"
        )

    required_fields = {
        "user_id",
        "installation_id",
        "anonymous_id",
        "signed_up_at",
        "onboarding_started_at",
        "onboarding_completed_at",
    }

    users_by_id: dict[
        str,
        dict[str, Any],
    ] = {}

    installation_ids: set[str] = set()

    for user in users:
        missing = sorted(
            required_fields - set(user)
        )

        if missing:
            raise ValueError(
                "User is missing required fields: "
                f"{missing}"
            )

        user_id = user["user_id"]
        installation_id = user[
            "installation_id"
        ]

        if not isinstance(user_id, str):
            raise TypeError(
                "user_id must be a string"
            )

        if user_id in users_by_id:
            raise ValueError(
                f"Duplicate user_id: {user_id}"
            )

        if installation_id in installation_ids:
            raise ValueError(
                "Only one registered user may be "
                "linked to an installation"
            )

        signed_up_at = user["signed_up_at"]

        if not isinstance(
            signed_up_at,
            datetime,
        ):
            raise TypeError(
                "signed_up_at must be a datetime"
            )

        if signed_up_at.tzinfo is None:
            raise ValueError(
                "signed_up_at must be timezone-aware"
            )

        if signed_up_at >= snapshot_at:
            raise ValueError(
                "signed_up_at must be before "
                "the snapshot"
            )

        for field in (
            "onboarding_started_at",
            "onboarding_completed_at",
        ):
            value = user[field]

            if value is None:
                continue

            if not isinstance(
                value,
                datetime,
            ):
                raise TypeError(
                    f"{field} must be a datetime "
                    "or None"
                )

            if value.tzinfo is None:
                raise ValueError(
                    f"{field} must be "
                    "timezone-aware"
                )

            if value >= snapshot_at:
                raise ValueError(
                    f"{field} must be before "
                    "the snapshot"
                )

        users_by_id[user_id] = user
        installation_ids.add(
            installation_id
        )

    return users_by_id


def _build_event_index(
    product_events: list[dict[str, Any]],
    users_by_id: dict[str, dict[str, Any]],
    snapshot_at: datetime,
) -> dict[str, dict[str, list[datetime]]]:
    """
    Index registered paywall and session events.

    Source product-event rows are never modified.
    """
    if not isinstance(product_events, list):
        raise TypeError(
            "product_events must be a list"
        )

    profiles: dict[
        str,
        dict[str, list[datetime]],
    ] = {
        user_id: {
            "paywall_viewed": [],
            "session_started": [],
        }
        for user_id in users_by_id
    }

    for event in product_events:
        user_id = event.get("user_id")

        if user_id is None:
            continue

        if user_id not in users_by_id:
            raise ValueError(
                "Product event references unknown "
                f"registered user: {user_id}"
            )

        occurred_at = event.get(
            "occurred_at"
        )

        if not isinstance(
            occurred_at,
            datetime,
        ):
            raise TypeError(
                "product event occurred_at "
                "must be a datetime"
            )

        if occurred_at.tzinfo is None:
            raise ValueError(
                "product event occurred_at must "
                "be timezone-aware"
            )

        if occurred_at >= snapshot_at:
            raise ValueError(
                "product event occurs at/after "
                "the snapshot"
            )

        event_name = event.get(
            "event_name"
        )

        if event_name in (
            "paywall_viewed",
            "session_started",
        ):
            profiles[user_id][
                event_name
            ].append(
                occurred_at
            )

    for profile in profiles.values():
        profile["paywall_viewed"].sort()
        profile["session_started"].sort()

    return profiles


def _first_timestamp_in_window(
    timestamps: list[datetime],
    earliest_at: datetime,
    end_at: datetime,
) -> datetime | None:
    """Return the first timestamp in [earliest_at, end_at)."""
    for timestamp in timestamps:
        if timestamp < earliest_at:
            continue

        if timestamp >= end_at:
            break

        return timestamp

    return None


def _assignment_candidate(
    *,
    definition: dict[str, Any],
    user: dict[str, Any],
    profile: dict[str, list[datetime]],
) -> tuple[
    datetime,
    datetime | None,
] | None:
    """Return assignment/exposure timestamps for an eligible user."""
    start_at = definition["start_at"]
    end_at = definition["end_at"]
    eligibility_rule = definition[
        "eligibility_rule"
    ]

    signed_up_at = user["signed_up_at"]

    if eligibility_rule == "new_signups":
        if not (
            start_at
            <= signed_up_at
            < end_at
        ):
            return None

        assignment_at = signed_up_at

        onboarding_started_at = user[
            "onboarding_started_at"
        ]

        exposed_at: datetime | None = None

        if (
            onboarding_started_at is not None
            and assignment_at
            <= onboarding_started_at
            < end_at
        ):
            exposed_at = onboarding_started_at

        return (
            assignment_at,
            exposed_at,
        )

    if eligibility_rule == "paywall_viewers":
        earliest_at = max(
            start_at,
            signed_up_at,
        )

        paywall_at = _first_timestamp_in_window(
            profile["paywall_viewed"],
            earliest_at,
            end_at,
        )

        if paywall_at is None:
            return None

        return (
            paywall_at,
            paywall_at,
        )

    if (
        eligibility_rule
        == "onboarded_session_users"
    ):
        onboarding_completed_at = user[
            "onboarding_completed_at"
        ]

        if onboarding_completed_at is None:
            return None

        earliest_at = max(
            start_at,
            signed_up_at,
            onboarding_completed_at,
        )

        session_at = _first_timestamp_in_window(
            profile["session_started"],
            earliest_at,
            end_at,
        )

        if session_at is None:
            return None

        return (
            session_at,
            session_at,
        )

    raise RuntimeError(
        "Unexpected eligibility rule: "
        f"{eligibility_rule}"
    )


def _choose_variant(
    *,
    definition: dict[str, Any],
    user_id: str,
) -> tuple[str, float]:
    """
    Deterministically randomise one user.

    Each experiment/user pair receives its own named deterministic seed. This
    means the assignment does not depend on list ordering or dataset scale.
    """
    experiment_id = definition[
        "experiment_id"
    ]

    seed_name = (
        f"{experiment_id}:"
        f"variant_assignment:"
        f"{user_id}"
    )

    rng = random.Random(
        get_substream_seed(
            "experiments",
            seed_name,
        )
    )

    draw = rng.random()

    cumulative_probability = 0.0

    for variant, probability in zip(
        definition["variants"],
        definition["allocation"],
        strict=True,
    ):
        cumulative_probability += float(
            probability
        )

        if draw < cumulative_probability:
            return (
                variant,
                float(probability),
            )

    # Protect against floating-point edge cases.
    return (
        definition["variants"][-1],
        float(
            definition["allocation"][-1]
        ),
    )


def _assignment_id(
    experiment_id: str,
    user_id: str,
) -> str:
    """Return a stable assignment identifier."""
    return (
        f"asgn_{experiment_id}_{user_id}"
    )


def generate_experiment_assignments(
    users: list[dict[str, Any]],
    product_events: list[dict[str, Any]],
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> list[dict[str, Any]]:
    """
    Generate deterministic user-level experiment assignments.

    Existing user and product-event rows are treated as read-only inputs.
    """
    experiment_config = (
        load_experiment_config(
            config_path
        )
    )

    snapshot_at = (
        get_experiment_snapshot_at(
            config_path
        )
    )

    users_by_id = _validate_users(
        users,
        snapshot_at,
    )

    event_index = _build_event_index(
        product_events,
        users_by_id,
        snapshot_at,
    )

    assignments: list[
        dict[str, Any]
    ] = []

    seen_pairs: set[
        tuple[str, str]
    ] = set()

    for definition in experiment_config[
        "definitions"
    ]:
        experiment_id = definition[
            "experiment_id"
        ]

        candidates: list[
            tuple[
                datetime,
                str,
                datetime | None,
            ]
        ] = []

        for user_id, user in (
            users_by_id.items()
        ):
            candidate = _assignment_candidate(
                definition=definition,
                user=user,
                profile=event_index[
                    user_id
                ],
            )

            if candidate is None:
                continue

            assignment_at, exposed_at = (
                candidate
            )

            candidates.append(
                (
                    assignment_at,
                    user_id,
                    exposed_at,
                )
            )

        candidates.sort(
            key=lambda row: (
                row[0],
                row[1],
            )
        )

        for (
            assignment_at,
            user_id,
            exposed_at,
        ) in candidates:
            pair = (
                experiment_id,
                user_id,
            )

            if pair in seen_pairs:
                raise RuntimeError(
                    "Duplicate experiment/user "
                    f"assignment: {pair}"
                )

            seen_pairs.add(pair)

            user = users_by_id[
                user_id
            ]

            variant, allocation_probability = (
                _choose_variant(
                    definition=definition,
                    user_id=user_id,
                )
            )

            assignments.append(
                {
                    "assignment_id": (
                        _assignment_id(
                            experiment_id,
                            user_id,
                        )
                    ),
                    "experiment_id": experiment_id,
                    "experiment_name": definition[
                        "experiment_name"
                    ],
                    "user_id": user_id,
                    "installation_id": user[
                        "installation_id"
                    ],
                    "randomization_unit": definition[
                        "randomization_unit"
                    ],
                    "variant": variant,
                    "allocation_probability": (
                        allocation_probability
                    ),
                    "assignment_at": assignment_at,
                    "exposed_at": exposed_at,
                    "experiment_start_at": definition[
                        "start_at"
                    ],
                    "experiment_end_at": definition[
                        "end_at"
                    ],
                    "eligibility_rule": definition[
                        "eligibility_rule"
                    ],
                    "assignment_trigger": definition[
                        "assignment_trigger"
                    ],
                    "exposure_trigger": definition[
                        "exposure_trigger"
                    ],
                    "hypothesis": definition[
                        "hypothesis"
                    ],
                    "primary_metric": definition[
                        "primary_metric"
                    ],
                    "secondary_metric": definition[
                        "secondary_metric"
                    ],
                    "commercial_metric": definition[
                        "commercial_metric"
                    ],
                    "guardrail_metric": definition[
                        "guardrail_metric"
                    ],
                    "analysis_window_days": definition[
                        "analysis_window_days"
                    ],
                }
            )

    assignments.sort(
        key=lambda row: (
            row["assignment_at"],
            row["experiment_id"],
            row["user_id"],
        )
    )

    return assignments