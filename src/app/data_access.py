"""Read-only data access for the Pulse Streamlit application."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Sequence

import pandas as pd

from src.analysis.reporting_client import (
    fetch_reporting_rows,
    get_metric_contracts,
    get_reporting_context,
)
from src.app.queries import APP_QUERY_REGISTRY
from src.ingestion.database import DatabaseConfig


class DashboardQueryError(ValueError):
    """Raised when the dashboard requests an unknown query contract."""


def fetch_reporting_dataframe(
    sql: str,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
    *,
    config: DatabaseConfig | None = None,
) -> pd.DataFrame:
    """Execute one validated reporting query and return a DataFrame."""

    rows = fetch_reporting_rows(
        sql,
        params,
        config=config,
    )

    return pd.DataFrame(rows)


def load_reporting_context(
    *,
    config: DatabaseConfig | None = None,
) -> dict[str, object]:
    """Load canonical ingestion/build/cutoff context."""

    return asdict(
        get_reporting_context(config=config)
    )


def load_metric_definitions(
    *,
    config: DatabaseConfig | None = None,
) -> pd.DataFrame:
    """Load the complete canonical metric registry."""

    return pd.DataFrame(
        get_metric_contracts(config=config)
    )


def load_supported_metric_definitions(
    *,
    config: DatabaseConfig | None = None,
) -> pd.DataFrame:
    """Load supported canonical metric definitions only."""

    frame = load_metric_definitions(
        config=config
    )

    if frame.empty:
        return frame

    return frame[
        frame["support_status"] == "supported"
    ].reset_index(drop=True)


def load_named_query(
    query_name: str,
    *,
    analytics_build_run_id: int,
    config: DatabaseConfig | None = None,
) -> pd.DataFrame:
    """Execute one approved dashboard query against a fixed build."""

    try:
        sql = APP_QUERY_REGISTRY[query_name]
    except KeyError as exc:
        raise DashboardQueryError(
            f"Unknown dashboard query: {query_name}"
        ) from exc

    return fetch_reporting_dataframe(
        sql,
        {
            "analytics_build_run_id":
                analytics_build_run_id,
        },
        config=config,
    )