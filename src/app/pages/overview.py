"""Executive Overview page."""

from __future__ import annotations

from typing import Mapping, Any

import streamlit as st

from src.app.components import (
    first_row,
    format_gbp,
    format_integer,
    format_percent,
    numeric_series,
)
from src.app.data_access import load_named_query


def render(context: Mapping[str, Any]) -> None:
    st.header("Executive Overview")
    st.caption(
        "Canonical product, funnel, monetisation and retention "
        "evidence from the validated reporting semantic layer."
    )

    build_id = int(context["analytics_build_run_id"])

    product = first_row(
        load_named_query(
            "overview_product",
            analytics_build_run_id=build_id,
        )
    )

    funnel = first_row(
        load_named_query(
            "overview_funnel",
            analytics_build_run_id=build_id,
        )
    )

    revenue = first_row(
        load_named_query(
            "overview_revenue",
            analytics_build_run_id=build_id,
        )
    )

    retention = first_row(
        load_named_query(
            "retention_summary",
            analytics_build_run_id=build_id,
        )
    )

    cols = st.columns(5)

    cols[0].metric(
        "Installations",
        format_integer(product["installation_count"]),
    )
    cols[1].metric(
        "Signups",
        format_integer(product["signup_count"]),
    )
    cols[2].metric(
        "Install → Signup",
        format_percent(funnel["install_to_signup_rate"]),
    )
    cols[3].metric(
        "Mature Trial → Paid",
        format_percent(
            funnel["trial_to_paid_conversion_rate"]
        ),
    )
    cols[4].metric(
        "D30 Paid Retention",
        format_percent(retention["paid_retention_d30"]),
    )

    cols = st.columns(5)

    cols[0].metric(
        "D90 Retention",
        format_percent(retention["paid_retention_d90"]),
    )
    cols[1].metric(
        "D180 Retention",
        format_percent(retention["paid_retention_d180"]),
    )
    cols[2].metric(
        "D365 Retention",
        format_percent(retention["paid_retention_d365"]),
    )
    cols[3].metric(
        "Successful Billed Collection",
        format_gbp(
            revenue["successful_payment_revenue_gbp"]
        ),
    )
    cols[4].metric(
        "Payment Failure",
        format_percent(revenue["payment_failure_rate"]),
    )

    st.subheader("Product growth")

    trend = load_named_query(
        "monthly_product_trend",
        analytics_build_run_id=build_id,
    )

    trend = numeric_series(
        trend,
        [
            "installation_count",
            "signup_count",
            "trial_start_count",
            "paid_subscription_start_count",
        ],
    )

    if not trend.empty:
        chart = trend.set_index("month")

        st.line_chart(
            chart[
                [
                    "installation_count",
                    "signup_count",
                ]
            ]
        )

        st.caption(
            "Monthly installations and signups. Counts are aggregated "
            "from canonical daily reporting KPIs."
        )

    st.subheader("Business interpretation")

    st.markdown(
        "- Funnel and retention rates use canonical numerators and "
        "maturity-controlled denominators.\n"
        "- Successful payment revenue means billed cash collection, "
        "not accounting-recognised or net revenue.\n"
        "- The largest long-horizon question should be assessed through "
        "the dedicated Retention & Lifecycle page rather than inferred "
        "from top-of-funnel volume alone."
    )