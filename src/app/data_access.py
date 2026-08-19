"""Read-only data-access helpers for the Pulse Streamlit application."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Sequence

import pandas as pd

from src.analysis.reporting_client import (
    fetch_reporting_rows,
    get_metric_contracts,
    get_reporting_context,
)
from src.ingestion.database import DatabaseConfig


def fetch_reporting_dataframe(
    sql: str,
    params: Sequence[Any] | Mapping[str, Any] | None = None,
    *,
    config: DatabaseConfig | None = None,
) -> pd.DataFrame:
    """Execute one validated reporting-only query and return a DataFrame."""

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


def load_supported_metric_definitions(
    *,
    config: DatabaseConfig | None = None,
) -> pd.DataFrame:
    """Load supported canonical metric definitions only."""

    rows = [
        row
        for row in get_metric_contracts(config=config)
        if row["support_status"] == "supported"
    ]

    return pd.DataFrame(rows)