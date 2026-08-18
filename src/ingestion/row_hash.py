"""Deterministic source-row hashing for Pulse raw ingestion."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from typing import Any, Mapping, Sequence


class RowHashError(ValueError):
    """Raised when a row cannot be deterministically hashed."""


def _canonical_decimal(value: Decimal) -> str:
    """Represent equivalent decimal values identically."""

    if not value.is_finite():
        raise RowHashError(
            "Non-finite decimal values cannot be hashed."
        )

    if value == 0:
        return "0"

    text = format(value.normalize(), "f")

    if "." in text:
        text = text.rstrip("0").rstrip(".")

    return text


def _canonical_timestamp(value: datetime) -> str:
    """Represent timestamps deterministically."""

    if (
        value.tzinfo is not None
        and value.utcoffset() is not None
    ):
        return (
            value
            .astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )

    return value.isoformat(
        timespec="microseconds"
    )


def _canonical_value(value: Any) -> list[Any]:
    """Return a typed, JSON-safe canonical value."""

    if value is None:
        return ["null", None]

    if isinstance(value, bool):
        return [
            "boolean",
            "true" if value else "false",
        ]

    if isinstance(value, int):
        return ["integer", str(value)]

    if isinstance(value, Decimal):
        return [
            "decimal",
            _canonical_decimal(value),
        ]

    if isinstance(value, datetime):
        return [
            "timestamp",
            _canonical_timestamp(value),
        ]

    if isinstance(value, date):
        return ["date", value.isoformat()]

    if isinstance(value, str):
        return ["string", value]

    raise RowHashError(
        "Unsupported value type for row hashing: "
        f"{type(value).__name__}"
    )


def canonical_row_payload(
    *,
    dataset_name: str,
    values: Mapping[str, Any],
    columns: Sequence[str],
) -> str:
    """Create the canonical serialized representation of a source row.

    Only approved source/business fields are included.

    Ingestion metadata such as batch ID, source row number,
    ingestion timestamp, and source filename is intentionally excluded.
    """

    if not dataset_name:
        raise RowHashError(
            "dataset_name must not be empty."
        )

    expected = tuple(columns)
    expected_set = set(expected)
    actual_set = set(values)

    missing = [
        column
        for column in expected
        if column not in actual_set
    ]

    extra = sorted(
        actual_set - expected_set
    )

    if missing:
        raise RowHashError(
            "Missing source columns: "
            + ", ".join(missing)
        )

    if extra:
        raise RowHashError(
            "Unexpected source columns: "
            + ", ".join(extra)
        )

    payload = {
        "dataset": dataset_name,
        "fields": [
            [
                column,
                _canonical_value(values[column]),
            ]
            for column in expected
        ],
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def compute_row_hash(
    *,
    dataset_name: str,
    values: Mapping[str, Any],
    columns: Sequence[str],
) -> str:
    """Return the deterministic SHA-256 hash for a typed source row."""

    payload = canonical_row_payload(
        dataset_name=dataset_name,
        values=values,
        columns=columns,
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()