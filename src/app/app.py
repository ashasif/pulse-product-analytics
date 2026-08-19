"""Pulse Streamlit application."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from src.app.components import (
    render_lineage,
    render_synthetic_notice,
)
from src.app.data_access import load_reporting_context
from src.app.evidence import (
    EvidenceIntegrityError,
    load_portfolio_evidence,
)
from src.app.pages import (
    acquisition,
    engagement,
    overview,
    retention,
)


PAGE_REGISTRY: dict[str, Callable] = {
    "Executive Overview": overview.render,
    "Growth & Acquisition": acquisition.render,
    "Engagement & Monetisation": engagement.render,
    "Retention & Lifecycle": retention.render,
}


def main() -> None:
    """Render the Pulse business analytics application."""

    st.set_page_config(
        page_title="Pulse Product Analytics",
        page_icon="📊",
        layout="wide",
    )

    st.title(
        "Pulse — Product Analytics & Subscription Intelligence"
    )

    render_synthetic_notice()

    try:
        evidence = load_portfolio_evidence()
        del evidence
        st.sidebar.success(
            "Frozen Phase 5/6 evidence integrity verified."
        )
    except EvidenceIntegrityError as exc:
        st.sidebar.error(
            "Frozen analytical evidence failed integrity verification."
        )
        st.error(str(exc))
        return

    try:
        context = load_reporting_context()
    except Exception as exc:
        st.error(
            "The live PostgreSQL reporting layer is unavailable. "
            "Configure the PULSE_DB_* environment variables and ensure "
            "the read-only reporting database is reachable."
        )
        st.caption(
            f"Connection error type: {type(exc).__name__}"
        )
        return

    render_lineage(context)

    st.sidebar.divider()

    selected_page = st.sidebar.radio(
        "Business view",
        list(PAGE_REGISTRY),
    )

    renderer = PAGE_REGISTRY[selected_page]

    try:
        renderer(context)
    except Exception as exc:
        st.error(
            "The selected business view could not be loaded from "
            "the canonical reporting layer."
        )
        st.caption(
            f"Dashboard error type: {type(exc).__name__}"
        )


if __name__ == "__main__":
    main()