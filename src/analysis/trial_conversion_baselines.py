"""Temporal splits, baselines and preprocessing for Phase 6.

The final test partition is defined here but must remain untouched during
baseline selection and model development.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    OneHotEncoder,
    StandardScaler,
)

from src.analysis.trial_conversion_dataset import (
    LABEL_COLUMN,
    PREDICTOR_COLUMNS,
)


TRAIN_START = date(2024, 1, 1)
VALIDATION_START = date(2025, 7, 1)
TEST_START = date(2026, 1, 1)
EXCLUSION_START = date(2026, 6, 1)

SPLIT_NAMES = (
    "train",
    "validation",
    "test",
    "excluded",
)

CATEGORICAL_FEATURES = (
    "platform",
    "acquisition_channel",
    "country_code",
    "billing_period",
)

STATIC_BASELINE_FEATURES = (
    "platform",
    "acquisition_channel",
    "country_code",
    "billing_period",
    "install_to_signup_hours",
    "signup_to_trial_hours",
    "onboarding_started_before_prediction",
    "onboarding_completed_before_prediction",
)

NUMERIC_FEATURES = tuple(
    feature
    for feature in PREDICTOR_COLUMNS
    if feature not in CATEGORICAL_FEATURES
)


@dataclass(frozen=True)
class SplitSummary:
    """Summary of one temporal partition."""

    name: str
    row_count: int
    converted_count: int
    not_converted_count: int
    conversion_rate: float
    earliest_trial_date: date
    latest_trial_date: date


@dataclass(frozen=True)
class BaselineMetrics:
    """Probability-model evaluation metrics."""

    brier_score: float
    log_loss: float
    roc_auc: float
    average_precision: float


def assign_temporal_split(
    row: Mapping[str, Any],
) -> str:
    """Assign one trial to the frozen out-of-time partition."""

    trial_started_at = row["trial_started_at"]

    if trial_started_at.tzinfo is None:
        raise ValueError(
            "trial_started_at must be timezone-aware."
        )

    trial_date = trial_started_at.date()

    if trial_date < TRAIN_START:
        raise ValueError(
            "Trial predates the approved Phase 6 history."
        )

    if trial_date < VALIDATION_START:
        return "train"

    if trial_date < TEST_START:
        return "validation"

    if trial_date < EXCLUSION_START:
        return "test"

    return "excluded"


def split_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    """Partition rows without randomization."""

    result: dict[str, list[Mapping[str, Any]]] = {
        name: []
        for name in SPLIT_NAMES
    }

    for row in rows:
        result[
            assign_temporal_split(row)
        ].append(row)

    return result


def summarize_split(
    name: str,
    rows: Sequence[Mapping[str, Any]],
) -> SplitSummary:
    """Summarize one temporal split."""

    if not rows:
        raise ValueError(
            f"Temporal split {name!r} is empty."
        )

    targets = [
        int(row[LABEL_COLUMN])
        for row in rows
    ]

    if set(targets) != {0, 1}:
        raise ValueError(
            f"Temporal split {name!r} must contain both classes."
        )

    dates = [
        row["trial_started_at"].date()
        for row in rows
    ]

    converted = sum(targets)
    row_count = len(rows)

    return SplitSummary(
        name=name,
        row_count=row_count,
        converted_count=converted,
        not_converted_count=(
            row_count - converted
        ),
        conversion_rate=(
            converted / row_count
        ),
        earliest_trial_date=min(dates),
        latest_trial_date=max(dates),
    )


def validate_temporal_splits(
    splits: Mapping[
        str,
        Sequence[Mapping[str, Any]],
    ],
) -> dict[str, SplitSummary]:
    """Validate partition exclusivity, coverage and chronology."""

    if set(splits) != set(SPLIT_NAMES):
        raise ValueError(
            "Temporal split mapping does not match the "
            "approved partition contract."
        )

    seen_keys: set[Any] = set()
    summaries: dict[str, SplitSummary] = {}

    for name in SPLIT_NAMES:
        rows = splits[name]

        summary = summarize_split(
            name,
            rows,
        )
        summaries[name] = summary

        for row in rows:
            key = row["subscription_key"]

            if key in seen_keys:
                raise ValueError(
                    "A subscription appears in more than one "
                    f"temporal split: {key}"
                )

            seen_keys.add(key)

            actual = assign_temporal_split(
                row
            )

            if actual != name:
                raise ValueError(
                    "Temporal split assignment mismatch: "
                    f"expected={name}, actual={actual}, "
                    f"subscription_key={key}."
                )

    if not (
        summaries["train"].latest_trial_date
        < summaries["validation"].earliest_trial_date
        <= summaries["validation"].latest_trial_date
        < summaries["test"].earliest_trial_date
        <= summaries["test"].latest_trial_date
        < summaries["excluded"].earliest_trial_date
    ):
        raise ValueError(
            "Temporal partitions overlap or are out of order."
        )

    return summaries


def feature_matrix(
    rows: Sequence[Mapping[str, Any]],
    feature_columns: Sequence[str],
) -> list[list[Any]]:
    """Create an ordered matrix without exposing audit columns."""

    unknown = (
        set(feature_columns)
        - set(PREDICTOR_COLUMNS)
    )

    if unknown:
        raise ValueError(
            "Unknown or non-predictor fields requested: "
            f"{sorted(unknown)}"
        )

    return [
        [
            row[column]
            for column in feature_columns
        ]
        for row in rows
    ]


def target_vector(
    rows: Sequence[Mapping[str, Any]],
) -> list[int]:
    """Return binary canonical targets."""

    targets = [
        int(row[LABEL_COLUMN])
        for row in rows
    ]

    if any(
        value not in (0, 1)
        for value in targets
    ):
        raise ValueError(
            "Trial-conversion target must remain binary."
        )

    return targets


def build_linear_preprocessor(
    feature_columns: Sequence[str],
) -> ColumnTransformer:
    """Build leakage-safe linear-model preprocessing."""

    feature_columns = tuple(
        feature_columns
    )

    unknown = (
        set(feature_columns)
        - set(PREDICTOR_COLUMNS)
    )

    if unknown:
        raise ValueError(
            "Preprocessor received non-predictor fields: "
            f"{sorted(unknown)}"
        )

    categorical_indices = [
        index
        for index, feature in enumerate(
            feature_columns
        )
        if feature in CATEGORICAL_FEATURES
    ]

    numeric_indices = [
        index
        for index, feature in enumerate(
            feature_columns
        )
        if feature in NUMERIC_FEATURES
    ]

    if (
        len(categorical_indices)
        + len(numeric_indices)
        != len(feature_columns)
    ):
        raise ValueError(
            "Every requested feature must have an explicit "
            "preprocessing type."
        )

    numeric_pipeline = Pipeline(
        steps=[
            (
                "imputer",
                SimpleImputer(
                    strategy="median",
                    add_indicator=True,
                ),
            ),
            (
                "scaler",
                StandardScaler(),
            ),
        ]
    )

    return ColumnTransformer(
        transformers=[
            (
                "categorical",
                OneHotEncoder(
                    handle_unknown="ignore",
                ),
                categorical_indices,
            ),
            (
                "numeric",
                numeric_pipeline,
                numeric_indices,
            ),
        ],
        remainder="drop",
    )


def build_static_logistic_pipeline() -> Pipeline:
    """Build the approved non-behavioural logistic baseline."""

    return Pipeline(
        steps=[
            (
                "preprocessor",
                build_linear_preprocessor(
                    STATIC_BASELINE_FEATURES
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


def fit_prevalence_baseline(
    training_rows: Sequence[Mapping[str, Any]],
) -> float:
    """Fit a constant probability using training labels only."""

    targets = target_vector(
        training_rows
    )

    if not targets:
        raise ValueError(
            "Cannot fit prevalence baseline on zero rows."
        )

    if set(targets) != {0, 1}:
        raise ValueError(
            "Training population must contain both classes."
        )

    return sum(targets) / len(targets)


def prevalence_predictions(
    prevalence: float,
    row_count: int,
) -> list[float]:
    """Return constant baseline probabilities."""

    if not 0.0 < prevalence < 1.0:
        raise ValueError(
            "Prevalence must lie strictly between zero and one."
        )

    if row_count < 1:
        raise ValueError(
            "Prediction row count must be positive."
        )

    return [
        prevalence
        for _ in range(row_count)
    ]


def evaluate_probabilities(
    y_true: Sequence[int],
    probabilities: Sequence[float],
) -> BaselineMetrics:
    """Evaluate validation probabilities using approved metrics."""

    y_true = list(y_true)
    probabilities = [
        float(value)
        for value in probabilities
    ]

    if len(y_true) != len(probabilities):
        raise ValueError(
            "Target and probability lengths differ."
        )

    if not y_true:
        raise ValueError(
            "Cannot evaluate an empty population."
        )

    if set(y_true) != {0, 1}:
        raise ValueError(
            "Evaluation population must contain both classes."
        )

    if any(
        probability < 0.0
        or probability > 1.0
        for probability in probabilities
    ):
        raise ValueError(
            "Predicted probabilities must be within [0, 1]."
        )

    return BaselineMetrics(
        brier_score=float(
            brier_score_loss(
                y_true,
                probabilities,
            )
        ),
        log_loss=float(
            log_loss(
                y_true,
                probabilities,
                labels=[0, 1],
            )
        ),
        roc_auc=float(
            roc_auc_score(
                y_true,
                probabilities,
            )
        ),
        average_precision=float(
            average_precision_score(
                y_true,
                probabilities,
            )
        ),
    )