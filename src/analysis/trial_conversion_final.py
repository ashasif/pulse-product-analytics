"""Locked final holdout evaluation for Phase 6.

This module contains evaluation mechanics only.
Model selection and tuning are prohibited after final-test scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from src.analysis.trial_conversion_baselines import (
    BaselineMetrics,
    PREDICTOR_COLUMNS,
    STATIC_BASELINE_FEATURES,
    build_static_logistic_pipeline,
    evaluate_probabilities,
    feature_matrix,
    target_vector,
)
from src.analysis.trial_conversion_models import (
    MODEL_BEHAVIOURAL_LOGISTIC,
    MODEL_STATIC_LOGISTIC,
    build_behavioural_logistic_pipeline,
)
from src.analysis.trial_conversion_robustness import (
    ReliabilityBin,
    RobustnessResult,
    TargetingResult,
)


MODEL_PREVALENCE = "prevalence"

BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20260819


@dataclass
class LockedModels:
    """Models fitted once on the complete development population."""

    prevalence: float
    static_logistic: Any
    behavioural_logistic: Any


@dataclass(frozen=True)
class HoldoutResult:
    """Metrics for one model on one frozen evaluation population."""

    model_name: str
    metrics: BaselineMetrics
    probability_mean: float
    observed_rate: float
    probability_min: float
    probability_max: float


@dataclass(frozen=True)
class PairedBootstrapDelta:
    """Behavioural-minus-static paired bootstrap result."""

    brier_delta: float
    brier_ci_low: float
    brier_ci_high: float
    log_loss_delta: float
    log_loss_ci_low: float
    log_loss_ci_high: float
    replicates: int
    seed: int


def fit_locked_models(
    development_rows: Sequence[Mapping[str, Any]],
) -> LockedModels:
    """Fit prevalence, static logistic and behavioural logistic once."""

    if not development_rows:
        raise ValueError(
            "Development population is empty."
        )

    targets = np.asarray(
        target_vector(
            development_rows
        ),
        dtype=int,
    )

    if set(targets.tolist()) != {0, 1}:
        raise ValueError(
            "Development population must contain both classes."
        )

    prevalence = float(
        targets.mean()
    )

    static_model = build_static_logistic_pipeline()

    static_model.fit(
        feature_matrix(
            development_rows,
            STATIC_BASELINE_FEATURES,
        ),
        targets,
    )

    behavioural_model = build_behavioural_logistic_pipeline()

    behavioural_model.fit(
        feature_matrix(
            development_rows,
            PREDICTOR_COLUMNS,
        ),
        targets,
    )

    return LockedModels(
        prevalence=prevalence,
        static_logistic=static_model,
        behavioural_logistic=behavioural_model,
    )


def score_locked_models(
    models: LockedModels,
    evaluation_rows: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[str, HoldoutResult],
    dict[str, np.ndarray],
]:
    """Score frozen models without fitting anything."""

    if not evaluation_rows:
        raise ValueError(
            "Evaluation population is empty."
        )

    targets = np.asarray(
        target_vector(
            evaluation_rows
        ),
        dtype=int,
    )

    if set(targets.tolist()) != {0, 1}:
        raise ValueError(
            "Evaluation population must contain both classes."
        )

    probabilities = {
        MODEL_PREVALENCE:
            np.full(
                len(evaluation_rows),
                models.prevalence,
                dtype=float,
            ),

        MODEL_STATIC_LOGISTIC:
            np.asarray(
                models.static_logistic.predict_proba(
                    feature_matrix(
                        evaluation_rows,
                        STATIC_BASELINE_FEATURES,
                    )
                )[:, 1],
                dtype=float,
            ),

        MODEL_BEHAVIOURAL_LOGISTIC:
            np.asarray(
                models.behavioural_logistic.predict_proba(
                    feature_matrix(
                        evaluation_rows,
                        PREDICTOR_COLUMNS,
                    )
                )[:, 1],
                dtype=float,
            ),
    }

    observed_rate = float(
        targets.mean()
    )

    results: dict[str, HoldoutResult] = {}

    for model_name, model_probabilities in probabilities.items():

        metrics = evaluate_probabilities(
            targets.tolist(),
            model_probabilities.tolist(),
        )

        results[model_name] = HoldoutResult(
            model_name=model_name,
            metrics=metrics,
            probability_mean=float(
                model_probabilities.mean()
            ),
            observed_rate=observed_rate,
            probability_min=float(
                model_probabilities.min()
            ),
            probability_max=float(
                model_probabilities.max()
            ),
        )

    return results, probabilities


def behavioural_generalisation_confirmed(
    results: Mapping[str, HoldoutResult],
) -> bool:
    """Apply the frozen probability-quality rule."""

    static = results[
        MODEL_STATIC_LOGISTIC
    ]

    behavioural = results[
        MODEL_BEHAVIOURAL_LOGISTIC
    ]

    return (
        behavioural.metrics.brier_score
        < static.metrics.brier_score
        and behavioural.metrics.log_loss
        < static.metrics.log_loss
    )


def _brier(
    targets: np.ndarray,
    probabilities: np.ndarray,
) -> float:
    return float(
        np.mean(
            (
                probabilities
                - targets
            ) ** 2
        )
    )


def _log_loss(
    targets: np.ndarray,
    probabilities: np.ndarray,
) -> float:

    probabilities = np.clip(
        probabilities,
        1e-15,
        1.0 - 1e-15,
    )

    return float(
        -np.mean(
            targets * np.log(
                probabilities
            )
            + (
                1.0 - targets
            )
            * np.log(
                1.0 - probabilities
            )
        )
    )


def paired_bootstrap_deltas(
    targets: Sequence[int],
    behavioural_probabilities: Sequence[float],
    static_probabilities: Sequence[float],
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> PairedBootstrapDelta:
    """Calculate deterministic paired bootstrap intervals."""

    targets_array = np.asarray(
        targets,
        dtype=float,
    )

    behavioural = np.asarray(
        behavioural_probabilities,
        dtype=float,
    )

    static = np.asarray(
        static_probabilities,
        dtype=float,
    )

    if not (
        len(targets_array)
        == len(behavioural)
        == len(static)
    ):
        raise ValueError(
            "Paired bootstrap inputs must have equal length."
        )

    if len(targets_array) < 2:
        raise ValueError(
            "Paired bootstrap population is too small."
        )

    if replicates < 100:
        raise ValueError(
            "At least 100 bootstrap replicates are required."
        )

    point_brier_delta = (
        _brier(
            targets_array,
            behavioural,
        )
        - _brier(
            targets_array,
            static,
        )
    )

    point_log_loss_delta = (
        _log_loss(
            targets_array,
            behavioural,
        )
        - _log_loss(
            targets_array,
            static,
        )
    )

    rng = np.random.default_rng(
        seed
    )

    brier_deltas = np.empty(
        replicates,
        dtype=float,
    )

    log_loss_deltas = np.empty(
        replicates,
        dtype=float,
    )

    row_count = len(
        targets_array
    )

    for replicate in range(
        replicates
    ):

        indices = rng.integers(
            0,
            row_count,
            size=row_count,
        )

        sampled_targets = targets_array[
            indices
        ]

        sampled_behavioural = behavioural[
            indices
        ]

        sampled_static = static[
            indices
        ]

        brier_deltas[
            replicate
        ] = (
            _brier(
                sampled_targets,
                sampled_behavioural,
            )
            - _brier(
                sampled_targets,
                sampled_static,
            )
        )

        log_loss_deltas[
            replicate
        ] = (
            _log_loss(
                sampled_targets,
                sampled_behavioural,
            )
            - _log_loss(
                sampled_targets,
                sampled_static,
            )
        )

    brier_ci = np.quantile(
        brier_deltas,
        [0.025, 0.975],
    )

    log_loss_ci = np.quantile(
        log_loss_deltas,
        [0.025, 0.975],
    )

    return PairedBootstrapDelta(
        brier_delta=float(
            point_brier_delta
        ),
        brier_ci_low=float(
            brier_ci[0]
        ),
        brier_ci_high=float(
            brier_ci[1]
        ),
        log_loss_delta=float(
            point_log_loss_delta
        ),
        log_loss_ci_low=float(
            log_loss_ci[0]
        ),
        log_loss_ci_high=float(
            log_loss_ci[1]
        ),
        replicates=replicates,
        seed=seed,
    )


def render_results_markdown(
    *,
    development_count: int,
    final_test_count: int,
    boundary_count: int,
    final_results: Mapping[str, HoldoutResult],
    boundary_results: Mapping[str, HoldoutResult],
    bootstrap: PairedBootstrapDelta,
    reliability: Sequence[ReliabilityBin],
    targeting: Sequence[TargetingResult],
    robustness: Mapping[str, Sequence[RobustnessResult]],
) -> str:
    """Render permanent Step 6 evidence."""

    confirmed = behavioural_generalisation_confirmed(
        final_results
    )

    lines = [
        "# Phase 6 — Final Holdout Evaluation",
        "",
        "## Locked evaluation",
        "",
        f"- development rows: {development_count:,}",
        f"- final test rows: {final_test_count:,}",
        f"- June 2026 boundary rows: {boundary_count:,}",
        "- selected model: `behavioural_logistic`",
        "- calibration: `uncalibrated`",
        "",
        "## Final test model comparison",
        "",
        "| Model | Brier | Log loss | ROC-AUC | Average precision | Mean prediction | Observed conversion |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]

    for model_name in (
        MODEL_PREVALENCE,
        MODEL_STATIC_LOGISTIC,
        MODEL_BEHAVIOURAL_LOGISTIC,
    ):

        result = final_results[
            model_name
        ]

        lines.append(
            "| "
            f"{model_name} | "
            f"{result.metrics.brier_score:.6f} | "
            f"{result.metrics.log_loss:.6f} | "
            f"{result.metrics.roc_auc:.6f} | "
            f"{result.metrics.average_precision:.6f} | "
            f"{result.probability_mean:.6f} | "
            f"{result.observed_rate:.6f} |"
        )

    lines.extend(
        [
            "",
            "## Final generalisation decision",
            "",
            (
                "**Behavioural probability-quality "
                f"improvement confirmed: {confirmed}.**"
            ),
            "",
            "Behavioural minus static:",
            "",
            f"- Brier delta: {bootstrap.brier_delta:+.6f}",
            f"- log-loss delta: {bootstrap.log_loss_delta:+.6f}",
            "",
            "Paired 95% bootstrap intervals:",
            "",
            (
                "- Brier delta: "
                f"[{bootstrap.brier_ci_low:+.6f}, "
                f"{bootstrap.brier_ci_high:+.6f}]"
            ),
            (
                "- log-loss delta: "
                f"[{bootstrap.log_loss_ci_low:+.6f}, "
                f"{bootstrap.log_loss_ci_high:+.6f}]"
            ),
            (
                f"- bootstrap replicates: "
                f"{bootstrap.replicates:,}"
            ),
            f"- bootstrap seed: {bootstrap.seed}",
            "",
            "Negative deltas favour the behavioural model.",
            "",
            "## Reliability deciles",
            "",
            "| Bin | n | Mean predicted conversion | Observed conversion | Gap |",
            "|---:|---:|---:|---:|---:|",
        ]
    )

    for item in reliability:
        lines.append(
            "| "
            f"{item.bin_number} | "
            f"{item.row_count} | "
            f"{item.mean_predicted_conversion:.4f} | "
            f"{item.observed_conversion_rate:.4f} | "
            f"{item.calibration_gap:+.4f} |"
        )

    lines.extend(
        [
            "",
            "## Non-conversion targeting utility",
            "",
            "| Capacity | Targeted | Non-conversions captured | Capture rate | Target-group non-conversion rate | Population non-conversion rate | Lift |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for item in targeting:
        lines.append(
            "| "
            f"{item.capacity:.0%} | "
            f"{item.targeted_count} | "
            f"{item.targeted_non_conversions} | "
            f"{item.non_conversion_capture_rate:.4f} | "
            f"{item.targeted_non_conversion_rate:.4f} | "
            f"{item.overall_non_conversion_rate:.4f} | "
            f"{item.lift_vs_population:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Final-test robustness",
            "",
        ]
    )

    for dimension in (
        "month",
        "platform",
        "billing_period",
        "acquisition_channel",
    ):

        lines.extend(
            [
                f"### {dimension}",
                "",
                "| Group | n | Conversion | Mean prediction | Brier | Log loss | ROC-AUC | Average precision |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )

        for item in robustness[
            dimension
        ]:

            roc_auc = (
                "NA"
                if item.roc_auc is None
                else f"{item.roc_auc:.6f}"
            )

            average_precision = (
                "NA"
                if item.average_precision is None
                else f"{item.average_precision:.6f}"
            )

            lines.append(
                "| "
                f"{item.group} | "
                f"{item.row_count} | "
                f"{item.conversion_rate:.4f} | "
                f"{item.mean_predicted_conversion:.4f} | "
                f"{item.brier_score:.6f} | "
                f"{item.log_loss:.6f} | "
                f"{roc_auc} | "
                f"{average_precision} |"
            )

        lines.append("")

    lines.extend(
        [
            "## June 2026 boundary sensitivity",
            "",
            "| Model | Brier | Log loss | ROC-AUC | Average precision | Mean prediction | Observed conversion |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for model_name in (
        MODEL_PREVALENCE,
        MODEL_STATIC_LOGISTIC,
        MODEL_BEHAVIOURAL_LOGISTIC,
    ):

        result = boundary_results[
            model_name
        ]

        lines.append(
            "| "
            f"{model_name} | "
            f"{result.metrics.brier_score:.6f} | "
            f"{result.metrics.log_loss:.6f} | "
            f"{result.metrics.roc_auc:.6f} | "
            f"{result.metrics.average_precision:.6f} | "
            f"{result.probability_mean:.6f} | "
            f"{result.observed_rate:.6f} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation constraints",
            "",
            "- Pulse uses synthetic customer behaviour.",
            "- Predictive ranking is not causal evidence.",
            "- Targeting utility does not estimate intervention effectiveness.",
            "- Final-test results cannot be used for further model tuning.",
            "- June 2026 is sensitivity evidence, not a second test set for selection.",
            "",
        ]
    )

    return "\n".join(
        lines
    )


def write_results_once(
    path: Path,
    content: str,
) -> None:
    """Persist final results and refuse overwrite."""

    if path.exists():
        raise FileExistsError(
            "Final holdout results already exist."
        )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary_path.write_text(
        content.rstrip() + "\n",
        encoding="utf-8",
        newline="\n",
    )

    temporary_path.replace(
        path
    )
