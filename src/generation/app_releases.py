"""Synthetic app-release generation for Pulse."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any

from src.generation.installations import (
    DEFAULT_SIMULATION_CONFIG,
    get_simulation_bounds,
    load_installation_dimensions,
    load_simulation_config,
)


VALID_RELEASE_TYPES = {"major", "minor", "patch"}

VALID_ROLLOUT_STRATEGIES = {
    "full",
    "phased",
}

SYSTEM_FEATURE_AREAS = {
    "onboarding",
    "core_platform",
    "paywall",
    "subscriptions",
}

SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$"
)


def _parse_utc_timestamp(
    value: str,
) -> datetime:
    """Parse an ISO-8601 timestamp and normalise it to UTC."""

    if not isinstance(value, str):
        raise TypeError(
            "release_at must be a string"
        )

    timestamp = datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )

    if timestamp.tzinfo is None:
        raise ValueError(
            "release_at must include timezone information"
        )

    return timestamp.astimezone(
        timezone.utc
    )


def _validate_non_empty_string(
    value: Any,
    name: str,
) -> str:
    """Validate and return a non-empty string."""

    if not isinstance(
        value,
        str,
    ):
        raise TypeError(
            f"{name} must be a string"
        )

    if not value.strip():
        raise ValueError(
            f"{name} must be a non-empty string"
        )

    return value


def _parse_semver(
    value: Any,
    name: str,
) -> tuple[int, int, int]:
    """
    Validate a semantic version and return
    its integer components.
    """

    version = _validate_non_empty_string(
        value,
        name,
    )

    match = SEMVER_PATTERN.fullmatch(
        version
    )

    if match is None:
        raise ValueError(
            f"{name} must use "
            "MAJOR.MINOR.PATCH semantic versioning"
        )

    return tuple(
        int(part)
        for part in match.groups()
    )


def _version_change_type(
    previous: tuple[int, int, int],
    current: tuple[int, int, int],
) -> str:
    """
    Classify a strictly increasing
    semantic-version change.
    """

    if current <= previous:
        raise ValueError(
            "App release versions must "
            "increase strictly"
        )

    if current[0] > previous[0]:
        return "major"

    if current[1] > previous[1]:
        return "minor"

    return "patch"


def load_app_release_config(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict[str, Any]:
    """Load and validate Pulse app-release configuration."""

    config = load_simulation_config(
        config_path
    )

    if "app_releases" not in config:
        raise ValueError(
            "simulation.toml is missing "
            "[app_releases]"
        )

    app_releases = config[
        "app_releases"
    ]

    grain = app_releases.get(
        "grain"
    )

    if grain != "release_platform":
        raise ValueError(
            "app_releases.grain must be "
            "'release_platform'"
        )

    release_channel = (
        _validate_non_empty_string(
            app_releases.get(
                "release_channel"
            ),
            "app_releases.release_channel",
        )
    )

    if release_channel != "production":
        raise ValueError(
            "app_releases.release_channel "
            "must be 'production'"
        )

    baseline_version_text = (
        _validate_non_empty_string(
            app_releases.get(
                "baseline_version"
            ),
            "app_releases.baseline_version",
        )
    )

    baseline_version = _parse_semver(
        baseline_version_text,
        "app_releases.baseline_version",
    )

    definitions = app_releases.get(
        "definitions"
    )

    if not isinstance(
        definitions,
        list,
    ):
        raise TypeError(
            "app_releases.definitions "
            "must be a list"
        )

    if not definitions:
        raise ValueError(
            "app_releases.definitions "
            "must not be empty"
        )

    (
        simulation_start,
        simulation_end,
    ) = get_simulation_bounds(
        config_path
    )

    installation_dimensions = (
        load_installation_dimensions(
            config_path
        )
    )

    platforms = tuple(
        installation_dimensions[
            "platform"
        ][
            "values"
        ]
    )

    product_feature_areas = set(
        config[
            "features"
        ][
            "names"
        ]
    )

    valid_feature_areas = (
        product_feature_areas
        | SYSTEM_FEATURE_AREAS
    )

    seen_release_keys: set[str] = set()

    validated_definitions: list[
        dict[str, Any]
    ] = []

    required_strings = (
        "release_key",
        "release_name",
        "release_type",
        "feature_area",
        "rollout_strategy",
        "release_notes",
    )

    for definition in definitions:

        if not isinstance(
            definition,
            dict,
        ):
            raise TypeError(
                "Each app release definition "
                "must be a table"
            )

        for field in required_strings:

            if field not in definition:
                raise ValueError(
                    "App release is missing: "
                    f"{field}"
                )

            _validate_non_empty_string(
                definition[
                    field
                ],
                field,
            )

        release_key = definition[
            "release_key"
        ]

        if release_key in seen_release_keys:
            raise ValueError(
                "Duplicate release_key: "
                f"{release_key}"
            )

        seen_release_keys.add(
            release_key
        )

        release_at = (
            _parse_utc_timestamp(
                definition.get(
                    "release_at"
                )
            )
        )

        if not (
            simulation_start
            <= release_at
            <= simulation_end
        ):
            raise ValueError(
                f"{release_key}.release_at "
                "must be inside the "
                "simulation period"
            )

        release_type = definition[
            "release_type"
        ]

        if (
            release_type
            not in VALID_RELEASE_TYPES
        ):
            raise ValueError(
                "Unsupported release_type "
                f"for {release_key}: "
                f"{release_type}"
            )

        feature_area = definition[
            "feature_area"
        ]

        if (
            feature_area
            not in valid_feature_areas
        ):
            raise ValueError(
                "Unsupported feature_area "
                f"for {release_key}: "
                f"{feature_area}"
            )

        rollout_strategy = definition[
            "rollout_strategy"
        ]

        if (
            rollout_strategy
            not in VALID_ROLLOUT_STRATEGIES
        ):
            raise ValueError(
                "Unsupported rollout_strategy "
                f"for {release_key}: "
                f"{rollout_strategy}"
            )

        rollout_days = definition.get(
            "rollout_days"
        )

        if (
            not isinstance(
                rollout_days,
                int,
            )
            or isinstance(
                rollout_days,
                bool,
            )
        ):
            raise TypeError(
                f"{release_key}.rollout_days "
                "must be an integer"
            )

        if rollout_days < 0:
            raise ValueError(
                f"{release_key}.rollout_days "
                "must be non-negative"
            )

        if (
            rollout_strategy == "full"
            and rollout_days != 0
        ):
            raise ValueError(
                f"{release_key}.rollout_days "
                "must be 0 for full rollout"
            )

        if (
            rollout_strategy == "phased"
            and rollout_days <= 0
        ):
            raise ValueError(
                f"{release_key}.rollout_days "
                "must be positive for "
                "phased rollout"
            )

        rollout_complete_at = (
            release_at
            + timedelta(
                days=rollout_days
            )
        )

        if (
            rollout_complete_at
            > simulation_end
        ):
            raise ValueError(
                f"{release_key} rollout "
                "must complete inside "
                "the simulation period"
            )

        platform_versions = (
            definition.get(
                "platform_versions"
            )
        )

        if not isinstance(
            platform_versions,
            dict,
        ):
            raise TypeError(
                f"{release_key}."
                "platform_versions "
                "must be a table"
            )

        if (
            set(
                platform_versions
            )
            != set(
                platforms
            )
        ):
            raise ValueError(
                f"{release_key}."
                "platform_versions must "
                "exactly match configured "
                "installation platforms"
            )

        validated_versions = {}

        for platform in platforms:

            version_text = (
                _validate_non_empty_string(
                    platform_versions[
                        platform
                    ],
                    (
                        f"{release_key}."
                        "platform_versions."
                        f"{platform}"
                    ),
                )
            )

            _parse_semver(
                version_text,
                (
                    f"{release_key}."
                    "platform_versions."
                    f"{platform}"
                ),
            )

            validated_versions[
                platform
            ] = version_text

        validated_definitions.append(
            {
                "release_key": (
                    release_key
                ),
                "release_name": (
                    definition[
                        "release_name"
                    ]
                ),
                "release_at": (
                    release_at
                ),
                "release_type": (
                    release_type
                ),
                "feature_area": (
                    feature_area
                ),
                "rollout_strategy": (
                    rollout_strategy
                ),
                "rollout_days": (
                    rollout_days
                ),
                "rollout_complete_at": (
                    rollout_complete_at
                ),
                "platform_versions": (
                    validated_versions
                ),
                "release_notes": (
                    definition[
                        "release_notes"
                    ]
                ),
            }
        )

    validated_definitions.sort(
        key=lambda row: row[
            "release_at"
        ]
    )

    for platform in platforms:

        previous_version = (
            baseline_version
        )

        for definition in (
            validated_definitions
        ):

            current_version = (
                _parse_semver(
                    definition[
                        "platform_versions"
                    ][
                        platform
                    ],
                    (
                        f"{definition['release_key']}."
                        "platform_versions."
                        f"{platform}"
                    ),
                )
            )

            observed_change_type = (
                _version_change_type(
                    previous_version,
                    current_version,
                )
            )

            if (
                observed_change_type
                != definition[
                    "release_type"
                ]
            ):
                raise ValueError(
                    f"{definition['release_key']}."
                    "release_type is "
                    f"'{definition['release_type']}' "
                    f"but {platform} version "
                    "change is "
                    f"'{observed_change_type}'"
                )

            previous_version = (
                current_version
            )

    return {
        "grain": grain,
        "release_channel": (
            release_channel
        ),
        "baseline_version": (
            baseline_version_text
        ),
        "platforms": (
            platforms
        ),
        "valid_feature_areas": tuple(
            sorted(
                valid_feature_areas
            )
        ),
        "definitions": (
            validated_definitions
        ),
    }


def generate_app_releases(
    start_at: datetime,
    end_at: datetime,
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> list[dict[str, Any]]:
    """
    Generate deterministic platform-level
    app-release rows.
    """

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

    start_at = start_at.astimezone(
        timezone.utc
    )

    end_at = end_at.astimezone(
        timezone.utc
    )

    release_config = (
        load_app_release_config(
            config_path
        )
    )

    sequence_by_platform = {
        platform: 0
        for platform in release_config[
            "platforms"
        ]
    }

    rows = []

    for definition in release_config[
        "definitions"
    ]:

        release_at = definition[
            "release_at"
        ]

        if not (
            start_at
            <= release_at
            <= end_at
        ):
            continue

        for platform in release_config[
            "platforms"
        ]:

            sequence_by_platform[
                platform
            ] += 1

            rows.append(
                {
                    "app_release_id": (
                        f"{definition['release_key']}_"
                        f"{platform}"
                    ),
                    "release_key": (
                        definition[
                            "release_key"
                        ]
                    ),
                    "release_name": (
                        definition[
                            "release_name"
                        ]
                    ),
                    "release_sequence": (
                        sequence_by_platform[
                            platform
                        ]
                    ),
                    "platform": (
                        platform
                    ),
                    "version": (
                        definition[
                            "platform_versions"
                        ][
                            platform
                        ]
                    ),
                    "release_at": (
                        release_at
                    ),
                    "release_type": (
                        definition[
                            "release_type"
                        ]
                    ),
                    "feature_area": (
                        definition[
                            "feature_area"
                        ]
                    ),
                    "rollout_strategy": (
                        definition[
                            "rollout_strategy"
                        ]
                    ),
                    "rollout_days": (
                        definition[
                            "rollout_days"
                        ]
                    ),
                    "rollout_complete_at": (
                        definition[
                            "rollout_complete_at"
                        ]
                    ),
                    "release_channel": (
                        release_config[
                            "release_channel"
                        ]
                    ),
                    "release_notes": (
                        definition[
                            "release_notes"
                        ]
                    ),
                }
            )

    rows.sort(
        key=lambda row: (
            row[
                "release_at"
            ],
            row[
                "platform"
            ],
        )
    )

    return rows


if __name__ == "__main__":

    (
        simulation_start,
        simulation_end,
    ) = get_simulation_bounds()

    releases = (
        generate_app_releases(
            simulation_start,
            simulation_end,
        )
    )

    for release in releases:
        print(
            release
        )