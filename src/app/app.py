"""Pulse Streamlit application foundation."""

from __future__ import annotations

import streamlit as st

from src.app.data_access import load_reporting_context
from src.app.evidence import (
    EvidenceIntegrityError,
    load_portfolio_evidence,
)


def main() -> None:
    """Render the Phase 7 application shell."""

    st.set_page_config(
        page_title="Pulse Product Analytics",
        page_icon="📊",
        layout="wide",
    )

    st.title("Pulse — Product Analytics & Subscription Intelligence")

    st.info(
        "Pulse uses synthetic customer behaviour created for portfolio "
        "and learning purposes. Dashboard results demonstrate analytical "
        "methodology and should not be interpreted as production customer evidence."
    )

    st.subheader("Analytical snapshot")

    try:
        context = load_reporting_context()

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Ingestion batch",
            context["ingestion_batch_id"],
        )

        col2.metric(
            "Analytics build",
            context["analytics_build_run_id"],
        )

        col3.metric(
            "Observation cutoff",
            str(context["observation_cutoff_at"]),
        )

    except Exception as exc:
        st.error(
            "Live PostgreSQL reporting context is currently unavailable. "
            "Configure the PULSE_DB_* environment variables to enable "
            "database-driven business analytics."
        )
        st.caption(
            f"Database connection detail: {type(exc).__name__}"
        )

    st.subheader("Frozen analytical evidence")

    try:
        evidence = load_portfolio_evidence()

        phase5 = evidence["phase5"]
        phase6 = evidence["phase6"]["manifest"]

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Experiments",
            phase5["experiment_count"],
        )

        col2.metric(
            "Detectable experiment outcomes",
            phase5["statistically_detectable_result_count"],
        )

        col3.metric(
            "Locked predictive model",
            phase6["selected_model"],
        )

        st.success(
            "Phase 5 experiment evidence loaded and Phase 6 frozen "
            "final-holdout integrity verified."
        )

    except EvidenceIntegrityError as exc:
        st.error(
            "Frozen portfolio evidence failed its integrity contract."
        )
        st.code(str(exc))

    st.caption(
        "Phase 7 is a presentation layer. Canonical business KPIs remain "
        "defined in PostgreSQL reporting.*, Phase 5 inference remains frozen, "
        "and Phase 6 final-test evidence cannot be used for model tuning."
    )


if __name__ == "__main__":
    main()