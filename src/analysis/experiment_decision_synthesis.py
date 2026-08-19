"""Final decision synthesis for Pulse Phase 5.

This module combines already-validated Phase 5 evidence.

It does not calculate new experiment outcomes or bypass the reporting semantic
layer. Its purpose is to convert statistical evidence into restrained,
portfolio-quality decision summaries without overstating what the synthetic
experiments establish.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.analysis.experiment_inference import InferenceContractError
from src.analysis.experiment_multiplicity_sensitivity import (
    validate_matching_contexts,
)


DEFAULT_STEP4_PATH = Path(
    "outputs/phase5/step4/live_binary_inference.json"
)

DEFAULT_STEP5_PATH = Path(
    "outputs/phase5/step5/live_continuous_inference.json"
)

DEFAULT_STEP6_PATH = Path(
    "outputs/phase5/step6/multiplicity_and_sensitivity.json"
)

DEFAULT_PORTFOLIO_DIR = Path(
    "outputs/phase5/portfolio"
)

DEFAULT_SUMMARY_DOC = Path(
    "docs/phase5-analysis-summary.md"
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise InferenceContractError(
            f"Required Phase 5 evidence is missing: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def _binary_result_map(
    binary_snapshot: Mapping[str, Any],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (
            str(row["experiment_id"]),
            str(row["metric_key"]),
        ): row
        for row in binary_snapshot["binary_results"]
    }


def _multiplicity_map(
    sensitivity_snapshot: Mapping[str, Any],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (
            str(row["experiment_id"]),
            str(row["metric_key"]),
        ): row
        for row in sensitivity_snapshot["multiplicity_results"]
    }


def _binary_sensitivity_map(
    sensitivity_snapshot: Mapping[str, Any],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    return {
        (
            str(row["experiment_id"]),
            str(row["metric_key"]),
        ): row
        for row in sensitivity_snapshot["binary_sensitivity"]
    }


def build_experiment_decisions(
    binary_snapshot: Mapping[str, Any],
    continuous_snapshot: Mapping[str, Any],
    sensitivity_snapshot: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build one restrained decision summary per experiment."""

    plan_by_experiment: dict[
        str,
        list[Mapping[str, Any]],
    ] = {}

    for row in binary_snapshot["metric_plan"]:
        plan_by_experiment.setdefault(
            str(row["experiment_id"]),
            [],
        ).append(row)

    binary_results = _binary_result_map(
        binary_snapshot
    )

    multiplicity = _multiplicity_map(
        sensitivity_snapshot
    )

    binary_sensitivity = _binary_sensitivity_map(
        sensitivity_snapshot
    )

    continuous_key = (
        str(continuous_snapshot["experiment_id"]),
        str(continuous_snapshot["metric_key"]),
    )

    decisions: list[dict[str, Any]] = []

    for experiment_id in sorted(plan_by_experiment):
        plan_rows = plan_by_experiment[experiment_id]

        experiment_name = str(
            plan_rows[0]["experiment_name"]
        )

        primary_rows = [
            row
            for row in plan_rows
            if row["metric_role"] == "primary"
        ]

        if len(primary_rows) != 1:
            raise InferenceContractError(
                "Each experiment must contain exactly one primary metric"
            )

        primary_plan = primary_rows[0]
        primary_metric = str(primary_plan["metric_key"])

        completed_metrics: list[str] = []
        excluded_metrics: list[dict[str, str]] = []

        evidence_rows: list[dict[str, Any]] = []

        for plan_row in plan_rows:
            metric_key = str(plan_row["metric_key"])
            role = str(plan_row["metric_role"])

            binary_key = (
                experiment_id,
                metric_key,
            )

            if binary_key in binary_results:
                result = binary_results[binary_key]

                sensitivity = binary_sensitivity.get(
                    binary_key
                )

                multiplicity_row = multiplicity.get(
                    binary_key
                )

                completed_metrics.append(metric_key)

                evidence_rows.append(
                    {
                        "metric_role": role,
                        "metric_key": metric_key,
                        "outcome_type": "binary",
                        "effect": float(
                            result["percentage_point_effect"]
                        ),
                        "effect_unit": "percentage_points",
                        "confidence_interval_low": float(
                            result["confidence_interval_low"]
                        ) * 100.0,
                        "confidence_interval_high": float(
                            result["confidence_interval_high"]
                        ) * 100.0,
                        "raw_p_value": float(
                            result["p_value"]
                        ),
                        "holm_adjusted_p_value": (
                            None
                            if multiplicity_row is None
                            else float(
                                multiplicity_row[
                                    "holm_adjusted_p_value"
                                ]
                            )
                        ),
                        "statistically_detectable": bool(
                            result["statistically_detectable"]
                        ),
                        "mde": (
                            None
                            if sensitivity is None
                            else sensitivity["mde_pp"]
                        ),
                        "mde_unit": "percentage_points",
                    }
                )

                continue

            if (
                (
                    experiment_id,
                    metric_key,
                )
                == continuous_key
            ):
                result = continuous_snapshot["inference"]

                continuous_sensitivity = (
                    sensitivity_snapshot[
                        "continuous_sensitivity"
                    ]
                )

                multiplicity_row = multiplicity.get(
                    (
                        experiment_id,
                        metric_key,
                    )
                )

                completed_metrics.append(metric_key)

                evidence_rows.append(
                    {
                        "metric_role": role,
                        "metric_key": metric_key,
                        "outcome_type": "continuous",
                        "effect": float(
                            result["absolute_effect"]
                        ),
                        "effect_unit": "GBP_per_assigned_user",
                        "confidence_interval_low": float(
                            result["confidence_interval_low"]
                        ),
                        "confidence_interval_high": float(
                            result["confidence_interval_high"]
                        ),
                        "raw_p_value": float(
                            result["permutation_p_value"]
                        ),
                        "holm_adjusted_p_value": (
                            None
                            if multiplicity_row is None
                            else float(
                                multiplicity_row[
                                    "holm_adjusted_p_value"
                                ]
                            )
                        ),
                        "statistically_detectable": bool(
                            result["statistically_detectable"]
                        ),
                        "mde": float(
                            continuous_sensitivity["mde_gbp"]
                        ),
                        "mde_unit": "GBP_per_assigned_user",
                    }
                )

                continue

            excluded_metrics.append(
                {
                    "metric_role": role,
                    "metric_key": metric_key,
                    "reason": str(
                        plan_row["inference_status"]
                    ),
                }
            )

        primary_key = (
            experiment_id,
            primary_metric,
        )

        primary_result = binary_results.get(
            primary_key
        )

        if primary_result is None:
            decision_status = (
                "not_decision_ready_primary_metric_unavailable"
            )

            decision = (
                "Do not make a treatment rollout decision from Phase 5. "
                "The configured primary metric is not currently available "
                "as a supported canonical inferential outcome."
            )

        elif bool(
            primary_result["statistically_detectable"]
        ):
            decision_status = (
                "detectable_primary_effect_requires_business_review"
            )

            decision = (
                "The prespecified primary outcome is statistically "
                "detectable. Review effect size, uncertainty, guardrails "
                "and business relevance before any rollout decision."
            )

        elif excluded_metrics:
            decision_status = (
                "primary_not_detectable_supporting_metrics_incomplete"
            )

            decision = (
                "The canonical primary outcome does not show a statistically "
                "detectable treatment-minus-control difference, while one "
                "or more configured supporting metrics remain unavailable. "
                "Do not interpret this as proof of no treatment effect."
            )

        else:
            all_completed_non_detectable = all(
                not bool(
                    row["statistically_detectable"]
                )
                for row in evidence_rows
            )

            if all_completed_non_detectable:
                decision_status = (
                    "no_detectable_effect_in_completed_metric_family"
                )

                decision = (
                    "The completed canonical primary and supportive outcome "
                    "family provides no statistically detectable evidence "
                    "supporting treatment rollout. This does not prove exact "
                    "equivalence between treatment and control."
                )

            else:
                decision_status = (
                    "mixed_completed_evidence_requires_review"
                )

                decision = (
                    "The completed experiment evidence is mixed and requires "
                    "metric-level business review before any rollout decision."
                )

        decisions.append(
            {
                "experiment_id": experiment_id,
                "experiment_name": experiment_name,
                "configured_metric_count": len(plan_rows),
                "completed_inference_metric_count":
                    len(completed_metrics),
                "excluded_metric_count":
                    len(excluded_metrics),
                "primary_metric": primary_metric,
                "primary_contract_status":
                    primary_plan["support_status"],
                "primary_inference_status":
                    primary_plan["inference_status"],
                "decision_status": decision_status,
                "decision": decision,
                "completed_metrics":
                    completed_metrics,
                "excluded_metrics":
                    excluded_metrics,
                "evidence":
                    evidence_rows,
            }
        )

    return decisions


