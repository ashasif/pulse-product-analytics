"""Phase 5 multiplicity and design-sensitivity synthesis."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from statistics import stdev
from typing import Any, Mapping, Sequence

from src.analysis.experiment_inference import (
    InferenceContractError,
    holm_adjust_p_values,
)
from src.analysis.experiment_live_continuous import (
    _fetch_assigned_mature_revenue,
)
from src.analysis.experiment_sensitivity import (
    binary_mde,
    mean_mde,
)
from src.analysis.reporting_client import (
    get_reporting_context,
)
from src.ingestion.database import DatabaseConfig


DEFAULT_STEP4_PATH = Path(
    "outputs/phase5/step4/live_binary_inference.json"
)

DEFAULT_STEP5_PATH = Path(
    "outputs/phase5/step5/live_continuous_inference.json"
)

DEFAULT_OUTPUT_DIR = Path(
    "outputs/phase5/step6"
)


def _load_json(
    path: Path,
) -> dict[str, Any]:
    if not path.exists():
        raise InferenceContractError(
            f"Required Phase 5 output does not exist: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def _normalise_context(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    cutoff = context[
        "observation_cutoff_at"
    ]

    if hasattr(cutoff, "isoformat"):
        cutoff = cutoff.isoformat()
    else:
        cutoff = str(cutoff)

    return {
        "ingestion_batch_id":
            int(context["ingestion_batch_id"]),
        "analytics_build_run_id":
            int(context["analytics_build_run_id"]),
        "observation_cutoff_at":
            cutoff,
    }


def validate_matching_contexts(
    *contexts: Mapping[str, Any],
) -> dict[str, Any]:
    if not contexts:
        raise InferenceContractError(
            "At least one context is required"
        )

    normalised = [
        _normalise_context(context)
        for context in contexts
    ]

    reference = normalised[0]

    for context in normalised[1:]:
        if context != reference:
            raise InferenceContractError(
                "Phase 5 outputs use incompatible production contexts"
            )

    return reference


def build_multiplicity_results(
    binary_snapshot: Mapping[str, Any],
    continuous_snapshot: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Apply Holm adjustment to completed supportive outcomes.

    Primary metrics remain separate from supportive outcome families.
    """

    supportive: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for row in binary_snapshot[
        "binary_results"
    ]:
        if row["metric_role"] == "primary":
            continue

        supportive.setdefault(
            row["experiment_id"],
            [],
        ).append(
            {
                "metric_key":
                    row["metric_key"],
                "metric_role":
                    row["metric_role"],
                "raw_p_value":
                    float(row["p_value"]),
                "test":
                    "two_proportion_z_test",
            }
        )

    if (
        continuous_snapshot[
            "metric_role"
        ]
        != "primary"
    ):
        supportive.setdefault(
            continuous_snapshot[
                "experiment_id"
            ],
            [],
        ).append(
            {
                "metric_key":
                    continuous_snapshot[
                        "metric_key"
                    ],
                "metric_role":
                    continuous_snapshot[
                        "metric_role"
                    ],
                "raw_p_value":
                    float(
                        continuous_snapshot[
                            "inference"
                        ][
                            "permutation_p_value"
                        ]
                    ),
                "test":
                    (
                        "randomization_"
                        "permutation_test"
                    ),
            }
        )

    results: list[
        dict[str, Any]
    ] = []

    for experiment_id, rows in (
        supportive.items()
    ):
        family = {
            row["metric_key"]:
                row["raw_p_value"]
            for row in rows
        }

        adjusted = {
            row.metric_name: row
            for row in holm_adjust_p_values(
                family
            )
        }

        for row in rows:
            item = adjusted[
                row["metric_key"]
            ]

            results.append(
                {
                    "experiment_id":
                        experiment_id,
                    "metric_key":
                        row["metric_key"],
                    "metric_role":
                        row["metric_role"],
                    "test":
                        row["test"],
                    "family_size":
                        len(rows),
                    "raw_p_value":
                        row["raw_p_value"],
                    "holm_adjusted_p_value":
                        item.adjusted_p_value,
                    "detectable_after_holm":
                        (
                            item
                            .statistically_detectable_after_adjustment
                        ),
                }
            )

    return results


