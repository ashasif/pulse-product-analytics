"""Live continuous-outcome inference for Pulse Phase 5.

Current supported application:

Paywall Redesign Experiment
    revenue_per_assigned_user_30d

The business metric means successful billed payment collection per assigned
user. It is not accounting-recognised revenue, net revenue, profit or LTV.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.analysis.experiment_continuous_inference import (
    DEFAULT_BOOTSTRAP_REPLICATES,
    DEFAULT_PERMUTATION_REPLICATES,
    DEFAULT_RESAMPLING_SEED,
    MeanDifferenceInferenceResult,
    infer_mean_difference_resampling,
)
from src.analysis.experiment_inference import (
    InferenceContractError,
    validate_common_lineage,
)
from src.analysis.experiment_integrity import (
    SampleRatioResult,
    build_sample_ratio_result,
)
from src.analysis.reporting_client import (
    ReportingContext,
    fetch_reporting_rows,
    get_reporting_context,
    require_supported_metrics,
)
from src.ingestion.database import DatabaseConfig


EXPERIMENT_ID = "exp_paywall_redesign_2024q3"
METRIC_KEY = "revenue_per_assigned_user_30d"
OUTCOME_FIELD = "successful_revenue_gbp_30d"


def _context_to_dict(
    context: ReportingContext,
) -> dict[str, Any]:
    cutoff = context.observation_cutoff_at

    if hasattr(cutoff, "isoformat"):
        cutoff_value = cutoff.isoformat()
    else:
        cutoff_value = str(cutoff)

    return {
        "ingestion_batch_id":
            context.ingestion_batch_id,
        "analytics_build_run_id":
            context.analytics_build_run_id,
        "observation_cutoff_at":
            cutoff_value,
    }


def _fetch_assigned_mature_revenue(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    """Load assignment-level canonical collection primitive."""

    return fetch_reporting_rows(
        """
        SELECT
            ingestion_batch_id,
            analytics_build_run_id,
            observation_cutoff_at,
            experiment_id,
            variant,
            allocation_probability,
            successful_revenue_gbp_30d AS outcome_value
        FROM reporting.vw_experiment_assignment_outcomes
        WHERE analytics_build_run_id = %s
          AND experiment_id = %s
          AND analysis_window_mature IS TRUE
        ORDER BY
            variant,
            experiment_assignment_key
        """,
        (
            analytics_build_run_id,
            EXPERIMENT_ID,
        ),
        config=config,
    )


def _fetch_canonical_variant_summary(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    """Load canonical descriptive commercial summary for reconciliation."""

    return fetch_reporting_rows(
        """
        SELECT
            ingestion_batch_id,
            analytics_build_run_id,
            experiment_id,
            variant,
            assigned_user_count,
            successful_revenue_gbp_30d,
            revenue_per_assigned_user_30d
        FROM reporting.vw_experiment_variant_summary
        WHERE analytics_build_run_id = %s
          AND experiment_id = %s
        ORDER BY variant
        """,
        (
            analytics_build_run_id,
            EXPERIMENT_ID,
        ),
        config=config,
    )


def _group_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    grouped = {
        "control": [],
        "treatment": [],
    }

    for row in rows:
        variant = str(row["variant"]).lower()

        if variant not in grouped:
            raise InferenceContractError(
                f"Unexpected experiment variant: {variant}"
            )

        grouped[variant].append(row)

    if not grouped["control"]:
        raise InferenceContractError(
            "No control observations were returned"
        )

    if not grouped["treatment"]:
        raise InferenceContractError(
            "No treatment observations were returned"
        )

    return grouped


def _build_srm_rows(
    grouped: Mapping[
        str,
        Sequence[Mapping[str, Any]],
    ],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for variant in (
        "control",
        "treatment",
    ):
        rows = grouped[variant]

        allocations = {
            float(row["allocation_probability"])
            for row in rows
        }

        if len(allocations) != 1:
            raise InferenceContractError(
                "Allocation probability must be constant "
                f"within variant: {variant}"
            )

        output.append(
            {
                "experiment_id": EXPERIMENT_ID,
                "variant": variant,
                "allocation_probability":
                    next(iter(allocations)),
                "assigned_mature_count":
                    len(rows),
            }
        )

    return output


def analyse_revenue_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_replicates: int =
        DEFAULT_BOOTSTRAP_REPLICATES,
    permutation_replicates: int =
        DEFAULT_PERMUTATION_REPLICATES,
    seed: int =
        DEFAULT_RESAMPLING_SEED,
) -> tuple[
    MeanDifferenceInferenceResult,
    SampleRatioResult,
    dict[str, Any],
]:
    """Validate and infer the commercial mean difference."""

    if not rows:
        raise InferenceContractError(
            "No revenue outcome rows were supplied"
        )

    validate_common_lineage(rows)

    grouped = _group_rows(rows)

    srm = build_sample_ratio_result(
        _build_srm_rows(grouped),
        count_field="assigned_mature_count",
    )

    if srm.mismatch_detected:
        raise InferenceContractError(
            "Continuous inference blocked because "
            "sample-ratio mismatch was detected"
        )

    control_values = [
        row["outcome_value"]
        for row in grouped["control"]
    ]

    treatment_values = [
        row["outcome_value"]
        for row in grouped["treatment"]
    ]

    result = infer_mean_difference_resampling(
        metric_name=METRIC_KEY,
        control_values=control_values,
        treatment_values=treatment_values,
        bootstrap_replicates=bootstrap_replicates,
        permutation_replicates=permutation_replicates,
        seed=seed,
    )

    def diagnostics(
        values: Sequence[object],
    ) -> dict[str, Any]:
        numeric = [
            float(value)
            for value in values
        ]

        zero_count = sum(
            value == 0.0
            for value in numeric
        )

        positive_count = sum(
            value > 0.0
            for value in numeric
        )

        return {
            "count": len(numeric),
            "zero_count": zero_count,
            "zero_rate":
                zero_count / len(numeric),
            "positive_count": positive_count,
            "positive_rate":
                positive_count / len(numeric),
            "unique_values":
                sorted(set(numeric)),
            "minimum": min(numeric),
            "maximum": max(numeric),
        }

    distribution = {
        "control": diagnostics(control_values),
        "treatment": diagnostics(treatment_values),
    }

    return result, srm, distribution


def _reconcile_to_canonical_summary(
    result: MeanDifferenceInferenceResult,
    summary_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Reconcile current mature means to reporting variant summary."""

    if len(summary_rows) != 2:
        raise InferenceContractError(
            "Expected exactly two canonical variant summary rows"
        )

    by_variant = {
        str(row["variant"]).lower(): row
        for row in summary_rows
    }

    if set(by_variant) != {
        "control",
        "treatment",
    }:
        raise InferenceContractError(
            "Canonical summary must contain control and treatment"
        )

    control = by_variant["control"]
    treatment = by_variant["treatment"]

    population_matches = (
        int(control["assigned_user_count"])
            == result.control_count
        and
        int(treatment["assigned_user_count"])
            == result.treatment_count
    )

    if not population_matches:
        return {
            "population_matches_variant_summary":
                False,
            "mean_reconciliation_applicable":
                False,
            "mean_reconciliation_passed":
                None,
        }

    control_summary_mean = float(
        control[
            "revenue_per_assigned_user_30d"
        ]
    )

    treatment_summary_mean = float(
        treatment[
            "revenue_per_assigned_user_30d"
        ]
    )

    tolerance = 1e-12

    mean_matches = (
        abs(
            result.control_mean
            - control_summary_mean
        ) <= tolerance
        and
        abs(
            result.treatment_mean
            - treatment_summary_mean
        ) <= tolerance
    )

    if not mean_matches:
        raise InferenceContractError(
            "Assigned-mature commercial means do not reconcile "
            "to the canonical reporting summary"
        )

    return {
        "population_matches_variant_summary":
            True,
        "mean_reconciliation_applicable":
            True,
        "mean_reconciliation_passed":
            True,
        "canonical_control_mean":
            control_summary_mean,
        "canonical_treatment_mean":
            treatment_summary_mean,
    }


