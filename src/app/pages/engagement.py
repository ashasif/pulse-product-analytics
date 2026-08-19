"""Engagement & Monetisation page."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from src.app.components import (
    dataframe_for_display,
    first_row,
    format_gbp,
    format_integer,
    format_percent,
    numeric_series,
)
from src.app.data_access import load_named_query


def render(context: Mapping[str, Any]) -> None:
    st.header("Engagement & Monetisation")
    st.caption(
        "Feature usage, product activity and successful billed "
        "payment collection from canonical reporting views."
    )

    build_id = int(context["analytics_build_run_id"])

    feature = load_named_query(
        "feature_summary",
        analytics_build_run_id=build_id,
    )

    revenue = first_row(
        load_named_query(
            "overview_revenue",
            analytics_build_run_id=build_id,
        )
    )

    if not feature.empty:
        top_feature = feature.iloc[0]

        cols = st.columns(4)

        cols[0].metric(
            "Feature Use Events",
            format_integer(
                feature["feature_use_event_count"].sum()
            ),
        )

        cols[1].metric(
            "Top Feature",
            str(top_feature["feature_name"]),
        )

        cols[2].metric(
            "Successful Billed Collection",
            format_gbp(
                revenue["successful_payment_revenue_gbp"]
            ),
        )

        cols[3].metric(
            "Renewal Success",
            format_percent(
                revenue["renewal_success_rate"]
            ),
        )

        st.subheader("Feature-use distribution")

        feature_chart = numeric_series(
            feature,
            ["feature_use_event_count"],
        ).set_index("feature_name")

        st.bar_chart(
            feature_chart[
                ["feature_use_event_count"]
            ]
        )

        st.dataframe(
            dataframe_for_display(feature),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "Feature volume establishes usage concentration only. "
            "It does not establish that a feature causes retention "
            "or commercial outcomes."
        )

    st.subheader("Monthly engagement")

    engagement = load_named_query(
        "monthly_engagement",
        analytics_build_run_id=build_id,
    )

    engagement = numeric_series(
        engagement,
        [
            "session_count",
            "feature_use_event_count",
            "paywall_view_count",
            "trial_start_count",
        ],
    )

    if not engagement.empty:
        st.line_chart(
            engagement.set_index("month")[
                [
                    "session_count",
                    "feature_use_event_count",
                ]
            ]
        )

    st.subheader("Successful billed payment collection")

    monthly_revenue = load_named_query(
        "monthly_revenue",
        analytics_build_run_id=build_id,
    )

    monthly_revenue = numeric_series(
        monthly_revenue,
        [
            "successful_payment_revenue_gbp",
            "payment_failure_rate",
            "renewal_success_rate",
        ],
    )

    if not monthly_revenue.empty:
        st.bar_chart(
            monthly_revenue.set_index("month")[
                ["successful_payment_revenue_gbp"]
            ]
        )

    st.caption(
        "Successful billed payment collection is not accounting-recognised "
        "revenue, net revenue, profit or customer lifetime value."
    )