def build_phase5_snapshot(
    *,
    binary_path: Path = DEFAULT_STEP4_PATH,
    continuous_path: Path = DEFAULT_STEP5_PATH,
    sensitivity_path: Path = DEFAULT_STEP6_PATH,
) -> dict[str, Any]:
    binary = _load_json(binary_path)
    continuous = _load_json(continuous_path)
    sensitivity = _load_json(sensitivity_path)

    context = validate_matching_contexts(
        binary["context"],
        continuous["context"],
        sensitivity["context"],
    )

    decisions = build_experiment_decisions(
        binary,
        continuous,
        sensitivity,
    )

    detectable_completed_results = sum(
        bool(row["statistically_detectable"])
        for decision in decisions
        for row in decision["evidence"]
    )

    total_completed_results = sum(
        len(decision["evidence"])
        for decision in decisions
    )

    return {
        "synthetic_data": True,
        "phase": 5,
        "step": 7,
        "status": "ready_for_formal_closure",
        "analysis_type":
            "randomized_experiment_statistical_inference_synthesis",
        "context": context,
        "experiment_count": len(decisions),
        "completed_inference_result_count":
            total_completed_results,
        "statistically_detectable_result_count":
            detectable_completed_results,
        "decisions": decisions,
        "methodology_summary": {
            "primary_population":
                "assigned_mature",
            "binary_effect_direction":
                "treatment_minus_control",
            "binary_confidence_interval":
                "newcombe_wilson",
            "binary_hypothesis_test":
                "two_proportion_z_test",
            "continuous_estimand":
                "treatment_minus_control_mean",
            "continuous_confidence_interval":
                "nonparametric_percentile_bootstrap",
            "continuous_hypothesis_test":
                "randomization_permutation_test",
            "supportive_multiplicity":
                "holm_within_completed_experiment_family",
            "design_sensitivity":
                "approximate_minimum_detectable_effect",
            "retrospective_observed_power":
                False,
            "causal_scope":
                "randomized_assigned_mature_contrast_only",
        },
        "headline": (
            "No completed canonical Pulse experiment outcome produced a "
            "statistically detectable treatment-minus-control difference "
            "at the current production snapshot. Several configured metrics "
            "remain deferred or non-canonical, so absence of detectability "
            "must not be interpreted as proof of zero effect."
        ),
    }