def build_live_continuous_inference(
    *,
    config: DatabaseConfig | None = None,
    bootstrap_replicates: int =
        DEFAULT_BOOTSTRAP_REPLICATES,
    permutation_replicates: int =
        DEFAULT_PERMUTATION_REPLICATES,
    seed: int =
        DEFAULT_RESAMPLING_SEED,
) -> dict[str, Any]:
    """Build the current production continuous-inference snapshot."""

    require_supported_metrics(
        [METRIC_KEY],
        config=config,
    )

    context = get_reporting_context(
        config=config,
    )

    rows = _fetch_assigned_mature_revenue(
        context.analytics_build_run_id,
        config=config,
    )

    result, srm, distribution = (
        analyse_revenue_rows(
            rows,
            bootstrap_replicates=
                bootstrap_replicates,
            permutation_replicates=
                permutation_replicates,
            seed=seed,
        )
    )

    summary_rows = (
        _fetch_canonical_variant_summary(
            context.analytics_build_run_id,
            config=config,
        )
    )

    reconciliation = (
        _reconcile_to_canonical_summary(
            result,
            summary_rows,
        )
    )

    values = asdict(result)
    values.pop("metric_name", None)

    return {
        "synthetic_data": True,
        "phase": 5,
        "step": 5,
        "analysis_type":
            "randomized_experiment_continuous_inference",
        "context":
            _context_to_dict(context),
        "experiment_id":
            EXPERIMENT_ID,
        "experiment_name":
            "Paywall Redesign Experiment",
        "metric_role":
            "commercial",
        "metric_key":
            METRIC_KEY,
        "metric_name":
            (
                "Successful Revenue per Assigned User "
                "Within 30 Days"
            ),
        "metric_unit":
            "GBP",
        "business_interpretation":
            (
                "successful billed payment collection "
                "per assigned user"
            ),
        "population":
            "assigned_mature",
        "outcome_primitive":
            OUTCOME_FIELD,
        "distribution":
            distribution,
        "srm": {
            "status":
                "pass",
            "p_value":
                srm.p_value,
        },
        "inference":
            values,
        "reconciliation":
            reconciliation,
        "methodology": {
            "estimand":
                "treatment_minus_control_mean",
            "confidence_interval":
                "nonparametric_percentile_bootstrap",
            "hypothesis_test":
                "two_sided_randomization_permutation_test",
            "bootstrap_replicates":
                bootstrap_replicates,
            "permutation_replicates":
                permutation_replicates,
            "seed":
                seed,
            "alpha":
                0.05,
            "multiplicity":
                "pending_phase5_combined_synthesis",
        },
    }


