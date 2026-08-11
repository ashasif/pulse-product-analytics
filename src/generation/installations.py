"""Synthetic installation generation for Pulse."""

from datetime import datetime, timedelta, timezone
from math import isclose
from pathlib import Path
import random
import tomllib

from src.generation.randomness import (
    get_stream_seed,
    get_substream_seed,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIMULATION_CONFIG = PROJECT_ROOT / "config" / "simulation.toml"


def load_simulation_config(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict:
    """Load the main Pulse simulation configuration."""

    with config_path.open("rb") as file:
        return tomllib.load(file)


def load_installation_dimensions(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict:
    """
    Load and validate configured installation dimensions.

    Each dimension must contain:
    - at least one value
    - one weight per value
    - unique values
    - non-negative weights
    - weights summing to 1
    """

    config = load_simulation_config(config_path)
    dimensions = config["installation_dimensions"]

    validated = {}

    for name, dimension in dimensions.items():
        values = tuple(dimension["values"])
        weights = tuple(dimension["weights"])

        if not values:
            raise ValueError(
                f"Installation dimension '{name}' has no values"
            )

        if len(values) != len(weights):
            raise ValueError(
                f"Installation dimension '{name}' has "
                "different numbers of values and weights"
            )

        if len(set(values)) != len(values):
            raise ValueError(
                f"Installation dimension '{name}' contains duplicate values"
            )

        if any(weight < 0 for weight in weights):
            raise ValueError(
                f"Installation dimension '{name}' contains a negative weight"
            )

        if not isclose(
            sum(weights),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError(
                f"Installation dimension '{name}' weights must sum to 1"
            )

        validated[name] = {
            "values": values,
            "weights": weights,
        }

    return validated


def get_simulation_bounds(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> tuple[datetime, datetime]:
    """
    Return the configured simulation start and final included timestamp.
    """

    config = load_simulation_config(config_path)

    start_at = datetime.fromisoformat(
        config["simulation"]["start_date"]
    ).replace(tzinfo=timezone.utc)

    snapshot_text = config["simulation"]["snapshot_at"].replace(
        "Z",
        "+00:00",
    )

    snapshot_at = datetime.fromisoformat(snapshot_text)

    if snapshot_at.tzinfo is None:
        snapshot_at = snapshot_at.replace(tzinfo=timezone.utc)

    end_at = snapshot_at - timedelta(seconds=1)

    expected_end_date = config["simulation"]["end_date"]

    if end_at.date().isoformat() != expected_end_date:
        raise ValueError(
            "Simulation end_date and snapshot_at are inconsistent"
        )

    return start_at, end_at


def generate_installations(
    count: int,
    start_at: datetime,
    end_at: datetime,
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> list[dict]:
    """
    Generate reproducible synthetic Pulse installations.

    The timestamp sequence preserves the already validated installation
    random stream. New installation dimensions use independent substreams,
    so adding or changing one dimension does not disturb the others.
    """

    if not isinstance(count, int):
        raise TypeError("count must be an integer")

    if count <= 0:
        raise ValueError("count must be greater than zero")

    if start_at.tzinfo is None or end_at.tzinfo is None:
        raise ValueError(
            "start_at and end_at must be timezone-aware"
        )

    if start_at >= end_at:
        raise ValueError(
            "start_at must be earlier than end_at"
        )

    dimensions = load_installation_dimensions(config_path)

    platform = dimensions["platform"]
    acquisition = dimensions["acquisition_channel"]
    country = dimensions["country_code"]

    # Keep the original installation stream for timestamps so the
    # previously validated timestamp sequence remains unchanged.
    timestamp_rng = random.Random(
        get_stream_seed("installations")
    )

    platform_rng = random.Random(
        get_substream_seed(
            "installations",
            "platform",
        )
    )

    acquisition_rng = random.Random(
        get_substream_seed(
            "installations",
            "acquisition_channel",
        )
    )

    country_rng = random.Random(
        get_substream_seed(
            "installations",
            "country_code",
        )
    )

    simulation_seconds = int(
        (end_at - start_at).total_seconds()
    )

    installations = []

    for index in range(1, count + 1):
        seconds_from_start = timestamp_rng.randrange(
            simulation_seconds + 1
        )

        installed_at = start_at + timedelta(
            seconds=seconds_from_start
        )

        platform_value = platform_rng.choices(
            platform["values"],
            weights=platform["weights"],
            k=1,
        )[0]

        acquisition_value = acquisition_rng.choices(
            acquisition["values"],
            weights=acquisition["weights"],
            k=1,
        )[0]

        country_value = country_rng.choices(
            country["values"],
            weights=country["weights"],
            k=1,
        )[0]

        installations.append(
            {
                "installation_id": f"inst_{index:08d}",
                "anonymous_id": f"anon_{index:08d}",
                "installed_at": installed_at,
                "platform": platform_value,
                "acquisition_channel": acquisition_value,
                "country_code": country_value,
            }
        )

    installations.sort(
        key=lambda row: row["installed_at"]
    )

    return installations


if __name__ == "__main__":
    start, end = get_simulation_bounds()

    sample = generate_installations(
        count=10,
        start_at=start,
        end_at=end,
    )

    for installation in sample:
        print(installation)