def build_binary_sensitivity(
    binary_snapshot: Mapping[str, Any],
) -> list[dict[str, Any]]:
    rows: list[
        dict[str, Any]
    ] = []

    for result in binary_snapshot[
        "binary_results"
    ]:
        mde = binary_mde(
            metric_key=
                result["metric_key"],
            control_rate=
                float(
                    result[
                        "control_rate"
                    ]
                ),
            control_count=
                int(
                    result[
                        "control_total"
                    ]
                ),
            treatment_count=
                int(
                    result[
                        "treatment_total"
                    ]
                ),
        )

        observed_pp = abs(
            float(
                result[
                    "percentage_point_effect"
                ]
            )
        )

        if (
            mde.mde_percentage_points
            is None
        ):
            ratio = None
        else:
            ratio = (
                observed_pp
                / mde.mde_percentage_points
            )

        rows.append(
            {
                "experiment_id":
                    result[
                        "experiment_id"
                    ],
                "experiment_name":
                    result[
                        "experiment_name"
                    ],
                "metric_key":
                    result[
                        "metric_key"
                    ],
                "metric_role":
                    result[
                        "metric_role"
                    ],
                "outcome_type":
                    "binary",
                "control_rate":
                    result[
                        "control_rate"
                    ],
                "control_count":
                    result[
                        "control_total"
                    ],
                "treatment_count":
                    result[
                        "treatment_total"
                    ],
                "observed_effect_pp":
                    result[
                        "percentage_point_effect"
                    ],
                "absolute_observed_effect_pp":
                    observed_pp,
                "mde_pp":
                    mde.mde_percentage_points,
                "effect_to_mde_ratio":
                    ratio,
                "alpha":
                    mde.alpha,
                "target_power":
                    mde.target_power,
                "status":
                    mde.status,
            }
        )

    return rows


def _group_revenue_values(
    rows: Sequence[
        Mapping[str, Any]
    ],
) -> dict[str, list[float]]:
    grouped = {
        "control": [],
        "treatment": [],
    }

    for row in rows:
        variant = str(
            row["variant"]
        ).lower()

        if variant not in grouped:
            raise InferenceContractError(
                f"Unexpected variant: {variant}"
            )

        grouped[variant].append(
            float(
                row[
                    "outcome_value"
                ]
            )
        )

    if (
        len(grouped["control"]) < 2
        or
        len(grouped["treatment"]) < 2
    ):
        raise InferenceContractError(
            "Continuous MDE requires at least two observations per arm"
        )

    return grouped


def build_continuous_sensitivity(
    continuous_snapshot: Mapping[str, Any],
    revenue_rows: Sequence[
        Mapping[str, Any]
    ],
) -> dict[str, Any]:
    grouped = _group_revenue_values(
        revenue_rows
    )

    control_sd = stdev(
        grouped["control"]
    )

    treatment_sd = stdev(
        grouped["treatment"]
    )

    mde = mean_mde(
        metric_key=
            continuous_snapshot[
                "metric_key"
            ],
        control_stddev=
            control_sd,
        treatment_stddev=
            treatment_sd,
        control_count=
            len(
                grouped["control"]
            ),
        treatment_count=
            len(
                grouped["treatment"]
            ),
    )

    observed = float(
        continuous_snapshot[
            "inference"
        ][
            "absolute_effect"
        ]
    )

    return {
        "experiment_id":
            continuous_snapshot[
                "experiment_id"
            ],
        "experiment_name":
            continuous_snapshot[
                "experiment_name"
            ],
        "metric_key":
            continuous_snapshot[
                "metric_key"
            ],
        "metric_role":
            continuous_snapshot[
                "metric_role"
            ],
        "outcome_type":
            "continuous",
        "control_stddev":
            control_sd,
        "treatment_stddev":
            treatment_sd,
        "control_count":
            len(
                grouped["control"]
            ),
        "treatment_count":
            len(
                grouped["treatment"]
            ),
        "observed_effect_gbp":
            observed,
        "absolute_observed_effect_gbp":
            abs(observed),
        "mde_gbp":
            mde.mde_absolute,
        "effect_to_mde_ratio":
            abs(observed)
            / mde.mde_absolute,
        "alpha":
            mde.alpha,
        "target_power":
            mde.target_power,
        "status":
            mde.status,
    }


