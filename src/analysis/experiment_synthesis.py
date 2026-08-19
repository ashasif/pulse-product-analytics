"""Descriptive experiment analysis and business synthesis for Pulse Phase 4.

Experiment outputs are descriptive only. The module deliberately avoids
statistical significance, confidence intervals, p-values, causal lift and
treatment-effect claims.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.analysis.reporting_client import (
    ReportingContext,
    fetch_reporting_rows,
    get_reporting_context,
    require_supported_metrics,
)
from src.ingestion.database import DatabaseConfig


STEP4_SUPPORTED_METRICS = (
    "experiment_exposure_rate",
    "onboarding_completion_48h",
    "overall_feature_use_7d",
    "trial_start_conversion_7d",
    "paid_conversion_14d",
    "revenue_per_assigned_user_30d",
    "cancellation_or_expiry_30d",
)


class PriorAnalysisContractError(ValueError):
    """Raised when prior Phase 4 outputs do not match current lineage."""


def _experiment_variant_summary(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            ingestion_batch_id,
            analytics_build_run_id,
            experiment_key,
            experiment_id,
            experiment_name,
            primary_metric,
            secondary_metric,
            commercial_metric,
            guardrail_metric,
            analysis_window_days,
            variant,
            assigned_user_count,
            exposed_user_count,
            exposure_rate,
            onboarding_completed_48h_count,
            onboarding_completion_48h_rate,
            feature_used_7d_count,
            overall_feature_use_7d_rate,
            trial_started_7d_count,
            trial_start_conversion_7d,
            paid_started_14d_count,
            paid_conversion_14d,
            successful_revenue_gbp_30d,
            revenue_per_assigned_user_30d,
            cancellation_or_expiry_30d_count,
            cancellation_or_expiry_30d_rate
        FROM reporting.vw_experiment_variant_summary
        WHERE analytics_build_run_id = %s
        ORDER BY experiment_id, variant
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _experiment_maturity_summary(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            experiment_key,
            experiment_id,
            experiment_name,
            variant,
            COUNT(*)::bigint AS assigned_user_count,
            COUNT(*) FILTER (
                WHERE is_exposed
            )::bigint AS exposed_user_count,
            COUNT(*) FILTER (
                WHERE analysis_window_mature
            )::bigint AS mature_analysis_window_count,
            CASE
                WHEN COUNT(*) = 0 THEN NULL
                ELSE COUNT(*) FILTER (
                    WHERE analysis_window_mature
                )::numeric / COUNT(*)
            END AS mature_analysis_window_rate
        FROM reporting.vw_experiment_assignment_outcomes
        WHERE analytics_build_run_id = %s
        GROUP BY
            analytics_build_run_id,
            experiment_key,
            experiment_id,
            experiment_name,
            variant
        ORDER BY experiment_id, variant
        """,
        (analytics_build_run_id,),
        config=config,
    )


def build_experiment_snapshot(
    *,
    config: DatabaseConfig | None = None,
) -> dict[str, Any]:
    """Load the canonical descriptive experiment snapshot."""

    require_supported_metrics(
        STEP4_SUPPORTED_METRICS,
        config=config,
    )

    context = get_reporting_context(config=config)
    build_id = context.analytics_build_run_id

    variants = _experiment_variant_summary(
        build_id,
        config=config,
    )

    maturity = _experiment_maturity_summary(
        build_id,
        config=config,
    )

    return {
        "context": context,
        "experiment_variant_summary": variants,
        "experiment_maturity_summary": maturity,
        "experiment_descriptive_comparisons":
            build_descriptive_comparisons(variants),
    }