def render_portfolio_markdown(
    snapshot: Mapping[str, Any],
) -> str:
    context = snapshot["context"]

    lines = [
        "# Pulse Phase 5 - Experimentation & Statistical Inference",
        "",
        (
            "> Pulse is a synthetic product analytics and subscription "
            "intelligence platform. All experiment data and results are "
            "synthetic."
        ),
        "",
        "## Executive result",
        "",
        snapshot["headline"],
        "",
        "## Production lineage",
        "",
        (
            f"- Ingestion batch: "
            f"`{context['ingestion_batch_id']}`"
        ),
        (
            f"- Analytics build: "
            f"`{context['analytics_build_run_id']}`"
        ),
        (
            f"- Observation cutoff: "
            f"`{context['observation_cutoff_at']}`"
        ),
        "- Primary population: `assigned_mature`",
        "",
        "## Experiment decisions",
        "",
    ]

    for decision in snapshot["decisions"]:
        lines.extend(
            [
                f"### {decision['experiment_name']}",
                "",
                (
                    f"- Decision status: "
                    f"`{decision['decision_status']}`"
                ),
                (
                    f"- Completed inferential metrics: "
                    f"{decision['completed_inference_metric_count']} / "
                    f"{decision['configured_metric_count']}"
                ),
                (
                    f"- Primary metric: "
                    f"`{decision['primary_metric']}`"
                ),
                "",
                decision["decision"],
                "",
            ]
        )

        if decision["evidence"]:
            lines.extend(
                [
                    "| Role | Metric | Effect | 95% CI | Raw p | Holm p | MDE |",
                    "|---|---|---:|---:|---:|---:|---:|",
                ]
            )

            for row in decision["evidence"]:
                if row["effect_unit"] == "percentage_points":
                    effect = f"{row['effect']:.2f} pp"
                    ci = (
                        f"[{row['confidence_interval_low']:.2f}, "
                        f"{row['confidence_interval_high']:.2f}] pp"
                    )

                    mde = (
                        "n/a"
                        if row["mde"] is None
                        else f"{row['mde']:.2f} pp"
                    )
                else:
                    effect = f"GBP {row['effect']:.4f}"
                    ci = (
                        f"[GBP {row['confidence_interval_low']:.4f}, "
                        f"GBP {row['confidence_interval_high']:.4f}]"
                    )

                    mde = (
                        "n/a"
                        if row["mde"] is None
                        else f"GBP {row['mde']:.4f}"
                    )

                raw_p = f"{row['raw_p_value']:.6g}"

                holm_p = (
                    "n/a"
                    if row["holm_adjusted_p_value"] is None
                    else f"{row['holm_adjusted_p_value']:.6g}"
                )

                lines.append(
                    "| "
                    f"{row['metric_role']} | "
                    f"`{row['metric_key']}` | "
                    f"{effect} | "
                    f"{ci} | "
                    f"{raw_p} | "
                    f"{holm_p} | "
                    f"{mde} |"
                )

            lines.append("")

        if decision["excluded_metrics"]:
            lines.append(
                "Unavailable configured metrics:"
            )

            for row in decision["excluded_metrics"]:
                lines.append(
                    f"- `{row['metric_key']}` "
                    f"({row['metric_role']}): "
                    f"`{row['reason']}`"
                )

            lines.append("")

    lines.extend(
        [
            "## Statistical architecture",
            "",
            "- Randomized assignment integrity checked before inference.",
            "- Sample-ratio mismatch diagnostics respect configured allocations.",
            "- Immature analysis windows are excluded from primary denominators.",
            "- Binary effects use treatment minus control proportions.",
            "- Binary uncertainty uses Newcombe/Wilson score intervals.",
            "- Continuous commercial uncertainty uses deterministic bootstrap.",
            "- Continuous commercial testing uses randomized-label permutation.",
            "- Supportive outcomes use Holm multiplicity adjustment.",
            "- MDE diagnostics are reported instead of retrospective observed power.",
            "- Deferred and non-canonical KPIs are not invented in Python.",
            "",
            "## Commercial metric interpretation",
            "",
            (
                "`revenue_per_assigned_user_30d` represents successful billed "
                "payment collection per assigned user. It is not accounting-"
                "recognised revenue, net revenue, profit or customer LTV."
            ),
            "",
            "## What Phase 5 does not claim",
            "",
            "- A non-significant result does not prove exact equality.",
            "- Statistical significance is not automatically business significance.",
            "- Exposure-conditioned subsets are not substituted for the randomized primary estimand.",
            "- Deferred metrics are not reconstructed from similar-looking event fields.",
            "- Phase 5 does not perform observational causal inference.",
            "- Phase 5 does not introduce predictive ML, forecasting or Streamlit.",
            "",
        ]
    )

    return "\n".join(lines)


