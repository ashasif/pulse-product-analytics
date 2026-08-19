"""Frozen Phase 5 experimentation evidence presentation."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from src.app.evidence import resolve_repo_path


def format_effect(result: Mapping[str, Any]) -> str:
    """Format one frozen experiment effect without changing its meaning."""

    effect = result["effect"]
    unit = result.get("effect_unit")

    if unit == "percentage_points":
        return f"{float(effect):+.2f} pp"

    if unit == "GBP_per_assigned_user":
        return f"£{float(effect):+.4f}"

    return f"{float(effect):+.4f}"


def format_interval(result: Mapping[str, Any]) -> str:
    """Format the frozen 95% confidence interval."""

    low = float(result["confidence_interval_low"])
    high = float(result["confidence_interval_high"])
    unit = result.get("effect_unit")

    if unit == "percentage_points":
        return f"[{low:.2f}, {high:.2f}] pp"

    if unit == "GBP_per_assigned_user":
        return f"[£{low:.4f}, £{high:.4f}]"

    return f"[{low:.4f}, {high:.4f}]"


def format_p_value(value: Any) -> str:
    """Format a frozen p-value for presentation."""

    if value is None:
        return "—"

    return f"{float(value):.4f}"


def format_mde(result: Mapping[str, Any]) -> str:
    """Format frozen MDE evidence."""

    value = result.get("mde")

    if value is None:
        return "—"

    unit = result.get("mde_unit")

    if unit == "percentage_points":
        return f"{float(value):.2f} pp"

    if unit == "GBP_per_assigned_user":
        return f"£{float(value):.4f}"

    return f"{float(value):.4f}"


def build_experiment_evidence_frame(
    payload: Mapping[str, Any],
) -> pd.DataFrame:
    """Convert frozen Phase 5 results into a presentation table."""

    rows: list[dict[str, Any]] = []

    for decision in payload["decisions"]:
        for result in decision["evidence"]:
            rows.append(
                {
                    "experiment_id":
                        decision["experiment_id"],
                    "experiment_name":
                        decision["experiment_name"],
                    "role":
                        result["metric_role"],
                    "metric":
                        result["metric_key"],
                    "effect":
                        format_effect(result),
                    "95% CI":
                        format_interval(result),
                    "raw p":
                        format_p_value(
                            result["raw_p_value"]
                        ),
                    "Holm p":
                        format_p_value(
                            result[
                                "holm_adjusted_p_value"
                            ]
                        ),
                    "detectable":
                        bool(
                            result[
                                "statistically_detectable"
                            ]
                        ),
                    "MDE":
                        format_mde(result),
                }
            )

    return pd.DataFrame(rows)


def build_excluded_metrics_frame(
    decision: Mapping[str, Any],
) -> pd.DataFrame:
    """Return configured metrics excluded from approved inference."""

    rows = [
        {
            "role": item["metric_role"],
            "metric": item["metric_key"],
            "reason": item["reason"],
        }
        for item in decision["excluded_metrics"]
    ]

    return pd.DataFrame(rows)


def render(evidence: Mapping[str, Any]) -> None:
    """Render frozen randomized experiment evidence."""

    phase5 = evidence["phase5"]

    st.header("Experimentation & Statistical Inference")

    st.caption(
        "Frozen Phase 5 randomized-experiment evidence. "
        "The dashboard presents approved inferential outputs and "
        "does not rerun hypothesis tests."
    )

    cols = st.columns(3)

    cols[0].metric(
        "Experiments",
        phase5["experiment_count"],
    )

    cols[1].metric(
        "Completed outcomes",
        phase5["completed_inference_result_count"],
    )

    cols[2].metric(
        "Statistically detectable",
        phase5["statistically_detectable_result_count"],
    )

    st.warning(
        "No completed canonical Pulse experiment outcome produced "
        "a statistically detectable treatment-minus-control difference. "
        "This does not prove that treatment and control are exactly equal."
    )

    forest_path = resolve_repo_path(
        "outputs/phase5/portfolio/binary_effects_forest.svg"
    )

    if forest_path.is_file():
        st.subheader("Binary effect evidence")

        st.image(
            str(forest_path),
            caption=(
                "Frozen Phase 5 binary treatment-minus-control "
                "effect estimates with approved uncertainty intervals."
            ),
        )

    evidence_frame = build_experiment_evidence_frame(
        phase5
    )

    st.subheader("Experiment decisions")

    for decision in phase5["decisions"]:
        with st.expander(
            decision["experiment_name"],
            expanded=True,
        ):
            cols = st.columns(4)

            cols[0].metric(
                "Completed",
                (
                    f"{decision['completed_inference_metric_count']}"
                    f"/{decision['configured_metric_count']}"
                ),
            )

            cols[1].metric(
                "Excluded",
                decision["excluded_metric_count"],
            )

            cols[2].metric(
                "Primary metric",
                decision["primary_metric"],
            )

            cols[3].metric(
                "Detectable outcomes",
                sum(
                    bool(item["statistically_detectable"])
                    for item in decision["evidence"]
                ),
            )

            st.markdown(
                f"**Decision status:** "
                f"`{decision['decision_status']}`"
            )

            st.write(decision["decision"])

            experiment_frame = evidence_frame[
                evidence_frame["experiment_id"]
                == decision["experiment_id"]
            ].drop(
                columns=[
                    "experiment_id",
                    "experiment_name",
                ]
            )

            if not experiment_frame.empty:
                st.dataframe(
                    experiment_frame,
                    use_container_width=True,
                    hide_index=True,
                )

            excluded = build_excluded_metrics_frame(
                decision
            )

            if not excluded.empty:
                st.markdown(
                    "**Unavailable configured outcomes**"
                )

                st.dataframe(
                    excluded,
                    use_container_width=True,
                    hide_index=True,
                )

    methodology = phase5["methodology_summary"]

    st.subheader("Inference contract")

    st.markdown(
        "- Primary population: "
        f"`{methodology['primary_population']}`\n"
        "- Binary effect direction: "
        f"`{methodology['binary_effect_direction']}`\n"
        "- Binary confidence interval: "
        f"`{methodology['binary_confidence_interval']}`\n"
        "- Continuous confidence interval: "
        f"`{methodology['continuous_confidence_interval']}`\n"
        "- Continuous hypothesis test: "
        f"`{methodology['continuous_hypothesis_test']}`\n"
        "- Supportive multiplicity control: "
        f"`{methodology['supportive_multiplicity']}`"
    )

    st.caption(
        "Unavailable or deferred outcomes remain unavailable. "
        "The application does not reconstruct them from similar-looking "
        "events or redefine canonical experiment metrics."
    )