def _reference_variant(
    rows: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Choose an explicit control/baseline when available."""

    for preferred in ("control", "baseline"):
        for row in rows:
            if str(row["variant"]).strip().lower() == preferred:
                return row

    return sorted(
        rows,
        key=lambda row: str(row["variant"]).lower(),
    )[0]


def _rate_difference_pp(
    reference: Any,
    comparison: Any,
) -> float | None:
    if reference is None or comparison is None:
        return None

    return (
        float(comparison) - float(reference)
    ) * 100.0


def _numeric_difference(
    reference: Any,
    comparison: Any,
) -> float | None:
    if reference is None or comparison is None:
        return None

    return float(comparison) - float(reference)


def build_descriptive_comparisons(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build observed variant differences without causal interpretation."""

    by_experiment: dict[str, list[Mapping[str, Any]]] = {}

    for row in rows:
        by_experiment.setdefault(
            str(row["experiment_id"]),
            [],
        ).append(row)

    comparisons: list[dict[str, Any]] = []

    for experiment_id in sorted(by_experiment):
        experiment_rows = by_experiment[experiment_id]

        if len(experiment_rows) < 2:
            continue

        reference = _reference_variant(experiment_rows)

        for comparison in experiment_rows:
            if comparison is reference:
                continue

            comparisons.append(
                {
                    "ingestion_batch_id":
                        reference["ingestion_batch_id"],
                    "analytics_build_run_id":
                        reference["analytics_build_run_id"],
                    "experiment_id":
                        reference["experiment_id"],
                    "experiment_name":
                        reference["experiment_name"],
                    "reference_variant":
                        reference["variant"],
                    "comparison_variant":
                        comparison["variant"],
                    "reference_assigned_user_count":
                        reference["assigned_user_count"],
                    "comparison_assigned_user_count":
                        comparison["assigned_user_count"],
                    "exposure_rate_difference_pp":
                        _rate_difference_pp(
                            reference["exposure_rate"],
                            comparison["exposure_rate"],
                        ),
                    "onboarding_completion_48h_difference_pp":
                        _rate_difference_pp(
                            reference[
                                "onboarding_completion_48h_rate"
                            ],
                            comparison[
                                "onboarding_completion_48h_rate"
                            ],
                        ),
                    "overall_feature_use_7d_difference_pp":
                        _rate_difference_pp(
                            reference[
                                "overall_feature_use_7d_rate"
                            ],
                            comparison[
                                "overall_feature_use_7d_rate"
                            ],
                        ),
                    "trial_start_conversion_7d_difference_pp":
                        _rate_difference_pp(
                            reference[
                                "trial_start_conversion_7d"
                            ],
                            comparison[
                                "trial_start_conversion_7d"
                            ],
                        ),
                    "paid_conversion_14d_difference_pp":
                        _rate_difference_pp(
                            reference["paid_conversion_14d"],
                            comparison["paid_conversion_14d"],
                        ),
                    "revenue_per_assigned_user_30d_difference_gbp":
                        _numeric_difference(
                            reference[
                                "revenue_per_assigned_user_30d"
                            ],
                            comparison[
                                "revenue_per_assigned_user_30d"
                            ],
                        ),
                    "cancellation_or_expiry_30d_difference_pp":
                        _rate_difference_pp(
                            reference[
                                "cancellation_or_expiry_30d_rate"
                            ],
                            comparison[
                                "cancellation_or_expiry_30d_rate"
                            ],
                        ),
                    "interpretation":
                        "descriptive_only",
                }
            )

    return comparisons


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def load_prior_business_context(
    outputs_root: str | Path,
    context: ReportingContext,
) -> dict[str, Any]:
    """Load validated Step 2/3 outputs and enforce shared lineage."""

    root = Path(outputs_root)

    step2_root = root / "step2"
    step3_root = root / "step3"

    step2_manifest = json.loads(
        (step2_root / "analysis_manifest.json").read_text(
            encoding="utf-8"
        )
    )

    step3_manifest = json.loads(
        (step3_root / "analysis_manifest.json").read_text(
            encoding="utf-8"
        )
    )

    for step_name, manifest in (
        ("step2", step2_manifest),
        ("step3", step3_manifest),
    ):
        if (
            int(manifest["ingestion_batch_id"])
            != context.ingestion_batch_id
        ):
            raise PriorAnalysisContractError(
                f"{step_name} ingestion lineage does not match."
            )

        if (
            int(manifest["analytics_build_run_id"])
            != context.analytics_build_run_id
        ):
            raise PriorAnalysisContractError(
                f"{step_name} analytics build does not match."
            )

        if (
            manifest["observation_cutoff_at"]
            != context.observation_cutoff_at.isoformat()
        ):
            raise PriorAnalysisContractError(
                f"{step_name} observation cutoff does not match."
            )

        if manifest["source_schema"] != "reporting":
            raise PriorAnalysisContractError(
                f"{step_name} does not use reporting as source."
            )

    return {
        "step2_manifest": step2_manifest,
        "step3_manifest": step3_manifest,
        "funnel_summary":
            _read_csv(
                step2_root / "funnel_summary.csv"
            )[0],
        "acquisition_channels":
            _read_csv(
                step2_root
                / "acquisition_channel_performance.csv"
            ),
        "revenue_summary":
            _read_csv(
                step3_root / "revenue_summary.csv"
            )[0],
        "trial_conversion_summary":
            _read_csv(
                step3_root
                / "trial_conversion_summary.csv"
            )[0],
        "retention_summary":
            _read_csv(
                step3_root / "retention_summary.csv"
            )[0],
        "feature_engagement":
            _read_csv(
                step3_root / "feature_engagement.csv"
            ),
        "channel_retention":
            _read_csv(
                step3_root
                / "retention_by_acquisition_channel.csv"
            ),
    }


def _count(value: Any) -> str:
    return f"{int(value):,}"


def _rate(value: Any) -> str:
    if value in (None, ""):
        return "n/a"

    return f"{float(value) * 100:.2f}%"


def _pp(value: Any) -> str:
    if value is None:
        return "n/a"

    return f"{float(value):+.2f} pp"


def _gbp(value: Any) -> str:
    return f"£{float(value):,.2f}"


def _gbp_delta(value: Any) -> str:
    if value is None:
        return "n/a"

    return f"{float(value):+.2f} GBP"


def render_experiment_findings(
    snapshot: Mapping[str, Any],
) -> str:
    """Render descriptive experiment findings."""

    context: ReportingContext = snapshot["context"]
    variants = snapshot["experiment_variant_summary"]
    comparisons = snapshot[
        "experiment_descriptive_comparisons"
    ]
    maturity = snapshot["experiment_maturity_summary"]

    experiment_ids = sorted(
        {
            str(row["experiment_id"])
            for row in variants
        }
    )

    assigned_total = sum(
        int(row["assigned_user_count"])
        for row in maturity
    )

    exposed_total = sum(
        int(row["exposed_user_count"])
        for row in maturity
    )

    mature_total = sum(
        int(row["mature_analysis_window_count"])
        for row in maturity
    )

    lines = [
        "# Pulse Phase 4 — Descriptive Experiment Findings",
        "",
        "> Pulse and all analysed data are synthetic and exist solely "
        "for portfolio and learning purposes.",
        "",
        "## Analysis context",
        "",
        f"- Ingestion batch: `{context.ingestion_batch_id}`",
        f"- Analytics build: `{context.analytics_build_run_id}`",
        (
            "- Observation cutoff: "
            f"`{context.observation_cutoff_at.isoformat()}`"
        ),
        f"- Experiments represented: **{len(experiment_ids)}**",
        f"- Assignments: **{_count(assigned_total)}**",
        f"- Exposed assignments: **{_count(exposed_total)}**",
        f"- Mature analysis windows: **{_count(mature_total)}**",
        "",
        "Only supported canonical outcome metrics are analysed. "
        "Configured experiment labels that remain deferred are not "
        "silently converted into new definitions.",
        "",
    ]

    for experiment_id in experiment_ids:
        exp_rows = [
            row
            for row in variants
            if str(row["experiment_id"]) == experiment_id
        ]

        first = exp_rows[0]

        lines.extend(
            [
                f"## {first['experiment_name']}",
                "",
                f"- Experiment ID: `{experiment_id}`",
                f"- Configured primary metric: `{first['primary_metric']}`",
                f"- Configured secondary metric: `{first['secondary_metric']}`",
                f"- Configured commercial metric: `{first['commercial_metric']}`",
                f"- Configured guardrail metric: `{first['guardrail_metric']}`",
                (
                    "- Analysis window: "
                    f"**{first['analysis_window_days']} days**"
                ),
                "",
                "| Variant | Assigned | Exposure | Onboarding 48h | "
                "Feature use 7d | Trial 7d | Paid 14d | "
                "Revenue/user 30d | Cancel/expiry 30d |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )

        for row in exp_rows:
            lines.append(
                "| "
                f"{row['variant']} | "
                f"{_count(row['assigned_user_count'])} | "
                f"{_rate(row['exposure_rate'])} | "
                f"{_rate(row['onboarding_completion_48h_rate'])} | "
                f"{_rate(row['overall_feature_use_7d_rate'])} | "
                f"{_rate(row['trial_start_conversion_7d'])} | "
                f"{_rate(row['paid_conversion_14d'])} | "
                f"{_gbp(row['revenue_per_assigned_user_30d'])} | "
                f"{_rate(row['cancellation_or_expiry_30d_rate'])} |"
            )

        exp_comparisons = [
            row
            for row in comparisons
            if str(row["experiment_id"]) == experiment_id
        ]

        if exp_comparisons:
            lines.extend(
                [
                    "",
                    "### Observed variant differences",
                    "",
                ]
            )

            for row in exp_comparisons:
                lines.extend(
                    [
                        (
                            f"**{row['comparison_variant']} vs "
                            f"{row['reference_variant']}**"
                        ),
                        "",
                        (
                            "- Onboarding completion within 48h: "
                            f"{_pp(row['onboarding_completion_48h_difference_pp'])}"
                        ),
                        (
                            "- Any feature use within 7d: "
                            f"{_pp(row['overall_feature_use_7d_difference_pp'])}"
                        ),
                        (
                            "- Trial start within 7d: "
                            f"{_pp(row['trial_start_conversion_7d_difference_pp'])}"
                        ),
                        (
                            "- Paid conversion within 14d: "
                            f"{_pp(row['paid_conversion_14d_difference_pp'])}"
                        ),
                        (
                            "- Successful payment collection per assigned "
                            "user within 30d: "
                            f"{_gbp_delta(row['revenue_per_assigned_user_30d_difference_gbp'])}"
                        ),
                        (
                            "- Cancellation or expiry within 30d: "
                            f"{_pp(row['cancellation_or_expiry_30d_difference_pp'])}"
                        ),
                        "",
                    ]
                )

    lines.extend(
        [
            "## Interpretation boundary",
            "",
            "Every difference above is an **observed descriptive difference** "
            "in the synthetic dataset.",
            "",
            "The analysis does **not** provide:",
            "",
            "- p-values",
            "- confidence intervals",
            "- statistical-significance decisions",
            "- causal lift",
            "- treatment effects",
            "- causal-inference claims",
            "",
            "The experiment results should therefore be used as "
            "hypothesis-generating evidence rather than proof that a "
            "variant caused an outcome.",
            "",
        ]
    )

    return "\n".join(lines)


def render_business_synthesis(
    snapshot: Mapping[str, Any],
    prior: Mapping[str, Any],
) -> str:
    """Combine Steps 2–4 into a decision-oriented business synthesis."""

    context: ReportingContext = snapshot["context"]

    funnel = prior["funnel_summary"]
    channels = prior["acquisition_channels"]
    revenue = prior["revenue_summary"]
    trial = prior["trial_conversion_summary"]
    retention = prior["retention_summary"]
    features = prior["feature_engagement"]
    channel_retention = prior["channel_retention"]
    comparisons = snapshot[
        "experiment_descriptive_comparisons"
    ]

    best_signup_channel = max(
        channels,
        key=lambda row: float(
            row["install_to_signup_rate"]
        ),
    )

    positive_cpi_channels = [
        row
        for row in channels
        if row["cost_per_install_gbp"]
        and float(row["cost_per_install_gbp"]) > 0
    ]

    lowest_positive_cpi = min(
        positive_cpi_channels,
        key=lambda row: float(
            row["cost_per_install_gbp"]
        ),
    )

    d365_rows = [
        row
        for row in channel_retention
        if row["paid_retention_d365"] not in ("", None)
    ]

    best_d365_channel = max(
        d365_rows,
        key=lambda row: float(
            row["paid_retention_d365"]
        ),
    )

    top_feature = max(
        features,
        key=lambda row: int(
            row["feature_use_event_count"]
        ),
    )

    lines = [
        "# Pulse Phase 4 — Business Synthesis",
        "",
        "> Pulse and all analysed data are synthetic and exist solely "
        "for portfolio and learning purposes.",
        "",
        "## Executive view",
        "",
        (
            "Pulse's synthetic dataset shows strong top-of-funnel growth "
            "and reasonable early paid retention, but much weaker "
            "long-horizon paid persistence."
        ),
        "",
        (
            f"The current reporting snapshot contains "
            f"**{_count(funnel['installation_count'])} installations**, "
            f"with an install-to-signup rate of "
            f"**{_rate(funnel['install_to_signup_rate'])}**."
        ),
        (
            f"Mature trial-to-paid conversion is "
            f"**{_rate(trial['trial_to_paid_conversion_rate'])}**, "
            f"while D30 paid retention is "
            f"**{_rate(retention['paid_retention_d30'])}**."
        ),
        (
            f"By D365, retention falls to "
            f"**{_rate(retention['paid_retention_d365'])}** "
            f"among {_count(retention['eligible_d365_count'])} "
            "eligible subscriptions."
        ),
        "",
        "## Business priorities",
        "",
        "### 1. Long-term paid retention",
        "",
        (
            f"D30 retention is "
            f"**{_rate(retention['paid_retention_d30'])}**, "
            f"D90 is **{_rate(retention['paid_retention_d90'])}**, "
            f"D180 is **{_rate(retention['paid_retention_d180'])}**, "
            f"and D365 is **{_rate(retention['paid_retention_d365'])}**."
        ),
        "",
        "The largest business issue visible in the current snapshot is "
        "therefore not initial paid activation alone, but maintaining "
        "subscriptions over longer horizons. The next product questions "
        "should focus on lifecycle drop-off, feature value and renewal "
        "behaviour rather than simply increasing acquisition volume.",
        "",
        "### 2. Acquisition quality, not just acquisition volume",
        "",
        (
            f"`{best_signup_channel['acquisition_channel']}` has the "
            "highest observed install-to-signup rate at "
            f"**{_rate(best_signup_channel['install_to_signup_rate'])}**."
        ),
        (
            f"`{lowest_positive_cpi['acquisition_channel']}` also has the "
            "lowest positive channel-level CPI at "
            f"**{_gbp(lowest_positive_cpi['cost_per_install_gbp'])}**."
        ),
        (
            f"The strongest observed D365 retention among acquisition "
            f"channels is `{best_d365_channel['acquisition_channel']}` at "
            f"**{_rate(best_d365_channel['paid_retention_d365'])}**."
        ),
        "",
        "These cross-stage patterns are useful for prioritising further "
        "investigation, but they do not prove that acquisition channel "
        "caused better downstream retention.",
        "",
        "### 3. Payment reliability",
        "",
        (
            f"The payment failure rate is "
            f"**{_rate(revenue['payment_failure_rate'])}**, while renewal "
            f"attempt success is "
            f"**{_rate(revenue['renewal_success_rate'])}**."
        ),
        (
            "Successful billed payment collection totals "
            f"**{_gbp(revenue['successful_payment_revenue_gbp'])}**."
        ),
        "",
        "Payment failure remains measurable friction, but the current "
        "snapshot does not support recognised revenue, net revenue, "
        "profit or customer lifetime value conclusions.",
        "",
        "### 4. Feature engagement concentration",
        "",
        (
            f"`{top_feature['feature_name']}` is the highest-volume "
            f"feature with **{_count(top_feature['feature_use_event_count'])} "
            "feature-use events**, representing "
            f"**{_rate(top_feature['feature_use_event_share'])}** "
            "of all feature-use events."
        ),
        "",
        "This establishes usage concentration, not which feature causes "
        "retention or commercial value.",
        "",
        "### 5. Experiments as hypothesis-generating evidence",
        "",
        (
            f"The reporting layer currently provides "
            f"**{len(comparisons)} descriptive variant comparison(s)** "
            "across the configured experiments."
        ),
        "",
        "Observed variant differences can identify areas worth deeper "
        "investigation, but Phase 4 deliberately does not convert those "
        "differences into causal lift or statistical-significance claims.",
        "",
        "## Recommended next investigations",
        "",
        "1. Examine which product behaviours precede the largest "
        "retention losses between D30, D90 and D180.",
        "2. Compare referral-acquired users with other channels across "
        "engagement, paid conversion and longer-horizon retention.",
        "3. Investigate payment-failure timing and whether failed attempts "
        "cluster around specific renewal stages.",
        "4. Examine whether high AI Assistant usage is associated with "
        "stronger retention while keeping the analysis explicitly "
        "observational.",
        "5. Treat experiment differences as hypotheses requiring a later "
        "approved statistical methodology before making causal claims.",
        "",
        "## Governance and interpretation boundaries",
        "",
        "- Source of truth: `reporting.*`",
        "- Only supported metric contracts are used.",
        "- Cohort maturity rules are preserved.",
        "- Successful payment collection is not accounting revenue.",
        "- Channel CPI is not campaign-attributed CAC.",
        "- No LTV, MAU, recognised revenue or net revenue is invented.",
        "- Experiment outputs remain descriptive only.",
        "- All data are synthetic.",
        "",
        "## Analysis lineage",
        "",
        f"- Ingestion batch: `{context.ingestion_batch_id}`",
        f"- Analytics build: `{context.analytics_build_run_id}`",
        (
            "- Observation cutoff: "
            f"`{context.observation_cutoff_at.isoformat()}`"
        ),
        "",
    ]

    return "\n".join(lines)


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    if not rows:
        raise ValueError(
            f"Cannot write empty analytical dataset: {path.name}"
        )

    fieldnames = list(rows[0].keys())

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def export_experiment_synthesis(
    snapshot: Mapping[str, Any],
    prior: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    """Persist Phase 4 Step 4 analytical evidence."""

    directory = Path(output_dir)
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    datasets = {
        "experiment_variant_summary":
            snapshot["experiment_variant_summary"],
        "experiment_maturity_summary":
            snapshot["experiment_maturity_summary"],
        "experiment_descriptive_comparisons":
            snapshot["experiment_descriptive_comparisons"],
    }

    paths: dict[str, Path] = {}

    for name, rows in datasets.items():
        path = directory / f"{name}.csv"
        _write_csv(path, rows)
        paths[name] = path

    experiment_findings_path = (
        directory / "experiment_findings.md"
    )

    experiment_findings_path.write_text(
        render_experiment_findings(snapshot),
        encoding="utf-8",
    )

    paths["experiment_findings"] = (
        experiment_findings_path
    )

    synthesis_path = directory / "business_synthesis.md"

    synthesis_path.write_text(
        render_business_synthesis(
            snapshot,
            prior,
        ),
        encoding="utf-8",
    )

    paths["business_synthesis"] = synthesis_path

    context: ReportingContext = snapshot["context"]

    manifest = {
        "phase": 4,
        "step": 4,
        "analysis":
            "descriptive_experiments_and_business_synthesis",
        "synthetic_data": True,
        "experiment_interpretation":
            "descriptive_only",
        "ingestion_batch_id":
            context.ingestion_batch_id,
        "analytics_build_run_id":
            context.analytics_build_run_id,
        "observation_cutoff_at":
            context.observation_cutoff_at.isoformat(),
        "metric_contracts":
            list(STEP4_SUPPORTED_METRICS),
        "source_schema": "reporting",
        "prior_phase4_steps": [
            2,
            3,
        ],
        "datasets": {
            name: {
                "file": paths[name].name,
                "row_count": len(rows),
            }
            for name, rows in datasets.items()
        },
    }

    manifest_path = directory / "analysis_manifest.json"

    with manifest_path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            manifest,
            handle,
            indent=2,
        )
        handle.write("\n")

    paths["manifest"] = manifest_path

    return paths
