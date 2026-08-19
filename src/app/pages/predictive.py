"""Frozen Phase 6 predictive decision-support presentation."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st


MODEL_LABELS = {
    "prevalence": "Prevalence baseline",
    "static_logistic": "Static logistic",
    "behavioural_logistic": "Behavioural logistic",
}


def build_model_comparison_frame(
    manifest: Mapping[str, Any],
) -> pd.DataFrame:
    """Build the locked final-test model-comparison table."""

    final_test = manifest["final_test"]

    rows: list[dict[str, Any]] = []

    for key in (
        "prevalence",
        "static_logistic",
        "behavioural_logistic",
    ):
        result = final_test[key]

        rows.append(
            {
                "model": MODEL_LABELS[key],
                "Brier":
                    float(result["brier_score"]),
                "Log loss":
                    float(result["log_loss"]),
                "ROC-AUC":
                    float(result["roc_auc"]),
                "Average precision":
                    float(result["average_precision"]),
            }
        )

    return pd.DataFrame(rows)


def build_targeting_frame(
    manifest: Mapping[str, Any],
) -> pd.DataFrame:
    """Build frozen capacity-constrained targeting evidence."""

    rows: list[dict[str, Any]] = []

    for key, result in manifest[
        "decision_utility"
    ].items():
        capacity = key.split("_percent_capacity")[0]

        rows.append(
            {
                "capacity": f"{capacity}%",
                "targeted_trialists":
                    int(result["targeted_rows"]),
                "non_conversions_captured":
                    int(
                        result[
                            "non_conversions_captured"
                        ]
                    ),
                "capture_rate":
                    float(result["capture_rate"]),
                "lift_vs_population":
                    float(result["lift_vs_population"]),
            }
        )

    return pd.DataFrame(rows)


def render(evidence: Mapping[str, Any]) -> None:
    """Render locked Phase 6 final-test evidence."""

    phase6 = evidence["phase6"]
    manifest = phase6["manifest"]

    final_test = manifest["final_test"]
    behavioural = final_test[
        "behavioural_logistic"
    ]
    delta = final_test[
        "behavioural_minus_static"
    ]

    st.header("Predictive Decision Support")

    st.caption(
        "Locked Phase 6 Day-5 paid-conversion prediction evidence. "
        "Operational non-conversion risk is "
        "`1 - P(paid conversion)`."
    )

    cols = st.columns(
        [1.6, 1.0, 1.0, 1.0, 1.0]
    )

    cols[0].metric(
        "Locked model",
        manifest["selected_model"],
    )

    cols[1].metric(
        "Calibration",
        manifest["calibration"],
    )

    cols[2].metric(
        "Final-test trials",
        f"{manifest['population']['final_test_rows']:,}",
    )

    cols[3].metric(
        "ROC-AUC",
        f"{behavioural['roc_auc']:.3f}",
    )

    cols[4].metric(
        "Average precision",
        f"{behavioural['average_precision']:.3f}",
    )

    st.warning(
        "The behavioural model provides a modest but validated "
        "out-of-time improvement. ROC-AUC is approximately 0.549, "
        "so this is not a high-performing classifier."
    )

    st.subheader("Locked final-test model comparison")

    comparison = build_model_comparison_frame(
        manifest
    )

    st.dataframe(
        comparison,
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "Lower Brier score and log loss are better. Higher ROC-AUC "
        "and average precision are better. Model selection and calibration "
        "were locked before opening the final holdout."
    )

    st.subheader("Validated probability-quality improvement")

    cols = st.columns(3)

    cols[0].metric(
        "Brier delta",
        f"{delta['brier_delta']:+.6f}",
    )

    cols[1].metric(
        "Log-loss delta",
        f"{delta['log_loss_delta']:+.6f}",
    )

    cols[2].metric(
        "Improvement confirmed",
        (
            "Yes"
            if final_test[
                "probability_quality_improvement_confirmed"
            ]
            else "No"
        ),
    )

    brier_ci = delta[
        "brier_95pct_bootstrap_ci"
    ]
    log_ci = delta[
        "log_loss_95pct_bootstrap_ci"
    ]

    st.markdown(
        "**Paired deterministic 95% bootstrap intervals**\n\n"
        f"- Brier delta: "
        f"`[{brier_ci[0]:.6f}, {brier_ci[1]:.6f}]`\n"
        f"- Log-loss delta: "
        f"`[{log_ci[0]:.6f}, {log_ci[1]:.6f}]`\n\n"
        "Negative deltas favour the behavioural model."
    )

    st.subheader("Capacity-constrained prioritisation")

    targeting = build_targeting_frame(
        manifest
    )

    st.dataframe(
        targeting,
        use_container_width=True,
        hide_index=True,
    )

    chart = targeting.copy()

    chart["capture_rate_pct"] = (
        chart["capture_rate"] * 100
    )

    st.bar_chart(
        chart.set_index("capacity")[
            ["capture_rate_pct"]
        ]
    )

    st.caption(
        "Capture rate measures concentration of observed non-conversions "
        "inside a capacity-limited targeting group. It does not measure "
        "the effect of contacting or intervening on those trialists."
    )

    st.subheader("Interpretation boundaries")

    for constraint in manifest["constraints"]:
        st.markdown(f"- {constraint}")

    st.markdown(
        "- Predictive ranking is **not causal evidence**.\n"
        "- Targeting lift does **not** establish intervention effectiveness.\n"
        "- Final-test and June 2026 boundary evidence cannot be used "
        "for further tuning, feature selection, calibration selection "
        "or model-family selection."
    )

    st.success(
        "Frozen final-holdout SHA-256 verified: "
        f"`{phase6['verified_final_results_sha256']}`"
    )