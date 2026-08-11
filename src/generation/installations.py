"""Synthetic installation generation for Pulse."""

from datetime import datetime, timedelta, timezone
import random

from src.generation.randomness import get_stream_seed


def generate_installations(
    count: int,
    start_at: datetime,
    end_at: datetime,
) -> list[dict]:
    """
    Generate a small reproducible collection of synthetic installations.

    Parameters
    ----------
    count:
        Number of installation records to generate.
    start_at:
        Earliest allowed installation timestamp.
    end_at:
        Latest allowed installation timestamp.
    """

    if count <= 0:
        raise ValueError("count must be greater than zero")

    if start_at >= end_at:
        raise ValueError("start_at must be earlier than end_at")

    rng = random.Random(get_stream_seed("installations"))

    simulation_seconds = int((end_at - start_at).total_seconds())

    installations = []

    for index in range(1, count + 1):
        seconds_from_start = rng.randrange(simulation_seconds + 1)

        installed_at = start_at + timedelta(seconds=seconds_from_start)

        installations.append(
            {
                "installation_id": f"inst_{index:08d}",
                "anonymous_id": f"anon_{index:08d}",
                "installed_at": installed_at,
            }
        )

    installations.sort(key=lambda row: row["installed_at"])

    return installations


if __name__ == "__main__":
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)

    sample = generate_installations(
        count=10,
        start_at=start,
        end_at=end,
    )

    for installation in sample:
        print(installation)