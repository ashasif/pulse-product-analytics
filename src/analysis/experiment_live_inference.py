"""Live randomized-experiment inference for Pulse Phase 5.

This module binds the validated statistical engine to the reporting semantic
layer.

Important controls:

- reporting.* is the only business source;
- metric contracts are checked before inference;
- deferred and unknown metrics are not reconstructed;
- primary analysis uses assigned-mature users;
- supported binary metrics are mapped only to canonical reporting outcome
  primitives;
- sample-ratio mismatch must pass before inference is considered valid;
- multiplicity adjustment is deferred until the complete inferential family
  is available, including supported non-binary metrics.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.analysis.experiment_inference import (
    BinaryInferenceResult,
    InferenceContractError,
    infer_binary_outcome,
    validate_common_lineage,
    validate_variant_summary_rows,
)
from src.analysis.experiment_integrity import (
    SampleRatioResult,
    build_sample_ratio_result,
)
from src.analysis.reporting_client import (
    ReportingContext,
    fetch_reporting_rows,
    get_metric_contracts,
    get_reporting_context,
    require_supported_metrics,
)
from src.ingestion.database import DatabaseConfig


# ---------------------------------------------------------------------------
# Canonical reporting-field bindings
#
# These are not KPI formulas.
#
# They map an already-canonical supported metric key to the boolean outcome
# primitive exposed by reporting.vw_experiment_assignment_outcomes.
# ---------------------------------------------------------------------------

BINARY_METRIC_FIELDS = {
    "onboarding_completion_48h": "onboarding_completed_48h",
    "overall_feature_use_7d": "feature_used_7d",
    "trial_start_conversion_7d": "trial_started_7d",
    "paid_conversion_14d": "paid_started_14d",
    "cancellation_or_expiry_30d": "cancellation_or_expiry_30d",
}


CONTINUOUS_METRIC_KEYS = frozenset(
    {
        "revenue_per_assigned_user_30d",
    }
)


EXPERIMENT_METRIC_ROLES = (
    ("primary", "primary_metric"),
    ("secondary", "secondary_metric"),
    ("commercial", "commercial_metric"),
    ("guardrail", "guardrail_metric"),
)


def _context_to_dict(context: ReportingContext) -> dict[str, Any]:
    cutoff = context.observation_cutoff_at

    if hasattr(cutoff, "isoformat"):
        cutoff_value = cutoff.isoformat()
    else:
        cutoff_value = str(cutoff)

    return {
        "ingestion_batch_id": context.ingestion_batch_id,
        "analytics_build_run_id": context.analytics_build_run_id,
        "observation_cutoff_at": cutoff_value,
    }


def _fetch_experiment_definitions(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    """Load canonical experiment role configuration from reporting."""

    return fetch_reporting_rows(
        """
        SELECT DISTINCT
            ingestion_batch_id,
            analytics_build_run_id,
            experiment_id,
            experiment_name,
            primary_metric,
            secondary_metric,
            commercial_metric,
            guardrail_metric,
            analysis_window_days
        FROM reporting.vw_experiment_assignment_outcomes
        WHERE analytics_build_run_id = %s
        ORDER BY experiment_id
        """,
        (analytics_build_run_id,),
        config=config,
    )


def build_metric_plan(
    experiments: Sequence[Mapping[str, Any]],
    contracts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Classify every configured experiment metric against its contract."""

    contract_by_key = {
        str(row["metric_key"]): row
        for row in contracts
    }

    plan: list[dict[str, Any]] = []

    for experiment in experiments:
        experiment_id = str(experiment["experiment_id"])

        for role, field_name in EXPERIMENT_METRIC_ROLES:
            metric_key = str(experiment[field_name])
            contract = contract_by_key.get(metric_key)

            if contract is None:
                support_status = "unknown"
                inference_status = "excluded_unknown_metric_contract"
                metric_name = None
                metric_unit = None

            else:
                support_status = str(contract["support_status"])
                metric_name = contract.get("metric_name")
                metric_unit = contract.get("metric_unit")

                if support_status != "supported":
                    inference_status = (
                        f"excluded_{support_status}"
                    )

                elif metric_key in BINARY_METRIC_FIELDS:
                    inference_status = "ready_binary"

                elif metric_key in CONTINUOUS_METRIC_KEYS:
                    inference_status = "pending_continuous_inference"

                else:
                    inference_status = (
                        "excluded_no_phase5_inference_binding"
                    )

            plan.append(
                {
                    "experiment_id": experiment_id,
                    "experiment_name": experiment["experiment_name"],
                    "metric_role": role,
                    "metric_key": metric_key,
                    "metric_name": metric_name,
                    "metric_unit": metric_unit,
                    "support_status": support_status,
                    "inference_status": inference_status,
                }
            )

    return plan


