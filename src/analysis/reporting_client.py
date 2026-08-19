"""Read-only access to the Pulse reporting semantic layer.

Phase 4 business analysis must consume the canonical reporting contract.
Direct reads from raw, staging, validation and analytics schemas are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Iterable, Mapping, Sequence

from psycopg.rows import dict_row

from src.ingestion.database import DatabaseConfig, connect_database


class ReportingQueryError(ValueError):
    """Raised when a Phase 4 query violates the reporting-only contract."""


class MetricContractError(ValueError):
    """Raised when an analysis requests a non-supported metric."""


_FORBIDDEN_SCHEMA_PATTERN = re.compile(
    r"\b(?:raw|staging|validation|analytics)\s*\.",
    flags=re.IGNORECASE,
)

_WRITE_KEYWORD_PATTERN = re.compile(
    (
        r"\b(?:insert|update|delete|truncate|alter|drop|create|grant|"
        r"revoke|copy|vacuum|analyze|refresh|call|do)\b"
    ),
    flags=re.IGNORECASE,
)

_REPORTING_REFERENCE_PATTERN = re.compile(
    r"\breporting\s*\.",
    flags=re.IGNORECASE,
)

_READ_QUERY_PATTERN = re.compile(
    r"^\s*(?:select|with)\b",
    flags=re.IGNORECASE,
)


@dataclass(frozen=True)
class ReportingContext:
    """Lineage and observation context for a reporting build."""

    ingestion_batch_id: int
    analytics_build_run_id: int
    observation_cutoff_at: datetime


def validate_reporting_sql(sql: str) -> str:
    """Validate that SQL conforms to the Phase 4 read-only contract."""

    if not isinstance(sql, str):
        raise TypeError("sql must be a string")

    stripped = sql.strip()

    if not stripped:
        raise ReportingQueryError("SQL must not be empty.")

    if not _READ_QUERY_PATTERN.search(stripped):
        raise ReportingQueryError(
            "Phase 4 analysis SQL must begin with SELECT or WITH."
        )

    statement_body = (
        stripped[:-1].rstrip()
        if stripped.endswith(";")
        else stripped
    )

    if ";" in statement_body:
        raise ReportingQueryError(
            "Multiple SQL statements are not allowed."
        )

    forbidden_schema = _FORBIDDEN_SCHEMA_PATTERN.search(statement_body)
    if forbidden_schema:
        raise ReportingQueryError(
            "Phase 4 business analysis may query reporting.* only; "
            f"forbidden reference found: {forbidden_schema.group(0)}"
        )

    write_keyword = _WRITE_KEYWORD_PATTERN.search(statement_body)
    if write_keyword:
        raise ReportingQueryError(
            "Phase 4 analysis queries must be read only; "
            f"forbidden keyword found: {write_keyword.group(0)}"
        )

    if not _REPORTING_REFERENCE_PATTERN.search(statement_body):
        raise ReportingQueryError(
            "Phase 4 analysis SQL must reference reporting.*."
        )

    return stripped


def fetch_reporting_rows(
    sql: str,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    """Execute one reporting-only query inside a read-only transaction."""

    validated_sql = validate_reporting_sql(sql)

    with connect_database(config) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")

            with connection.cursor(row_factory=dict_row) as cursor:
                if params is None:
                    cursor.execute(validated_sql)
                else:
                    cursor.execute(validated_sql, params)

                return [
                    dict(row)
                    for row in cursor.fetchall()
                ]


def get_metric_contracts(
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    """Load the canonical reporting metric registry."""

    return fetch_reporting_rows(
        """
        SELECT
            metric_key,
            metric_name,
            metric_domain,
            metric_grain,
            metric_unit,
            support_status,
            definition,
            denominator_definition,
            caveat
        FROM reporting.metric_definitions
        ORDER BY metric_key
        """,
        config=config,
    )


def require_supported_metrics(
    metric_keys: Iterable[str],
    *,
    config: DatabaseConfig | None = None,
) -> dict[str, dict[str, Any]]:
    """Require every requested metric to exist and be supported."""

    requested = tuple(dict.fromkeys(metric_keys))

    if not requested:
        raise MetricContractError(
            "At least one metric key must be requested."
        )

    contracts = {
        row["metric_key"]: row
        for row in get_metric_contracts(config=config)
    }

    missing = [
        key
        for key in requested
        if key not in contracts
    ]

    if missing:
        raise MetricContractError(
            "Unknown metric contract(s): "
            + ", ".join(sorted(missing))
        )

    unsupported = {
        key: contracts[key]["support_status"]
        for key in requested
        if contracts[key]["support_status"] != "supported"
    }

    if unsupported:
        detail = ", ".join(
            f"{key}={status}"
            for key, status in sorted(unsupported.items())
        )
        raise MetricContractError(
            "Phase 4 may use supported metrics only: "
            + detail
        )

    return {
        key: contracts[key]
        for key in requested
    }


def get_reporting_context(
    *,
    config: DatabaseConfig | None = None,
) -> ReportingContext:
    """Return the latest canonical reporting observation context."""

    rows = fetch_reporting_rows(
        """
        SELECT
            ingestion_batch_id,
            analytics_build_run_id,
            observation_cutoff_at
        FROM reporting.vw_observation_cutoff
        ORDER BY analytics_build_run_id DESC
        LIMIT 1
        """,
        config=config,
    )

    if len(rows) != 1:
        raise ReportingQueryError(
            "Expected exactly one latest reporting context row."
        )

    row = rows[0]

    return ReportingContext(
        ingestion_batch_id=int(row["ingestion_batch_id"]),
        analytics_build_run_id=int(row["analytics_build_run_id"]),
        observation_cutoff_at=row["observation_cutoff_at"],
    )