def render_forest_svg(
    snapshot: Mapping[str, Any],
) -> str:
    """Render a dependency-free forest plot for completed binary effects."""

    rows: list[dict[str, Any]] = []

    for decision in snapshot["decisions"]:
        for row in decision["evidence"]:
            if row["outcome_type"] != "binary":
                continue

            rows.append(
                {
                    "experiment_name":
                        decision["experiment_name"],
                    **row,
                }
            )

    if not rows:
        raise InferenceContractError(
            "No binary inference results exist for forest plot"
        )

    low = min(
        min(
            float(row["confidence_interval_low"]),
            float(row["effect"]),
            0.0,
        )
        for row in rows
    )

    high = max(
        max(
            float(row["confidence_interval_high"]),
            float(row["effect"]),
            0.0,
        )
        for row in rows
    )

    span = high - low

    if span <= 0:
        span = 1.0

    padding = span * 0.12
    axis_low = low - padding
    axis_high = high + padding

    width = 1100
    left = 500
    right = 70
    plot_width = width - left - right
    row_height = 72
    top = 115
    bottom = 80
    height = top + len(rows) * row_height + bottom

    def x(value: float) -> float:
        return (
            left
            + (
                (value - axis_low)
                / (axis_high - axis_low)
            )
            * plot_width
        )

    svg: list[str] = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
        ),
        '<rect width="100%" height="100%" fill="white"/>',
        (
            '<text x="40" y="42" font-family="Arial" '
            'font-size="24" font-weight="bold">'
            'Pulse Phase 5 - Binary Experiment Effects'
            '</text>'
        ),
        (
            '<text x="40" y="70" font-family="Arial" '
            'font-size="14">'
            'Synthetic data; treatment minus control; 95% confidence intervals'
            '</text>'
        ),
    ]

    zero_x = x(0.0)

    svg.append(
        (
            f'<line x1="{zero_x:.2f}" y1="{top - 20}" '
            f'x2="{zero_x:.2f}" '
            f'y2="{height - bottom + 10}" '
            'stroke="#777" stroke-width="1.5" '
            'stroke-dasharray="5,5"/>'
        )
    )

    for index, row in enumerate(rows):
        y = top + index * row_height

        label = (
            f"{row['experiment_name']} - "
            f"{row['metric_role']} - "
            f"{row['metric_key']}"
        )

        svg.append(
            (
                f'<text x="40" y="{y + 5}" '
                'font-family="Arial" font-size="13">'
                f'{html.escape(label)}'
                '</text>'
            )
        )

        ci_low = x(
            float(row["confidence_interval_low"])
        )

        ci_high = x(
            float(row["confidence_interval_high"])
        )

        point = x(
            float(row["effect"])
        )

        svg.append(
            (
                f'<line x1="{ci_low:.2f}" y1="{y}" '
                f'x2="{ci_high:.2f}" y2="{y}" '
                'stroke="#222" stroke-width="3"/>'
            )
        )

        svg.append(
            (
                f'<line x1="{ci_low:.2f}" y1="{y - 7}" '
                f'x2="{ci_low:.2f}" y2="{y + 7}" '
                'stroke="#222" stroke-width="2"/>'
            )
        )

        svg.append(
            (
                f'<line x1="{ci_high:.2f}" y1="{y - 7}" '
                f'x2="{ci_high:.2f}" y2="{y + 7}" '
                'stroke="#222" stroke-width="2"/>'
            )
        )

        svg.append(
            (
                f'<circle cx="{point:.2f}" cy="{y}" r="6" '
                'fill="#222"/>'
            )
        )

    axis_y = height - bottom + 25

    svg.append(
        (
            f'<line x1="{left}" y1="{axis_y}" '
            f'x2="{width - right}" y2="{axis_y}" '
            'stroke="#222" stroke-width="1"/>'
        )
    )

    for fraction in (
        0.0,
        0.25,
        0.50,
        0.75,
        1.0,
    ):
        value = (
            axis_low
            + fraction
            * (axis_high - axis_low)
        )

        tick_x = x(value)

        svg.append(
            (
                f'<line x1="{tick_x:.2f}" y1="{axis_y}" '
                f'x2="{tick_x:.2f}" y2="{axis_y + 7}" '
                'stroke="#222" stroke-width="1"/>'
            )
        )

        svg.append(
            (
                f'<text x="{tick_x:.2f}" y="{axis_y + 27}" '
                'text-anchor="middle" '
                'font-family="Arial" font-size="12">'
                f'{value:.1f} pp'
                '</text>'
            )
        )

    svg.append(
        (
            f'<text x="{left + plot_width / 2:.2f}" '
            f'y="{height - 15}" text-anchor="middle" '
            'font-family="Arial" font-size="14">'
            'Treatment minus control effect'
            '</text>'
        )
    )

    svg.append("</svg>")

    return "\n".join(svg)