def build_step6_snapshot(
    *,
    binary_path: Path =
        DEFAULT_STEP4_PATH,
    continuous_path: Path =
        DEFAULT_STEP5_PATH,
    config: DatabaseConfig | None =
        None,
) -> dict[str, Any]:
    binary_snapshot = _load_json(
        binary_path
    )

    continuous_snapshot = _load_json(
        continuous_path
    )

    context = get_reporting_context(
        config=config
    )

    current_context = {
        "ingestion_batch_id":
            context.ingestion_batch_id,
        "analytics_build_run_id":
            context.analytics_build_run_id,
        "observation_cutoff_at":
            context.observation_cutoff_at,
    }

    common_context = (
        validate_matching_contexts(
            binary_snapshot[
                "context"
            ],
            continuous_snapshot[
                "context"
            ],
            current_context,
        )
    )

    revenue_rows = (
        _fetch_assigned_mature_revenue(
            context.analytics_build_run_id,
            config=config,
        )
    )

    multiplicity = (
        build_multiplicity_results(
            binary_snapshot,
            continuous_snapshot,
        )
    )

    binary_sensitivity = (
        build_binary_sensitivity(
            binary_snapshot
        )
    )

    continuous_sensitivity = (
        build_continuous_sensitivity(
            continuous_snapshot,
            revenue_rows,
        )
    )

    return {
        "synthetic_data": True,
        "phase": 5,
        "step": 6,
        "analysis_type":
            (
                "experiment_multiplicity_"
                "and_design_sensitivity"
            ),
        "context":
            common_context,
        "methodology": {
            "multiplicity":
                "holm_within_completed_supportive_family",
            "primary_metric_adjustment":
                "none_prespecified_primary",
            "mde_target_power":
                0.80,
            "mde_alpha":
                0.05,
            "binary_mde":
                (
                    "local_normal_approximation_"
                    "around_control_rate"
                ),
            "continuous_mde":
                (
                    "normal_approximation_using_"
                    "observed_arm_specific_stddev"
                ),
            "observed_power":
                "not_calculated",
        },
        "multiplicity_results":
            multiplicity,
        "binary_sensitivity":
            binary_sensitivity,
        "continuous_sensitivity":
            continuous_sensitivity,
    }


def render_markdown(
    snapshot: Mapping[str, Any],
) -> str:
    context = snapshot[
        "context"
    ]

    lines = [
        "# Pulse Phase 5 - Multiplicity and Design Sensitivity",
        "",
        (
            "> Pulse and all experiment data are synthetic."
        ),
        "",
        "## Production context",
        "",
        (
            "- Ingestion batch: "
            f"`{context['ingestion_batch_id']}`"
        ),
        (
            "- Analytics build: "
            f"`{context['analytics_build_run_id']}`"
        ),
        (
            "- Observation cutoff: "
            f"`{context['observation_cutoff_at']}`"
        ),
        "",
        "## Multiplicity",
        "",
        (
            "Primary metrics remain prespecified and are not mixed "
            "into supportive Holm families."
        ),
        "",
        (
            "| Experiment | Role | Metric | Raw p | "
            "Holm p | Family size | Detectable after Holm |"
        ),
        (
            "|---|---|---|---:|---:|---:|---|"
        ),
    ]

    for row in snapshot[
        "multiplicity_results"
    ]:
        lines.append(
            "| "
            f"{row['experiment_id']} | "
            f"{row['metric_role']} | "
            f"`{row['metric_key']}` | "
            f"{row['raw_p_value']:.6g} | "
            f"{row['holm_adjusted_p_value']:.6g} | "
            f"{row['family_size']} | "
            + (
                "Yes"
                if row[
                    "detectable_after_holm"
                ]
                else "No"
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Binary design sensitivity",
            "",
            (
                "| Experiment | Role | Metric | "
                "Observed effect | Approx. MDE | "
                "Effect / MDE | Status |"
            ),
            (
                "|---|---|---|---:|---:|---:|---|"
            ),
        ]
    )

    for row in snapshot[
        "binary_sensitivity"
    ]:
        if row["mde_pp"] is None:
            mde_text = "not estimable"
            ratio_text = "n/a"
        else:
            mde_text = (
                f"{row['mde_pp']:.2f} pp"
            )
            ratio_text = (
                f"{row['effect_to_mde_ratio']:.2f}"
            )

        lines.append(
            "| "
            f"{row['experiment_id']} | "
            f"{row['metric_role']} | "
            f"`{row['metric_key']}` | "
            f"{row['observed_effect_pp']:.2f} pp | "
            f"{mde_text} | "
            f"{ratio_text} | "
            f"{row['status']} |"
        )

    continuous = snapshot[
        "continuous_sensitivity"
    ]

    lines.extend(
        [
            "",
            "## Continuous commercial design sensitivity",
            "",
            (
                f"- Experiment: `{continuous['experiment_id']}`"
            ),
            (
                f"- Metric: `{continuous['metric_key']}`"
            ),
            (
                "- Observed treatment-minus-control mean: "
                f"GBP {continuous['observed_effect_gbp']:.4f}"
            ),
            (
                "- Approximate 80%-power MDE: "
                f"GBP {continuous['mde_gbp']:.4f}"
            ),
            (
                "- Absolute observed effect / MDE: "
                f"{continuous['effect_to_mde_ratio']:.2f}"
            ),
            (
                "- Control sample SD: "
                f"GBP {continuous['control_stddev']:.4f}"
            ),
            (
                "- Treatment sample SD: "
                f"GBP {continuous['treatment_stddev']:.4f}"
            ),
            "",
            "## Interpretation",
            "",
            (
                "- MDE is a design-sensitivity diagnostic, not "
                "retrospective observed power."
            ),
            (
                "- An observed effect smaller than the approximate "
                "MDE indicates that the current experiment was not "
                "designed to reliably detect effects that small."
            ),
            (
                "- Failure to reject a null hypothesis does not prove "
                "that treatment and control are exactly equal."
            ),
            (
                "- Statistical detectability and practical relevance "
                "remain separate questions."
            ),
            "",
        ]
    )

    return "\n".join(
        lines
    )