def _fetch_binary_metric_counts(
    *,
    experiment_id: str,
    metric_key: str,
    analytics_build_run_id: int,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    """Load assigned-mature binary counts from canonical reporting outcomes."""

    if metric_key not in BINARY_METRIC_FIELDS:
        raise InferenceContractError(
            f"No canonical binary reporting binding for metric: {metric_key}"
        )

    outcome_field = BINARY_METRIC_FIELDS[metric_key]

    # outcome_field comes only from the hard-coded canonical whitelist above.
    sql = f"""
        SELECT
            MIN(ingestion_batch_id)::bigint
                AS ingestion_batch_id,

            analytics_build_run_id,

            MIN(observation_cutoff_at)
                AS observation_cutoff_at,

            experiment_id,
            variant,

            MIN(allocation_probability)::double precision
                AS allocation_probability,

            COUNT(*)::bigint
                AS assigned_mature_count,

            COUNT(*) FILTER (
                WHERE {outcome_field} IS TRUE
            )::bigint
                AS success_count

        FROM reporting.vw_experiment_assignment_outcomes

        WHERE analytics_build_run_id = %s
          AND experiment_id = %s
          AND analysis_window_mature IS TRUE

        GROUP BY
            analytics_build_run_id,
            experiment_id,
            variant

        ORDER BY variant
    """

    return fetch_reporting_rows(
        sql,
        (
            analytics_build_run_id,
            experiment_id,
        ),
        config=config,
    )


def analyse_binary_metric_rows(
    *,
    metric_key: str,
    rows: Sequence[Mapping[str, Any]],
) -> tuple[BinaryInferenceResult, SampleRatioResult]:
    """Validate and infer one supported binary experiment metric."""

    validate_variant_summary_rows(rows)
    validate_common_lineage(rows)

    sample_ratio = build_sample_ratio_result(
        rows,
        count_field="assigned_mature_count",
    )

    if sample_ratio.mismatch_detected:
        raise InferenceContractError(
            "Outcome inference blocked because sample-ratio mismatch "
            f"was detected for {sample_ratio.experiment_id}"
        )

    by_variant = {
        str(row["variant"]).lower(): row
        for row in rows
    }

    control = by_variant["control"]
    treatment = by_variant["treatment"]

    result = infer_binary_outcome(
        metric_name=metric_key,
        control_successes=int(control["success_count"]),
        control_total=int(control["assigned_mature_count"]),
        treatment_successes=int(treatment["success_count"]),
        treatment_total=int(treatment["assigned_mature_count"]),
    )

    return result, sample_ratio


def build_live_binary_inference(
    *,
    config: DatabaseConfig | None = None,
) -> dict[str, Any]:
    """Build the current production binary-inference snapshot."""

    context = get_reporting_context(config=config)

    experiments = _fetch_experiment_definitions(
        context.analytics_build_run_id,
        config=config,
    )

    if not experiments:
        raise InferenceContractError(
            "No experiment definitions were returned from reporting."
        )

    experiment_lineage_rows = [
        {
            "ingestion_batch_id": row["ingestion_batch_id"],
            "analytics_build_run_id": row["analytics_build_run_id"],
            "observation_cutoff_at": context.observation_cutoff_at,
        }
        for row in experiments
    ]

    validate_common_lineage(experiment_lineage_rows)

    contracts = get_metric_contracts(config=config)

    plan = build_metric_plan(
        experiments,
        contracts,
    )

    supported_metric_keys = [
        row["metric_key"]
        for row in plan
        if row["support_status"] == "supported"
    ]

    if supported_metric_keys:
        require_supported_metrics(
            supported_metric_keys,
            config=config,
        )

    contract_by_key = {
        str(row["metric_key"]): row
        for row in contracts
    }

    binary_results: list[dict[str, Any]] = []

    for plan_row in plan:
        if plan_row["inference_status"] != "ready_binary":
            continue

        metric_key = str(plan_row["metric_key"])
        experiment_id = str(plan_row["experiment_id"])

        rows = _fetch_binary_metric_counts(
            experiment_id=experiment_id,
            metric_key=metric_key,
            analytics_build_run_id=context.analytics_build_run_id,
            config=config,
        )

        result, sample_ratio = analyse_binary_metric_rows(
            metric_key=metric_key,
            rows=rows,
        )

        result_values = asdict(result)

        # The engine calls this metric_name; in the integrated output the
        # canonical identifier is represented explicitly as metric_key.
        result_values.pop("metric_name", None)

        contract = contract_by_key[metric_key]

        binary_results.append(
            {
                "experiment_id": experiment_id,
                "experiment_name": plan_row["experiment_name"],
                "metric_role": plan_row["metric_role"],
                "metric_key": metric_key,
                "metric_name": contract["metric_name"],
                "metric_unit": contract["metric_unit"],
                "population": "assigned_mature",
                "srm_status": "pass",
                "srm_p_value": sample_ratio.p_value,
                **result_values,
                "multiplicity_status": (
                    "pending_complete_experiment_family"
                ),
            }
        )

    return {
        "synthetic_data": True,
        "phase": 5,
        "step": 4,
        "analysis_type": "randomized_experiment_binary_inference",
        "context": _context_to_dict(context),
        "metric_plan": plan,
        "binary_results": binary_results,
        "methodology": {
            "primary_population": "assigned_mature",
            "effect_direction": "treatment_minus_control",
            "confidence_level": 0.95,
            "binary_test": "two_proportion_z_test",
            "difference_interval": "newcombe_wilson",
            "srm_alpha": 0.001,
            "multiplicity": (
                "deferred_until_complete_supported_metric_family"
            ),
        },
    }


def _format_percentage(value: float) -> str:
    return f"{value * 100:.2f}%"


def _format_pp(value: float) -> str:
    return f"{value:.2f} pp"


def render_live_binary_markdown(
    snapshot: Mapping[str, Any],
) -> str:
    """Render a restrained human-readable Step 4 inference report."""

    context = snapshot["context"]

    lines = [
        "# Pulse Phase 5 — Live Binary Experiment Inference",
        "",
        "> Pulse is a synthetic product analytics project. "
        "All experiment data and results are synthetic.",
        "",
        "## Production context",
        "",
        f"- Ingestion batch: `{context['ingestion_batch_id']}`",
        (
            "- Analytics build: "
            f"`{context['analytics_build_run_id']}`"
        ),
        (
            "- Observation cutoff: "
            f"`{context['observation_cutoff_at']}`"
        ),
        "- Primary population: `assigned_mature`",
        "",
        "## Metric eligibility",
        "",
        "| Experiment | Role | Metric | Contract | Phase 5 status |",
        "|---|---|---|---|---|",
    ]

    for row in snapshot["metric_plan"]:
        lines.append(
            "| "
            f"{row['experiment_name']} | "
            f"{row['metric_role']} | "
            f"`{row['metric_key']}` | "
            f"{row['support_status']} | "
            f"{row['inference_status']} |"
        )

    lines.extend(
        [
            "",
            "## Supported binary inference",
            "",
            (
                "| Experiment | Role | Metric | Control | Treatment | "
                "Effect | 95% CI | p-value | Detectable at 0.05 |"
            ),
            (
                "|---|---|---|---:|---:|---:|---:|---:|---|"
            ),
        ]
    )

    for row in snapshot["binary_results"]:
        control = _format_percentage(row["control_rate"])
        treatment = _format_percentage(row["treatment_rate"])

        effect = _format_pp(
            row["percentage_point_effect"]
        )

        ci_low = row["confidence_interval_low"] * 100
        ci_high = row["confidence_interval_high"] * 100

        ci = (
            f"[{ci_low:.2f}, {ci_high:.2f}] pp"
        )

        p_value = f"{row['p_value']:.6g}"

        detectable = (
            "Yes"
            if row["statistically_detectable"]
            else "No"
        )

        lines.append(
            "| "
            f"{row['experiment_name']} | "
            f"{row['metric_role']} | "
            f"`{row['metric_key']}` | "
            f"{control} | "
            f"{treatment} | "
            f"{effect} | "
            f"{ci} | "
            f"{p_value} | "
            f"{detectable} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation controls",
            "",
            (
                "- Effect direction is always treatment minus control."
            ),
            (
                "- Deferred metrics are not reconstructed or substituted."
            ),
            (
                "- Metrics absent from `reporting.metric_definitions` are "
                "not inferred."
            ),
            (
                "- The supported continuous revenue metric is not forced "
                "through a binary test."
            ),
            (
                "- Raw p-values are shown at this stage. Holm adjustment is "
                "deferred until the complete supported inferential family "
                "has been analysed."
            ),
            (
                "- Statistical detectability alone is not a business "
                "decision."
            ),
            (
                "- Phase 5 does not assume that the synthetic generator "
                "contains treatment effects."
            ),
            "",
        ]
    )

    return "\n".join(lines)