def export_phase5_portfolio(
    snapshot: Mapping[str, Any],
    *,
    output_dir: Path = DEFAULT_PORTFOLIO_DIR,
    summary_doc: Path = DEFAULT_SUMMARY_DOC,
) -> dict[str, Path]:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_doc.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    portfolio_summary = (
        output_dir
        / "phase5_portfolio_summary.md"
    )

    snapshot_path = (
        output_dir
        / "phase5_experiment_decisions.json"
    )

    forest_path = (
        output_dir
        / "binary_effects_forest.svg"
    )

    manifest_path = (
        output_dir
        / "phase5_manifest.json"
    )

    markdown = render_portfolio_markdown(
        snapshot
    )

    portfolio_summary.write_text(
        markdown,
        encoding="utf-8",
    )

    summary_doc.write_text(
        markdown,
        encoding="utf-8",
    )

    snapshot_path.write_text(
        json.dumps(
            snapshot,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    forest_path.write_text(
        render_forest_svg(
            snapshot
        ),
        encoding="utf-8",
    )

    manifest = {
        "phase": 5,
        "status": "ready_for_formal_closure",
        "synthetic_data": True,
        "context": snapshot["context"],
        "experiment_count":
            snapshot["experiment_count"],
        "completed_inference_result_count":
            snapshot[
                "completed_inference_result_count"
            ],
        "statistically_detectable_result_count":
            snapshot[
                "statistically_detectable_result_count"
            ],
        "files": [
            portfolio_summary.name,
            snapshot_path.name,
            forest_path.name,
        ],
        "documentation": [
            str(summary_doc),
            "docs/phase5-experimentation-inference-contract.md",
        ],
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "portfolio_summary":
            portfolio_summary,
        "decision_json":
            snapshot_path,
        "forest_svg":
            forest_path,
        "manifest":
            manifest_path,
        "analysis_summary":
            summary_doc,
    }


def main() -> None:
    snapshot = build_phase5_snapshot()

    paths = export_phase5_portfolio(
        snapshot
    )

    print("")
    print("=" * 72)
    print(
        "PHASE 5 - STEP 7 "
        "FINAL DECISION SYNTHESIS"
    )
    print("=" * 72)

    print("")
    print(snapshot["headline"])

    print("")
    print("Experiment decisions:")

    for row in snapshot["decisions"]:
        print("")
        print(row["experiment_name"])
        print(
            "  completed metrics:",
            f"{row['completed_inference_metric_count']}/"
            f"{row['configured_metric_count']}",
        )
        print(
            "  status:",
            row["decision_status"],
        )
        print(
            "  decision:",
            row["decision"],
        )

    print("")
    print(
        "Completed inference results:",
        snapshot[
            "completed_inference_result_count"
        ],
    )

    print(
        "Statistically detectable results:",
        snapshot[
            "statistically_detectable_result_count"
        ],
    )

    print("")
    print("Outputs:")

    for name, path in paths.items():
        print(
            f"  {name}: {path}"
        )


if __name__ == "__main__":
    main()