def export_step6(
    snapshot: Mapping[str, Any],
    *,
    output_dir: Path =
        DEFAULT_OUTPUT_DIR,
) -> dict[str, Path]:
    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = (
        output_dir
        / "multiplicity_and_sensitivity.json"
    )

    markdown_path = (
        output_dir
        / "multiplicity_and_sensitivity.md"
    )

    manifest_path = (
        output_dir
        / "step6_manifest.json"
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
        render_markdown(
            snapshot
        ),
        encoding="utf-8",
    )

    manifest_path.write_text(
        json.dumps(
            {
                "phase": 5,
                "step": 6,
                "synthetic_data": True,
                "context":
                    snapshot["context"],
                "files": [
                    json_path.name,
                    markdown_path.name,
                ],
                "observed_power_calculated":
                    False,
                "target_power":
                    0.80,
            },
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "json":
            json_path,
        "markdown":
            markdown_path,
        "manifest":
            manifest_path,
    }


def main() -> None:
    snapshot = (
        build_step6_snapshot()
    )

    paths = export_step6(
        snapshot
    )

    print("")
    print("=" * 72)
    print(
        "PHASE 5 - STEP 6 "
        "MULTIPLICITY + DESIGN SENSITIVITY"
    )
    print("=" * 72)

    print("")
    print("Holm-adjusted supportive metrics:")

    for row in snapshot[
        "multiplicity_results"
    ]:
        print(
            row["experiment_id"],
            row["metric_key"],
            "raw=",
            round(
                row["raw_p_value"],
                6,
            ),
            "holm=",
            round(
                row[
                    "holm_adjusted_p_value"
                ],
                6,
            ),
            "detectable=",
            row[
                "detectable_after_holm"
            ],
        )

    print("")
    print("Binary MDE diagnostics:")

    for row in snapshot[
        "binary_sensitivity"
    ]:
        print(
            row["experiment_id"],
            row["metric_key"],
            "observed_pp=",
            round(
                row[
                    "observed_effect_pp"
                ],
                4,
            ),
            "mde_pp=",
            (
                None
                if row["mde_pp"] is None
                else round(
                    row["mde_pp"],
                    4,
                )
            ),
            "status=",
            row["status"],
        )

    continuous = snapshot[
        "continuous_sensitivity"
    ]

    print("")
    print("Continuous commercial MDE:")
    print(
        "observed GBP effect:",
        round(
            continuous[
                "observed_effect_gbp"
            ],
            6,
        ),
    )
    print(
        "approximate MDE GBP:",
        round(
            continuous[
                "mde_gbp"
            ],
            6,
        ),
    )

    print("")
    print("Outputs:")

    for name, path in paths.items():
        print(name, ":", path)


if __name__ == "__main__":
    main()
