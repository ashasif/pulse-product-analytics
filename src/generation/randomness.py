"""Utilities for reproducible random-number streams."""

from hashlib import sha256
from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SEED_CONFIG = PROJECT_ROOT / "config" / "seeds.toml"

def derive_seed(master_seed: int, stream_name: str) -> int:
    """
    Derive a stable 64-bit child seed from a master seed and stream name.

    The same master seed and stream name will always produce the same
    child seed.
    """

    if not isinstance(master_seed, int):
        raise TypeError("master_seed must be an integer")

    if master_seed < 0:
        raise ValueError("master_seed must be non-negative")

    if not isinstance(stream_name, str):
        raise TypeError("stream_name must be a string")

    if not stream_name.strip():
        raise ValueError("stream_name must not be empty")

    payload = f"{master_seed}:{stream_name}".encode("utf-8")
    digest = sha256(payload).digest()

    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def load_seed_config(config_path: Path = DEFAULT_SEED_CONFIG) -> dict:
    """Load the seed configuration from TOML."""

    with config_path.open("rb") as file:
        return tomllib.load(file)


def get_stream_seed(
    stream_name: str,
    config_path: Path = DEFAULT_SEED_CONFIG,
) -> int:
    """
    Return the deterministic seed for a registered random stream.
    """

    config = load_seed_config(config_path)

    master_seed = config["random"]["master_seed"]
    derivation_method = config["random"]["derivation_method"]
    registered_streams = config["streams"]["names"]

    if derivation_method != "sha256":
        raise ValueError(
            f"Unsupported seed derivation method: {derivation_method}"
        )

    if stream_name not in registered_streams:
        raise ValueError(
            f"Unknown random stream: {stream_name}"
        )

    return derive_seed(master_seed, stream_name)