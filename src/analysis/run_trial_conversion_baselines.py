"""Run Phase 6 Step 3 temporal split and baseline validation."""

from __future__ import annotations

from src.analysis.trial_conversion_baselines import (
    PREDICTOR_COLUMNS,
    STATIC_BASELINE_FEATURES,
    build_linear_preprocessor,
    build_static_logistic_pipeline,
    evaluate_probabilities,
    feature_matrix,
    fit_prevalence_baseline,
    prevalence_predictions,
    split_rows,
    target_vector,
    validate_temporal_splits,
)
from src.analysis.trial_conversion_dataset import (
    load_trial_conversion_rows,
    validate_trial_conversion_rows,
)
from src.ingestion.database import connect_database


def print_metrics(
    name,
    metrics,
) -> None:
    """Print one validation-only metric set."""

    print(name)
    print(
        f"  brier_score: "
        f"{metrics.brier_score:.6f}"
    )
    print(
        f"  log_loss: "
        f"{metrics.log_loss:.6f}"
    )
    print(
        f"  roc_auc: "
        f"{metrics.roc_auc:.6f}"
    )
    print(
        f"  average_precision: "
        f"{metrics.average_precision:.6f}"
    )


def main() -> None:
    """Validate temporal splits, baselines and preprocessing."""

    with connect_database() as connection:
        rows = load_trial_conversion_rows(
            connection
        )

    validate_trial_conversion_rows(
        rows
    )

    splits = split_rows(
        rows
    )

    summaries = validate_temporal_splits(
        splits
    )

    print(
        "=== PHASE 6 STEP 3 TEMPORAL SPLIT ==="
    )

    for name in (
        "train",
        "validation",
        "test",
        "excluded",
    ):
        summary = summaries[name]

        print(
            f"{name}: "
            f"rows={summary.row_count}, "
            f"converted={summary.converted_count}, "
            f"not_converted="
            f"{summary.not_converted_count}, "
            f"rate={summary.conversion_rate:.4f}, "
            f"range="
            f"{summary.earliest_trial_date}"
            f"..{summary.latest_trial_date}"
        )

    train_rows = splits["train"]
    validation_rows = splits[
        "validation"
    ]

    # --------------------------------------------------------
    # Baseline 1: training prevalence only.
    # --------------------------------------------------------

    prevalence = fit_prevalence_baseline(
        train_rows
    )

    validation_targets = target_vector(
        validation_rows
    )

    prevalence_metrics = (
        evaluate_probabilities(
            validation_targets,
            prevalence_predictions(
                prevalence,
                len(validation_rows),
            ),
        )
    )

    print()
    print(
        "=== VALIDATION-ONLY BASELINES ==="
    )

    print(
        f"training_prevalence: "
        f"{prevalence:.6f}"
    )

    print_metrics(
        "prevalence_baseline:",
        prevalence_metrics,
    )

    # --------------------------------------------------------
    # Baseline 2: static/lifecycle logistic regression.
    # No trial-behaviour predictors are allowed here.
    # --------------------------------------------------------

    static_pipeline = (
        build_static_logistic_pipeline()
    )

    static_pipeline.fit(
        feature_matrix(
            train_rows,
            STATIC_BASELINE_FEATURES,
        ),
        target_vector(
            train_rows
        ),
    )

    static_probabilities = (
        static_pipeline.predict_proba(
            feature_matrix(
                validation_rows,
                STATIC_BASELINE_FEATURES,
            )
        )[:, 1]
    )

    static_metrics = (
        evaluate_probabilities(
            validation_targets,
            static_probabilities,
        )
    )

    print_metrics(
        "static_logistic_baseline:",
        static_metrics,
    )

    # --------------------------------------------------------
    # Dry-run the complete 16-feature linear preprocessor.
    # Fit ONLY on training rows.
    # Do not fit a behavioural model yet.
    # --------------------------------------------------------

    full_preprocessor = (
        build_linear_preprocessor(
            PREDICTOR_COLUMNS
        )
    )

    transformed_train = (
        full_preprocessor.fit_transform(
            feature_matrix(
                train_rows,
                PREDICTOR_COLUMNS,
            )
        )
    )

    transformed_validation = (
        full_preprocessor.transform(
            feature_matrix(
                validation_rows,
                PREDICTOR_COLUMNS,
            )
        )
    )

    transformed_test = (
        full_preprocessor.transform(
            feature_matrix(
                splits["test"],
                PREDICTOR_COLUMNS,
            )
        )
    )

    print()
    print(
        "=== PREPROCESSING DRY RUN ==="
    )
    print(
        "preprocessor_fit_population: TRAIN ONLY"
    )
    print(
        f"transformed_train_shape: "
        f"{transformed_train.shape}"
    )
    print(
        f"transformed_validation_shape: "
        f"{transformed_validation.shape}"
    )
    print(
        f"transformed_test_shape: "
        f"{transformed_test.shape}"
    )

    print()
    print(
        "final_test_metrics: DEFERRED"
    )
    print(
        "excluded_june_2026_metrics: DEFERRED"
    )
    print(
        "STEP 3 TEST-SET FIREWALL: PASS"
    )


if __name__ == "__main__":
    main()