"""Retention & Lifecycle page."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from src.app.components import (
    dataframe_for_display,
    first_row,
    format_integer,
    format_percent,
    numeric_series,
)
from src.app.data_access import load_named_query


def render(context: Mapping[str, Any]) -> None:
    st.header("Retention & Lifecycle")
    st.caption(
        "Maturity-controlled trial conversion and paid retention. "
        "Immature observations are excluded from canonical denominators."
    )

    build_id = int(context["analytics_build_run_id"])

    retention = first_row(
        load_named_query(
            "retention_summary",
            analytics_build_run_id=build_id,
        )
    )

    cols = st.columns(5)

    cols[0].metric(
        "Paid Subscriptions",
        format_integer(
            retention["paid_subscription_count"]
        ),
    )

    cols[1].metric(
        "D30",
        format_percent(
            retention["paid_retention_d30"]
        ),
    )

    cols[2].metric(
        "D90",
        format_percent(
            retention["paid_retention_d90"]
        ),
    )

    cols[3].metric(
        "D180",
        format_percent(
            retention["paid_retention_d180"]
        ),
    )

    cols[4].metric(
        "D365",
        format_percent(
            retention["paid_retention_d365"]
        ),
    )

    st.subheader("Paid retention curve")

    retention_curve = pd.DataFrame(
        {
            "horizon": [
                "D30",
                "D90",
                "D180",
                "D365",
            ],
            "retention_rate": [
                float(retention["paid_retention_d30"]),
                float(retention["paid_retention_d90"]),
                float(retention["paid_retention_d180"]),
                float(retention["paid_retention_d365"]),
            ],
            "mature_subscriptions": [
                retention["mature_d30_count"],
                retention["mature_d90_count"],
                retention["mature_d180_count"],
                retention["mature_d365_count"],
            ],
        }
    )

    retention_chart = retention_curve.copy()

    retention_chart["horizon_order"] = [
        30,
        90,
        180,
        365,
    ]

    retention_chart = retention_chart.sort_values(
        "horizon_order"
    )

    st.line_chart(
        retention_chart,
        x="horizon_order",
        y="retention_rate",
        x_label="Days since paid start",
        y_label="Paid retention rate",
    )

    st.dataframe(
        retention_curve,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Trial conversion by acquisition channel")

    trial = load_named_query(
        "trial_conversion_channel",
        analytics_build_run_id=build_id,
    )

    trial_chart = numeric_series(
        trial,
        ["trial_to_paid_conversion_rate"],
    )

    if not trial_chart.empty:
        st.bar_chart(
            trial_chart.set_index(
                "acquisition_channel"
            )[
                ["trial_to_paid_conversion_rate"]
            ]
        )

        st.dataframe(
            dataframe_for_display(trial),
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Paid retention by acquisition channel")

    channel_retention = load_named_query(
        "retention_channel",
        analytics_build_run_id=build_id,
    )

    if not channel_retention.empty:
        st.dataframe(
            dataframe_for_display(
                channel_retention
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.caption(
        "Cross-channel retention differences are descriptive. "
        "They do not establish that acquisition channel caused "
        "different retention outcomes."
    )