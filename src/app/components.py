"""Reusable presentation helpers for Pulse Streamlit pages."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st


PULSE_BUSINESS_TIMEZONE = ZoneInfo(
    "Europe/London"
)


def format_integer(value: Any) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{int(value):,}"


def format_percent(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"{float(value) * 100:.{digits}f}%"


def format_gbp(value: Any, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "—"
    return f"£{float(value):,.{digits}f}"


def format_observation_cutoff(
    value: Any,
) -> str:
    """Render the canonical cutoff consistently in Europe/London."""

    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(
                PULSE_BUSINESS_TIMEZONE
            )

        return value.strftime(
            "%Y-%m-%d %H:%M:%S %Z"
        )

    return str(value)


def numeric_series(
    frame: pd.DataFrame,
    columns: list[str],
) -> pd.DataFrame:
    """Return chart-safe numeric columns without mutating source data."""

    result = frame.copy()

    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(
                result[column],
                errors="coerce",
            )

    return result


def first_row(
    frame: pd.DataFrame,
) -> Mapping[str, Any]:
    """Return the first query row and fail clearly on empty evidence."""

    if frame.empty:
        raise ValueError(
            "Expected dashboard query to return at least one row."
        )

    return frame.iloc[0].to_dict()


def render_synthetic_notice() -> None:
    st.info(
        "Pulse uses synthetic customer behaviour created for portfolio "
        "and learning purposes. Results demonstrate analytical methodology "
        "and are not evidence of identical relationships in real customers."
    )


def render_lineage(
    context: Mapping[str, Any],
) -> None:
    st.sidebar.caption(
        "Canonical reporting context"
    )

    st.sidebar.write(
        f"**Ingestion batch:** "
        f"{context['ingestion_batch_id']}"
    )

    st.sidebar.write(
        f"**Analytics build:** "
        f"{context['analytics_build_run_id']}"
    )

    st.sidebar.write(
        "**Observation cutoff:** "
        + format_observation_cutoff(
            context["observation_cutoff_at"]
        )
    )


def dataframe_for_display(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """Convert Decimal values to floats for Streamlit display."""

    result = frame.copy()

    for column in result.columns:
        if result[column].map(
            lambda value:
                isinstance(value, Decimal)
        ).any():
            result[column] = result[column].map(
                lambda value:
                    float(value)
                    if isinstance(value, Decimal)
                    else value
            )

    return result