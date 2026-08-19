"""Phase 6 behavioural model development and validation comparison.

Only training and validation partitions are used here.
The frozen final test partition must not be scored in Step 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from src.analysis.trial_conversion_baselines import (
    BaselineMetrics,
    PREDICTOR_COLUMNS,
    STATIC_BASELINE_FEATURES,
    build_linear_preprocessor,
    build_static_logistic_pipeline,
    evaluate_probabilities,
    feature_matrix,
    target_vector,
)


MODEL_STATIC_LOGISTIC = "static_logistic"
MODEL_BEHAVIOURAL_LOGISTIC = "behavioural_logistic"
MODEL_HIST_GRADIENT_BOOSTING = "hist_gradient_boosting"


@dataclass(frozen=True)
class ValidationModelResult:
    """Validation-only model comparison result."""

    model_name: str
    metrics: BaselineMetrics
    probability_min: float
    probability_max: float
    probability_mean: float


def _to_dense(matrix):
    """Convert sparse preprocessing output for dense-only estimators."""

    if hasattr(matrix, "toarray"):
        return matrix.toarray()

    return np.asarray(matrix)


def build_behavioural_logistic_pipeline() -> Pipeline:
    """Build regularized logistic regression with all approved predictors."""

    return Pipeline(
        steps=[
            (
                "preprocessor",
                build_linear_preprocessor(
                    PREDICTOR_COLUMNS
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    l1_ratio=0.0,
                    solver="lbfgs",
                    max_iter=2000,
                ),
            ),
        ]
    )


def build_hist_gradient_boosting_pipeline() -> Pipeline:
    """Build one deterministic nonlinear challenger.

    Hyperparameters are intentionally modest and fixed in Step 4.
    This is a challenger, not a tuning exercise.
    """

    return Pipeline(
        steps=[
            (
                "preprocessor",
                build_linear_preprocessor(
                    PREDICTOR_COLUMNS
                ),
            ),
            (
                "dense",
                FunctionTransformer(
                    _to_dense,
                    accept_sparse=True,
                ),
            ),
            (
                "classifier",
                HistGradientBoostingClassifier(
                    loss="log_loss",
                    learning_rate=0.05,
                    max_iter=200,
                    max_leaf_nodes=15,
                    min_samples_leaf=30,
                    l2_regularization=1.0,
                    random_state=42,
                ),
            ),
        ]
    )


def _validation_result(
    model_name: str,
    y_true: Sequence[int],
    probabilities: Sequence[float],
) -> ValidationModelResult:
    """Create a validated model-comparison record."""

    probabilities = np.asarray(
        probabilities,
        dtype=float,
    )

    if probabilities.ndim != 1:
        raise ValueError(
            "Validation probabilities must be one-dimensional."
        )

    if probabilities.size != len(y_true):
        raise ValueError(
            "Validation probability count does not match target count."
        )

    if np.any(probabilities < 0.0) or np.any(probabilities > 1.0):
        raise ValueError(
            "Validation probabilities must lie within [0, 1]."
        )

    metrics = evaluate_probabilities(
        y_true,
        probabilities.tolist(),
    )

    return ValidationModelResult(
        model_name=model_name,
        metrics=metrics,
        probability_min=float(
            probabilities.min()
        ),
        probability_max=float(
            probabilities.max()
        ),
        probability_mean=float(
            probabilities.mean()
        ),
    )


def fit_validation_models(
    training_rows: Sequence[Mapping[str, Any]],
    validation_rows: Sequence[Mapping[str, Any]],
) -> dict[str, ValidationModelResult]:
    """Fit approved models on training only and score validation only."""

    if not training_rows:
        raise ValueError(
            "Training population is empty."
        )

    if not validation_rows:
        raise ValueError(
            "Validation population is empty."
        )

    training_targets = target_vector(
        training_rows
    )
    validation_targets = target_vector(
        validation_rows
    )

    results: dict[str, ValidationModelResult] = {}

    # --------------------------------------------------------
    # Frozen Step 3 static baseline.
    # --------------------------------------------------------

    static_pipeline = (
        build_static_logistic_pipeline()
    )

    static_pipeline.fit(
        feature_matrix(
            training_rows,
            STATIC_BASELINE_FEATURES,
        ),
        training_targets,
    )

    static_probabilities = (
        static_pipeline.predict_proba(
            feature_matrix(
                validation_rows,
                STATIC_BASELINE_FEATURES,
            )
        )[:, 1]
    )

    results[
        MODEL_STATIC_LOGISTIC
    ] = _validation_result(
        MODEL_STATIC_LOGISTIC,
        validation_targets,
        static_probabilities,
    )

    # --------------------------------------------------------
    # Full 16-feature behavioural logistic model.
    # --------------------------------------------------------

    behavioural_pipeline = (
        build_behavioural_logistic_pipeline()
    )

    behavioural_pipeline.fit(
        feature_matrix(
            training_rows,
            PREDICTOR_COLUMNS,
        ),
        training_targets,
    )

    behavioural_probabilities = (
        behavioural_pipeline.predict_proba(
            feature_matrix(
                validation_rows,
                PREDICTOR_COLUMNS,
            )
        )[:, 1]
    )

    results[
        MODEL_BEHAVIOURAL_LOGISTIC
    ] = _validation_result(
        MODEL_BEHAVIOURAL_LOGISTIC,
        validation_targets,
        behavioural_probabilities,
    )

    # --------------------------------------------------------
    # Single nonlinear challenger.
    # --------------------------------------------------------

    boosting_pipeline = (
        build_hist_gradient_boosting_pipeline()
    )

    boosting_pipeline.fit(
        feature_matrix(
            training_rows,
            PREDICTOR_COLUMNS,
        ),
        training_targets,
    )

    boosting_probabilities = (
        boosting_pipeline.predict_proba(
            feature_matrix(
                validation_rows,
                PREDICTOR_COLUMNS,
            )
        )[:, 1]
    )

    results[
        MODEL_HIST_GRADIENT_BOOSTING
    ] = _validation_result(
        MODEL_HIST_GRADIENT_BOOSTING,
        validation_targets,
        boosting_probabilities,
    )

    return results


def rank_validation_models(
    results: Mapping[
        str,
        ValidationModelResult,
    ],
) -> list[ValidationModelResult]:
    """Rank models by Brier score, then log loss."""

    required = {
        MODEL_STATIC_LOGISTIC,
        MODEL_BEHAVIOURAL_LOGISTIC,
        MODEL_HIST_GRADIENT_BOOSTING,
    }

    if set(results) != required:
        raise ValueError(
            "Model comparison results do not match the "
            "approved Step 4 candidate set."
        )

    return sorted(
        results.values(),
        key=lambda result: (
            result.metrics.brier_score,
            result.metrics.log_loss,
            result.model_name,
        ),
    )


def metric_delta(
    candidate: ValidationModelResult,
    reference: ValidationModelResult,
) -> dict[str, float]:
    """Return candidate-minus-reference metric deltas."""

    return {
        "brier_score": (
            candidate.metrics.brier_score
            - reference.metrics.brier_score
        ),
        "log_loss": (
            candidate.metrics.log_loss
            - reference.metrics.log_loss
        ),
        "roc_auc": (
            candidate.metrics.roc_auc
            - reference.metrics.roc_auc
        ),
        "average_precision": (
            candidate.metrics.average_precision
            - reference.metrics.average_precision
        ),
    }


def behavioural_increment_passes(
    candidate: ValidationModelResult,
    static_reference: ValidationModelResult,
) -> bool:
    """Require improvement on both probability-quality metrics."""

    return (
        candidate.metrics.brier_score
        < static_reference.metrics.brier_score
        and candidate.metrics.log_loss
        < static_reference.metrics.log_loss
    )