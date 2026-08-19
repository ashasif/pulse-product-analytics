"""Growth & Acquisition page."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from src.app.components import (
    dataframe_for_display,
    format_gbp,
    format_integer,
    format_percent,
    numeric_series,
)
from src.app.data_access import load_named_query


def render(context: Mapping[str, Any]) -> None:
    st.header("Growth & Acquisition")
    st.caption(
        "Acquisition quality and efficiency using canonical "
        "installation-cohort and marketing-spend reporting."
    )

    build_id = int(context["analytics_build_run_id"])

    channel = load_named_query(
        "acquisition_channel",
        analytics_build_run_id=build_id,
    )

    if channel.empty:
        st.warning("No acquisition-channel evidence is available.")
        return

    total_spend = channel["marketing_spend_gbp"].map(
        float
    ).sum()

    total_installations = channel[
        "installation_count"
    ].sum()

    total_signups = channel[
        "installations_with_signup"
    ].sum()

    overall_rate = (
        total_signups / total_installations
        if total_installations
        else None
    )

    cols = st.columns(3)

    cols[0].metric(
        "Marketing Spend",
        format_gbp(total_spend),
    )

    cols[1].metric(
        "Installations",
        format_integer(total_installations),
    )

    cols[2].metric(
        "Install → Signup",
        format_percent(overall_rate),
    )

    st.subheader("Channel performance")

    chart_frame = numeric_series(
        channel,
        [
            "install_to_signup_rate",
            "cost_per_install_gbp",
        ],
    )

    rate_chart = (
        chart_frame[
            [
                "acquisition_channel",
                "install_to_signup_rate",
            ]
        ]
        .set_index("acquisition_channel")
        * 100
    )

    st.bar_chart(rate_chart)

    display = dataframe_for_display(
        channel[
            [
                "acquisition_channel",
                "marketing_spend_gbp",
                "installation_count",
                "installations_with_signup",
                "install_to_signup_rate",
                "click_through_rate",
                "cost_per_click_gbp",
                "cost_per_install_gbp",
            ]
        ]
    )

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Cost per install is a channel-level acquisition-efficiency "
        "metric. It is not campaign-attributed CAC."
    )

    st.subheader("Platform funnel")

    platform = load_named_query(
        "platform_funnel",
        analytics_build_run_id=build_id,
    )

    platform_display = dataframe_for_display(platform)

    st.dataframe(
        platform_display,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Platform comparisons are descriptive. They do not establish "
        "that platform caused downstream differences."
    )