def render_markdown(
    snapshot: Mapping[str, Any],
) -> str:
    context = snapshot["context"]
    result = snapshot["inference"]
    distribution = snapshot["distribution"]

    relative = result["relative_effect"]

    if relative is None:
        relative_text = "not defined"
    else:
        relative_text = (
            f"{relative * 100:.2f}%"
        )

    lines = [
        "# Pulse Phase 5 - Continuous Commercial Outcome Inference",
        "",
        (
            "> Pulse is synthetic. The monetary outcome represents "
            "successful billed payment collection, not accounting-"
            "recognised revenue, net revenue, profit or LTV."
        ),
        "",
        "## Production context",
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
        "## Distribution diagnostics",
        "",
        (
            f"- Control users: "
            f"{distribution['control']['count']:,}"
        ),
        (
            f"- Treatment users: "
            f"{distribution['treatment']['count']:,}"
        ),
        (
            "- Control zero-collection rate: "
            f"{distribution['control']['zero_rate'] * 100:.2f}%"
        ),
        (
            "- Treatment zero-collection rate: "
            f"{distribution['treatment']['zero_rate'] * 100:.2f}%"
        ),
        (
            "- Observed control support: "
            f"`{distribution['control']['unique_values']}`"
        ),
        (
            "- Observed treatment support: "
            f"`{distribution['treatment']['unique_values']}`"
        ),
        "",
        "## Mean collection inference",
        "",
        (
            "- Control mean: "
            f"£{result['control_mean']:.4f}"
        ),
        (
            "- Treatment mean: "
            f"£{result['treatment_mean']:.4f}"
        ),
        (
            "- Treatment minus control: "
            f"£{result['absolute_effect']:.4f}"
        ),
        (
            "- Relative mean difference: "
            f"{relative_text}"
        ),
        (
            "- Bootstrap 95% CI: "
            f"[£{result['confidence_interval_low']:.4f}, "
            f"£{result['confidence_interval_high']:.4f}]"
        ),
        (
            "- Randomization permutation p-value: "
            f"{result['permutation_p_value']:.6g}"
        ),
        (
            "- Statistically detectable at alpha 0.05: "
            + (
                "Yes"
                if result["statistically_detectable"]
                else "No"
            )
        ),
        "",
        "## Method",
        "",
        (
            f"- Bootstrap replicates: "
            f"{result['bootstrap_replicates']:,}"
        ),
        (
            f"- Permutation replicates: "
            f"{result['permutation_replicates']:,}"
        ),
        (
            f"- Bootstrap seed: "
            f"`{result['bootstrap_seed']}`"
        ),
        (
            f"- Permutation seed: "
            f"`{result['permutation_seed']}`"
        ),
        (
            "- Confidence interval: non-parametric percentile "
            "bootstrap of treatment-minus-control mean."
        ),
        (
            "- Hypothesis test: randomized-label permutation test "
            "with fixed observed group sizes."
        ),
        "",
        "## Interpretation",
        "",
        (
            "- The commercial estimand is the arithmetic mean across "
            "all assigned-mature users, including users with £0 collection."
        ),
        (
            "- Positive-only users are not used as the primary population."
        ),
        (
            "- The zero-heavy discrete distribution is why the Phase 5 "
            "primary method uses resampling rather than assuming normally "
            "distributed user-level collection."
        ),
        (
            "- Statistical detectability alone is not a rollout decision."
        ),
        "",
    ]

    return "\n".join(lines)


