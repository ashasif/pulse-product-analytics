"""Methodology, metric contracts and analytical boundaries."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from src.app.components import (
    dataframe_for_display,
)
from src.app.data_access import (
    load_metric_definitions,
)


def render(
    context: Mapping[str, Any],
) -> None:
    """Render the canonical methodology and governance view."""

    st.header("Methodology & Contracts")

    st.caption(
        "The dashboard is a presentation layer over validated "
        "analytical contracts. It does not redefine canonical KPIs."
    )

    metrics = load_metric_definitions()

    if metrics.empty:
        st.warning(
            "No canonical metric definitions are available."
        )
        return

    counts = (
        metrics["support_status"]
        .value_counts()
        .to_dict()
    )

    cols = st.columns(4)

    cols[0].metric(
        "Metric contracts",
        len(metrics),
    )

    cols[1].metric(
        "Supported",
        counts.get("supported", 0),
    )

    cols[2].metric(
        "Deferred",
        counts.get("deferred", 0),
    )

    cols[3].metric(
        "Unsupported",
        counts.get("unsupported", 0),
    )

    st.subheader("Canonical metric registry")

    st.dataframe(
        dataframe_for_display(
            metrics[
                [
                    "metric_key",
                    "metric_name",
                    "metric_domain",
                    "metric_grain",
                    "metric_unit",
                    "support_status",
                    "definition",
                    "denominator_definition",
                    "caveat",
                ]
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Analytical boundaries")

    st.markdown(
        "- Business-facing KPI logic is owned by PostgreSQL "
        "`reporting.*`.\n"
        "- Trial conversion and paid retention use maturity-controlled "
        "denominators.\n"
        "- Successful payment revenue means successful billed payment "
        "collection, not accounting-recognised revenue or net revenue.\n"
        "- Phase 5 randomized inference is presented from frozen approved "
        "artifacts rather than rerun by the dashboard.\n"
        "- Phase 6 final-test evidence is frozen and cannot be used for "
        "additional tuning, calibration selection or model selection.\n"
        "- Predictive ranking is not causal evidence.\n"
        "- All Pulse customer behaviour is synthetic."
    )

    st.subheader("Production lineage")

    st.write(
        f"Ingestion batch: `{context['ingestion_batch_id']}`"
    )

    st.write(
        f"Analytics build: `{context['analytics_build_run_id']}`"
    )