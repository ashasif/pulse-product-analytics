"""Calibration, decision utility and robustness for Phase 6.

The final test and June-2026 boundary populations are not scored here.

Calibration models are fitted only from temporally generated out-of-fold
training predictions. Validation outcomes are used only for comparison.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from sklearn.base import clone
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit

from src.analysis.trial_conversion_baselines import (
    BaselineMetrics,
    PREDICTOR_COLUMNS,
    evaluate_probabilities,
    feature_matrix,
    target_vector,
)
from src.analysis.trial_conversion_models import (
    build_behavioural_logistic_pipeline,
)


CALIBRATION_NONE = "uncalibrated"
CALIBRATION_SIGMOID = "sigmoid"
CALIBRATION_ISOTONIC = "isotonic"

CALIBRATION_METHODS = (
    CALIBRATION_NONE,
    CALIBRATION_SIGMOID,
    CALIBRATION_ISOTONIC,
)

TARGETING_CAPACITIES = (
    0.10,
    0.20,
    0.30,
)


@dataclass(frozen=True)
class CalibrationResult:
    """Validation calibration candidate result."""

    method: str
    metrics: BaselineMetrics
    probability_mean: float
    observed_rate: float
    mean_probability_bias: float


@dataclass(frozen=True)
class ReliabilityBin:
    """Equal-frequency reliability bin."""

    bin_number: int
    row_count: int
    probability_min: float
    probability_max: float
    mean_predicted_conversion: float
    observed_conversion_rate: float
    calibration_gap: float


@dataclass(frozen=True)
class TargetingResult:
    """Capacity-constrained non-conversion targeting result."""

    capacity: float
    targeted_count: int
    total_non_conversions: int
    targeted_non_conversions: int
    non_conversion_capture_rate: float
    targeted_non_conversion_rate: float
    overall_non_conversion_rate: float
    lift_vs_population: float


@dataclass(frozen=True)
class RobustnessResult:
    """Performance summary for one validation subgroup."""

    dimension: str
    group: str
    row_count: int
    conversion_rate: float
    mean_predicted_conversion: float
    brier_score: float
    log_loss: float
    roc_auc: float | None
    average_precision: float | None


def _safe_logit(
    probabilities: Sequence[float],
    epsilon: float = 1e-6,
) -> np.ndarray:
    """Convert probabilities to finite logits."""

    probabilities_array = np.asarray(
        probabilities,
        dtype=float,
    )

    clipped = np.clip(
        probabilities_array,
        epsilon,
        1.0 - epsilon,
    )

    return np.log(
        clipped / (1.0 - clipped)
    )


def temporal_oof_probabilities(
    training_rows: Sequence[Mapping[str, Any]],
    *,
    n_splits: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """Create expanding-window OOF probabilities using training only.

    The earliest training block is used only as model history because
    TimeSeriesSplit cannot produce predictions before any prior data exist.
    """

    if len(training_rows) < 100:
        raise ValueError(
            "Training population is too small for temporal calibration."
        )

    ordered_rows = sorted(
        training_rows,
        key=lambda row: (
            row["trial_started_at"],
            row["subscription_key"],
        ),
    )

    targets = np.asarray(
        target_vector(ordered_rows),
        dtype=int,
    )

    splitter = TimeSeriesSplit(
        n_splits=n_splits,
    )

    oof_probabilities = np.full(
        len(ordered_rows),
        np.nan,
        dtype=float,
    )

    for train_indices, calibration_indices in splitter.split(
        ordered_rows
    ):
        if (
            train_indices[-1]
            >= calibration_indices[0]
        ):
            raise ValueError(
                "Temporal OOF split is not chronological."
            )

        fold_train_rows = [
            ordered_rows[index]
            for index in train_indices
        ]

        fold_calibration_rows = [
            ordered_rows[index]
            for index in calibration_indices
        ]

        fold_targets = targets[
            train_indices
        ]

        if set(fold_targets.tolist()) != {0, 1}:
            raise ValueError(
                "Temporal calibration fold training data "
                "must contain both classes."
            )

        model = clone(
            build_behavioural_logistic_pipeline()
        )

        model.fit(
            feature_matrix(
                fold_train_rows,
                PREDICTOR_COLUMNS,
            ),
            fold_targets,
        )

        probabilities = model.predict_proba(
            feature_matrix(
                fold_calibration_rows,
                PREDICTOR_COLUMNS,
            )
        )[:, 1]

        oof_probabilities[
            calibration_indices
        ] = probabilities

    available = ~np.isnan(
        oof_probabilities
    )

    if available.sum() < 100:
        raise ValueError(
            "Too few temporal OOF probabilities were generated."
        )

    return (
        targets[available],
        oof_probabilities[available],
    )


def fit_sigmoid_calibrator(
    oof_targets: Sequence[int],
    oof_probabilities: Sequence[float],
) -> LogisticRegression:
    """Fit Platt-style calibration on training OOF predictions."""

    targets = np.asarray(
        oof_targets,
        dtype=int,
    )

    if set(targets.tolist()) != {0, 1}:
        raise ValueError(
            "Sigmoid calibration requires both classes."
        )

    logits = _safe_logit(
        oof_probabilities
    ).reshape(-1, 1)

    calibrator = LogisticRegression(
        C=np.inf,
        solver="lbfgs",
        max_iter=2000,
    )

    calibrator.fit(
        logits,
        targets,
    )

    return calibrator


def apply_sigmoid_calibrator(
    calibrator: LogisticRegression,
    probabilities: Sequence[float],
) -> np.ndarray:
    """Apply fitted sigmoid calibration."""

    logits = _safe_logit(
        probabilities
    ).reshape(-1, 1)

    return calibrator.predict_proba(
        logits
    )[:, 1]


def fit_isotonic_calibrator(
    oof_targets: Sequence[int],
    oof_probabilities: Sequence[float],
) -> IsotonicRegression:
    """Fit isotonic calibration on training OOF predictions."""

    targets = np.asarray(
        oof_targets,
        dtype=int,
    )

    if set(targets.tolist()) != {0, 1}:
        raise ValueError(
            "Isotonic calibration requires both classes."
        )

    calibrator = IsotonicRegression(
        y_min=0.0,
        y_max=1.0,
        out_of_bounds="clip",
    )

    calibrator.fit(
        np.asarray(
            oof_probabilities,
            dtype=float,
        ),
        targets,
    )

    return calibrator


def fit_calibration_candidates(
    training_rows: Sequence[Mapping[str, Any]],
    validation_rows: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[str, CalibrationResult],
    dict[str, np.ndarray],
]:
    """Fit champion on training and compare calibration on validation."""

    if not training_rows or not validation_rows:
        raise ValueError(
            "Training and validation populations must be non-empty."
        )

    base_model = (
        build_behavioural_logistic_pipeline()
    )

    base_model.fit(
        feature_matrix(
            training_rows,
            PREDICTOR_COLUMNS,
        ),
        target_vector(
            training_rows
        ),
    )

    validation_probabilities = (
        base_model.predict_proba(
            feature_matrix(
                validation_rows,
                PREDICTOR_COLUMNS,
            )
        )[:, 1]
    )

    validation_targets = np.asarray(
        target_vector(
            validation_rows
        ),
        dtype=int,
    )

    (
        oof_targets,
        oof_probabilities,
    ) = temporal_oof_probabilities(
        training_rows
    )

    sigmoid = fit_sigmoid_calibrator(
        oof_targets,
        oof_probabilities,
    )

    isotonic = fit_isotonic_calibrator(
        oof_targets,
        oof_probabilities,
    )

    candidate_probabilities = {
        CALIBRATION_NONE:
            np.asarray(
                validation_probabilities,
                dtype=float,
            ),

        CALIBRATION_SIGMOID:
            apply_sigmoid_calibrator(
                sigmoid,
                validation_probabilities,
            ),

        CALIBRATION_ISOTONIC:
            np.asarray(
                isotonic.predict(
                    validation_probabilities
                ),
                dtype=float,
            ),
    }

    results: dict[str, CalibrationResult] = {}

    observed_rate = float(
        validation_targets.mean()
    )

    for method in CALIBRATION_METHODS:
        probabilities = candidate_probabilities[
            method
        ]

        metrics = evaluate_probabilities(
            validation_targets.tolist(),
            probabilities.tolist(),
        )

        probability_mean = float(
            probabilities.mean()
        )

        results[method] = CalibrationResult(
            method=method,
            metrics=metrics,
            probability_mean=probability_mean,
            observed_rate=observed_rate,
            mean_probability_bias=(
                probability_mean
                - observed_rate
            ),
        )

    return (
        results,
        candidate_probabilities,
    )


def select_calibration_method(
    results: Mapping[
        str,
        CalibrationResult,
    ],
) -> str:
    """Prefer no calibration unless complexity improves both metrics."""

    if set(results) != set(
        CALIBRATION_METHODS
    ):
        raise ValueError(
            "Calibration comparison does not match "
            "the approved candidate set."
        )

    reference = results[
        CALIBRATION_NONE
    ]

    passing = []

    for method in (
        CALIBRATION_SIGMOID,
        CALIBRATION_ISOTONIC,
    ):
        candidate = results[
            method
        ]

        if (
            candidate.metrics.brier_score
            < reference.metrics.brier_score
            and candidate.metrics.log_loss
            < reference.metrics.log_loss
        ):
            passing.append(
                candidate
            )

    if not passing:
        return CALIBRATION_NONE

    passing.sort(
        key=lambda result: (
            result.metrics.brier_score,
            result.metrics.log_loss,
            result.method,
        )
    )

    return passing[0].method


def reliability_bins(
    targets: Sequence[int],
    probabilities: Sequence[float],
    *,
    bin_count: int = 10,
) -> list[ReliabilityBin]:
    """Build deterministic equal-frequency reliability bins."""

    targets_array = np.asarray(
        targets,
        dtype=int,
    )

    probabilities_array = np.asarray(
        probabilities,
        dtype=float,
    )

    if (
        targets_array.size
        != probabilities_array.size
    ):
        raise ValueError(
            "Reliability targets and probabilities differ in length."
        )

    if targets_array.size < bin_count:
        raise ValueError(
            "Reliability population is smaller than bin count."
        )

    order = np.argsort(
        probabilities_array,
        kind="stable",
    )

    groups = np.array_split(
        order,
        bin_count,
    )

    output = []

    for bin_number, indices in enumerate(
        groups,
        start=1,
    ):
        bin_targets = targets_array[
            indices
        ]

        bin_probabilities = (
            probabilities_array[
                indices
            ]
        )

        predicted = float(
            bin_probabilities.mean()
        )

        observed = float(
            bin_targets.mean()
        )

        output.append(
            ReliabilityBin(
                bin_number=bin_number,
                row_count=len(indices),
                probability_min=float(
                    bin_probabilities.min()
                ),
                probability_max=float(
                    bin_probabilities.max()
                ),
                mean_predicted_conversion=predicted,
                observed_conversion_rate=observed,
                calibration_gap=(
                    predicted - observed
                ),
            )
        )

    if sum(
        item.row_count
        for item in output
    ) != targets_array.size:
        raise ValueError(
            "Reliability bins do not cover the validation population."
        )

    return output


def targeting_utility(
    targets: Sequence[int],
    conversion_probabilities: Sequence[float],
    *,
    capacities: Sequence[float] = TARGETING_CAPACITIES,
) -> list[TargetingResult]:
    """Measure concentration of non-conversion risk by capacity.

    This is a prioritisation analysis only. It does not assume or estimate
    treatment effect from contacting a high-risk user.
    """

    targets_array = np.asarray(
        targets,
        dtype=int,
    )

    probabilities = np.asarray(
        conversion_probabilities,
        dtype=float,
    )

    if targets_array.size != probabilities.size:
        raise ValueError(
            "Targeting targets and probabilities differ in length."
        )

    if set(targets_array.tolist()) != {0, 1}:
        raise ValueError(
            "Targeting population must contain both classes."
        )

    non_conversion = (
        1 - targets_array
    )

    total_non_conversions = int(
        non_conversion.sum()
    )

    overall_non_conversion_rate = float(
        non_conversion.mean()
    )

    risk = 1.0 - probabilities

    order = np.argsort(
        -risk,
        kind="stable",
    )

    results = []

    for capacity in capacities:
        if not 0.0 < capacity <= 1.0:
            raise ValueError(
                "Targeting capacity must be within (0, 1]."
            )

        targeted_count = ceil(
            len(targets_array)
            * capacity
        )

        targeted_indices = order[
            :targeted_count
        ]

        targeted_non_conversions = int(
            non_conversion[
                targeted_indices
            ].sum()
        )

        targeted_non_conversion_rate = (
            targeted_non_conversions
            / targeted_count
        )

        capture_rate = (
            targeted_non_conversions
            / total_non_conversions
        )

        lift = (
            targeted_non_conversion_rate
            / overall_non_conversion_rate
        )

        results.append(
            TargetingResult(
                capacity=float(capacity),
                targeted_count=targeted_count,
                total_non_conversions=total_non_conversions,
                targeted_non_conversions=targeted_non_conversions,
                non_conversion_capture_rate=float(
                    capture_rate
                ),
                targeted_non_conversion_rate=float(
                    targeted_non_conversion_rate
                ),
                overall_non_conversion_rate=float(
                    overall_non_conversion_rate
                ),
                lift_vs_population=float(
                    lift
                ),
            )
        )

    return results


def _optional_discrimination(
    targets: Sequence[int],
    probabilities: Sequence[float],
) -> tuple[
    float | None,
    float | None,
]:
    """Return discrimination metrics only when both classes exist."""

    targets_list = [
        int(value)
        for value in targets
    ]

    if set(targets_list) != {0, 1}:
        return (
            None,
            None,
        )

    metrics = evaluate_probabilities(
        targets_list,
        [
            float(value)
            for value in probabilities
        ],
    )

    return (
        metrics.roc_auc,
        metrics.average_precision,
    )


def robustness_by_group(
    validation_rows: Sequence[Mapping[str, Any]],
    probabilities: Sequence[float],
    *,
    dimension: str,
    group_getter: Callable[
        [Mapping[str, Any]],
        str,
    ],
) -> list[RobustnessResult]:
    """Evaluate validation probability quality across one grouping."""

    probabilities_array = np.asarray(
        probabilities,
        dtype=float,
    )

    if len(validation_rows) != len(
        probabilities_array
    ):
        raise ValueError(
            "Robustness rows and probabilities differ in length."
        )

    grouped_indices: dict[
        str,
        list[int],
    ] = {}

    for index, row in enumerate(
        validation_rows
    ):
        group = str(
            group_getter(row)
        )

        grouped_indices.setdefault(
            group,
            [],
        ).append(index)

    output = []

    for group in sorted(
        grouped_indices
    ):
        indices = grouped_indices[
            group
        ]

        targets = [
            int(
                validation_rows[index][
                    "converted_to_paid"
                ]
            )
            for index in indices
        ]

        group_probabilities = (
            probabilities_array[
                indices
            ]
        )

        # Brier and log loss are always defined here because
        # explicit labels are supplied to log_loss.
        squared_errors = [
            (
                float(probability)
                - int(target)
            ) ** 2
            for target, probability in zip(
                targets,
                group_probabilities,
            )
        ]

        brier = float(
            np.mean(
                squared_errors
            )
        )

        clipped = np.clip(
            group_probabilities,
            1e-15,
            1.0 - 1e-15,
        )

        targets_array = np.asarray(
            targets,
            dtype=float,
        )

        logloss = float(
            -np.mean(
                (
                    targets_array
                    * np.log(clipped)
                )
                + (
                    (1.0 - targets_array)
                    * np.log(
                        1.0 - clipped
                    )
                )
            )
        )

        (
            roc_auc,
            average_precision,
        ) = _optional_discrimination(
            targets,
            group_probabilities,
        )

        output.append(
            RobustnessResult(
                dimension=dimension,
                group=group,
                row_count=len(indices),
                conversion_rate=float(
                    np.mean(
                        targets_array
                    )
                ),
                mean_predicted_conversion=float(
                    group_probabilities.mean()
                ),
                brier_score=brier,
                log_loss=logloss,
                roc_auc=roc_auc,
                average_precision=average_precision,
            )
        )

    if sum(
        item.row_count
        for item in output
    ) != len(validation_rows):
        raise ValueError(
            "Robustness groups do not cover validation rows."
        )

    return output


def validation_robustness(
    validation_rows: Sequence[Mapping[str, Any]],
    probabilities: Sequence[float],
) -> dict[str, list[RobustnessResult]]:
    """Build approved validation robustness summaries."""

    return {
        "month":
            robustness_by_group(
                validation_rows,
                probabilities,
                dimension="month",
                group_getter=lambda row: (
                    row["trial_started_at"]
                    .strftime("%Y-%m")
                ),
            ),

        "platform":
            robustness_by_group(
                validation_rows,
                probabilities,
                dimension="platform",
                group_getter=lambda row:
                    row["platform"],
            ),

        "billing_period":
            robustness_by_group(
                validation_rows,
                probabilities,
                dimension="billing_period",
                group_getter=lambda row:
                    row["billing_period"],
            ),

        "acquisition_channel":
            robustness_by_group(
                validation_rows,
                probabilities,
                dimension="acquisition_channel",
                group_getter=lambda row:
                    row["acquisition_channel"],
            ),
    }
