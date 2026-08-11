"""Synthetic installation generation for Pulse."""

from datetime import date, datetime, timedelta, timezone
from math import isclose
from pathlib import Path
import random
import tomllib

from src.generation.randomness import get_substream_seed


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIMULATION_CONFIG = (
    PROJECT_ROOT / "config" / "simulation.toml"
)


def load_simulation_config(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict:
    """Load the main Pulse simulation configuration."""

    with config_path.open("rb") as file:
        return tomllib.load(file)


def load_installation_dimensions(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict:
    """Load and validate configured installation dimensions."""

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


def load_installation_timing(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict:
    """Load and validate installation timing assumptions."""

    config = load_simulation_config(config_path)
    timing = config["installation_timing"]

    growth_model = timing["growth_model"]

    if growth_model != "linear":
        raise ValueError(
            f"Unsupported installation growth model: {growth_model}"
        )

    growth_start = timing["growth_start_multiplier"]
    growth_end = timing["growth_end_multiplier"]

    if growth_start <= 0 or growth_end <= 0:
        raise ValueError(
            "Growth multipliers must be greater than zero"
        )

    month_multipliers = tuple(
        timing["month_multipliers"]
    )

    weekday_multipliers = tuple(
        timing["weekday_multipliers"]
    )

    if len(month_multipliers) != 12:
        raise ValueError(
            "month_multipliers must contain 12 values"
        )

    if len(weekday_multipliers) != 7:
        raise ValueError(
            "weekday_multipliers must contain 7 values"
        )

    if any(value <= 0 for value in month_multipliers):
        raise ValueError(
            "All month multipliers must be greater than zero"
        )

    if any(value <= 0 for value in weekday_multipliers):
        raise ValueError(
            "All weekday multipliers must be greater than zero"
        )

    return {
        "growth_model": growth_model,
        "growth_start_multiplier": growth_start,
        "growth_end_multiplier": growth_end,
        "month_multipliers": month_multipliers,
        "weekday_multipliers": weekday_multipliers,
    }


def get_simulation_bounds(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> tuple[datetime, datetime]:
    """Return the configured simulation timestamp boundaries."""

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
        snapshot_at = snapshot_at.replace(
            tzinfo=timezone.utc
        )

    end_at = snapshot_at - timedelta(seconds=1)

    expected_end_date = config["simulation"]["end_date"]

    if end_at.date().isoformat() != expected_end_date:
        raise ValueError(
            "Simulation end_date and snapshot_at are inconsistent"
        )

    return start_at, end_at


def build_daily_installation_weights(
    start_at: datetime,
    end_at: datetime,
    timing: dict,
) -> tuple[list[date], list[float]]:
    """
    Build relative installation intensity for every simulation day.

    Daily intensity combines:
    - long-term product growth
    - month-of-year seasonality
    - weekday behaviour
    """

    number_of_days = (
        end_at.date() - start_at.date()
    ).days + 1

    days = []
    weights = []

    growth_start = timing["growth_start_multiplier"]
    growth_end = timing["growth_end_multiplier"]

    for day_index in range(number_of_days):
        current_day = (
            start_at.date()
            + timedelta(days=day_index)
        )

        if number_of_days == 1:
            growth_fraction = 0.0
        else:
            growth_fraction = (
                day_index / (number_of_days - 1)
            )

        growth_multiplier = (
            growth_start
            + growth_fraction
            * (growth_end - growth_start)
        )

        month_multiplier = (
            timing["month_multipliers"][
                current_day.month - 1
            ]
        )

        weekday_multiplier = (
            timing["weekday_multipliers"][
                current_day.weekday()
            ]
        )

        daily_weight = (
            growth_multiplier
            * month_multiplier
            * weekday_multiplier
        )

        days.append(current_day)
        weights.append(daily_weight)

    return days, weights


def generate_installations(
    count: int,
    start_at: datetime,
    end_at: datetime,
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> list[dict]:
    """Generate reproducible synthetic Pulse installations."""

    if not isinstance(count, int):
        raise TypeError("count must be an integer")

    if count <= 0:
        raise ValueError(
            "count must be greater than zero"
        )

    if start_at.tzinfo is None or end_at.tzinfo is None:
        raise ValueError(
            "start_at and end_at must be timezone-aware"
        )

    if start_at >= end_at:
        raise ValueError(
            "start_at must be earlier than end_at"
        )

    dimensions = load_installation_dimensions(
        config_path
    )

    timing = load_installation_timing(
        config_path
    )

    platform = dimensions["platform"]
    acquisition = dimensions["acquisition_channel"]
    country = dimensions["country_code"]

    day_rng = random.Random(
        get_substream_seed(
            "installations",
            "install_day",
        )
    )

    time_rng = random.Random(
        get_substream_seed(
            "installations",
            "install_time",
        )
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

    days, daily_weights = (
        build_daily_installation_weights(
            start_at,
            end_at,
            timing,
        )
    )

    selected_days = day_rng.choices(
        days,
        weights=daily_weights,
        k=count,
    )

    installations = []

    for index, selected_day in enumerate(
        selected_days,
        start=1,
    ):
        day_start = datetime(
            selected_day.year,
            selected_day.month,
            selected_day.day,
            tzinfo=timezone.utc,
        )

        lower_bound = max(
            day_start,
            start_at,
        )

        upper_bound = min(
            day_start
            + timedelta(days=1)
            - timedelta(seconds=1),
            end_at,
        )

        seconds_available = int(
            (
                upper_bound - lower_bound
            ).total_seconds()
        )

        seconds_from_day_start = time_rng.randrange(
            seconds_available + 1
        )

        installed_at = (
            lower_bound
            + timedelta(
                seconds=seconds_from_day_start
            )
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
                "installation_id": (
                    f"inst_{index:08d}"
                ),
                "anonymous_id": (
                    f"anon_{index:08d}"
                ),
                "installed_at": installed_at,
                "platform": platform_value,
                "acquisition_channel": (
                    acquisition_value
                ),
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