def export_live_binary_inference(
    snapshot: Mapping[str, Any],
    *,
    output_dir: Path = Path("outputs/phase5/step4"),
) -> dict[str, Path]:
    """Export machine-readable and portfolio-readable Step 4 evidence."""

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = output_dir / "live_binary_inference.json"
    markdown_path = output_dir / "live_binary_inference.md"
    manifest_path = output_dir / "step4_manifest.json"

    json_path.write_text(
        json.dumps(
            snapshot,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    markdown_path.write_text(
        render_live_binary_markdown(snapshot),
        encoding="utf-8",
    )

    manifest = {
        "phase": 5,
        "step": 4,
        "synthetic_data": True,
        "context": snapshot["context"],
        "files": [
            json_path.name,
            markdown_path.name,
        ],
        "binary_result_count": len(
            snapshot["binary_results"]
        ),
        "metric_plan_count": len(
            snapshot["metric_plan"]
        ),
        "multiplicity_status": (
            "pending_complete_experiment_family"
        ),
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
        "json": json_path,
        "markdown": markdown_path,
        "manifest": manifest_path,
    }


def main() -> None:
    snapshot = build_live_binary_inference()

    paths = export_live_binary_inference(snapshot)

    print("")
    print("=" * 72)
    print("PHASE 5 — STEP 4 LIVE BINARY INFERENCE")
    print("=" * 72)

    print("")
    print("Metric contract plan:")

    for row in snapshot["metric_plan"]:
        print(
            row["experiment_id"],
            row["metric_role"],
            row["metric_key"],
            "->",
            row["inference_status"],
        )

    print("")
    print("Binary inference results:")

    for row in snapshot["binary_results"]:
        print("")
        print(
            row["experiment_name"],
            "|",
            row["metric_role"],
            "|",
            row["metric_key"],
        )

        print(
            "  control:",
            f"{row['control_rate'] * 100:.4f}%",
        )

        print(
            "  treatment:",
            f"{row['treatment_rate'] * 100:.4f}%",
        )

        print(
            "  effect:",
            f"{row['percentage_point_effect']:.4f} pp",
        )

        print(
            "  95% CI:",
            (
                f"[{row['confidence_interval_low'] * 100:.4f}, "
                f"{row['confidence_interval_high'] * 100:.4f}] pp"
            ),
        )

        print(
            "  p-value:",
            f"{row['p_value']:.10g}",
        )

        print(
            "  statistically detectable:",
            row["statistically_detectable"],
        )

        print(
            "  SRM:",
            row["srm_status"],
        )

    print("")
    print("Outputs:")

    for name, path in paths.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