def export_live_continuous_inference(
    snapshot: Mapping[str, Any],
    *,
    output_dir: Path =
        Path("outputs/phase5/step5"),
) -> dict[str, Path]:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = (
        output_dir
        / "live_continuous_inference.json"
    )

    markdown_path = (
        output_dir
        / "live_continuous_inference.md"
    )

    manifest_path = (
        output_dir
        / "step5_manifest.json"
    )

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
        render_markdown(snapshot),
        encoding="utf-8",
    )

    manifest = {
        "phase": 5,
        "step": 5,
        "synthetic_data": True,
        "context": snapshot["context"],
        "experiment_id":
            snapshot["experiment_id"],
        "metric_key":
            snapshot["metric_key"],
        "method":
            (
                "bootstrap_ci_plus_"
                "randomization_permutation_test"
            ),
        "files": [
            json_path.name,
            markdown_path.name,
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
        "json": json_path,
        "markdown": markdown_path,
        "manifest": manifest_path,
    }


def main() -> None:
    snapshot = (
        build_live_continuous_inference()
    )

    paths = (
        export_live_continuous_inference(
            snapshot
        )
    )

    result = snapshot["inference"]

    print("")
    print("=" * 72)
    print(
        "PHASE 5 - STEP 5 CONTINUOUS "
        "COMMERCIAL INFERENCE"
    )
    print("=" * 72)

    print("")
    print(
        "Metric:",
        snapshot["metric_key"],
    )

    print(
        "Control mean:",
        f"£{result['control_mean']:.6f}",
    )

    print(
        "Treatment mean:",
        f"£{result['treatment_mean']:.6f}",
    )

    print(
        "Effect:",
        f"£{result['absolute_effect']:.6f}",
    )

    print(
        "95% bootstrap CI:",
        (
            f"[£{result['confidence_interval_low']:.6f}, "
            f"£{result['confidence_interval_high']:.6f}]"
        ),
    )

    print(
        "Permutation p-value:",
        f"{result['permutation_p_value']:.10g}",
    )

    print(
        "Statistically detectable:",
        result["statistically_detectable"],
    )

    print(
        "Canonical reconciliation:",
        snapshot["reconciliation"],
    )

    print("")
    print("Outputs:")

    for name, path in paths.items():
        print(
            f"  {name}: {path}"
        )


if __name__ == "__main__":
    main()
