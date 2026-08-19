"""Run Phase 6 Step 4 behavioural model comparison."""

from __future__ import annotations

from src.analysis.trial_conversion_baselines import (
    split_rows,
    validate_temporal_splits,
)
from src.analysis.trial_conversion_dataset import (
    load_trial_conversion_rows,
    validate_trial_conversion_rows,
)
from src.analysis.trial_conversion_models import (
    MODEL_BEHAVIOURAL_LOGISTIC,
    MODEL_HIST_GRADIENT_BOOSTING,
    MODEL_STATIC_LOGISTIC,
    behavioural_increment_passes,
    fit_validation_models,
    metric_delta,
    rank_validation_models,
)
from src.ingestion.database import connect_database


def print_result(
    result,
) -> None:
    """Print one validation model result."""

    print(result.model_name)
    print(
        f"  brier_score: "
        f"{result.metrics.brier_score:.6f}"
    )
    print(
        f"  log_loss: "
        f"{result.metrics.log_loss:.6f}"
    )
    print(
        f"  roc_auc: "
        f"{result.metrics.roc_auc:.6f}"
    )
    print(
        f"  average_precision: "
        f"{result.metrics.average_precision:.6f}"
    )
    print(
        f"  probability_min: "
        f"{result.probability_min:.6f}"
    )
    print(
        f"  probability_max: "
        f"{result.probability_max:.6f}"
    )
    print(
        f"  probability_mean: "
        f"{result.probability_mean:.6f}"
    )


def print_delta(
    name,
    delta,
) -> None:
    """Print candidate-minus-static validation deltas."""

    print(name)
    print(
        f"  brier_delta: "
        f"{delta['brier_score']:+.6f}"
    )
    print(
        f"  log_loss_delta: "
        f"{delta['log_loss']:+.6f}"
    )
    print(
        f"  roc_auc_delta: "
        f"{delta['roc_auc']:+.6f}"
    )
    print(
        f"  average_precision_delta: "
        f"{delta['average_precision']:+.6f}"
    )


def main() -> None:
    """Run validation-only behavioural model development."""

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

    train_rows = splits["train"]
    validation_rows = splits["validation"]

    print(
        "=== PHASE 6 STEP 4 MODEL DEVELOPMENT ==="
    )
    print(
        f"train_rows: "
        f"{summaries['train'].row_count}"
    )
    print(
        f"validation_rows: "
        f"{summaries['validation'].row_count}"
    )
    print(
        f"final_test_rows_defined_not_scored: "
        f"{summaries['test'].row_count}"
    )
    print(
        f"excluded_boundary_rows_not_scored: "
        f"{summaries['excluded'].row_count}"
    )

    results = fit_validation_models(
        train_rows,
        validation_rows,
    )

    print()
    print(
        "=== VALIDATION MODEL METRICS ==="
    )

    for model_name in (
        MODEL_STATIC_LOGISTIC,
        MODEL_BEHAVIOURAL_LOGISTIC,
        MODEL_HIST_GRADIENT_BOOSTING,
    ):
        print_result(
            results[model_name]
        )

    static_result = results[
        MODEL_STATIC_LOGISTIC
    ]

    print()
    print(
        "=== BEHAVIOURAL INCREMENT VS STATIC ==="
    )

    for model_name in (
        MODEL_BEHAVIOURAL_LOGISTIC,
        MODEL_HIST_GRADIENT_BOOSTING,
    ):
        candidate = results[
            model_name
        ]

        delta = metric_delta(
            candidate,
            static_result,
        )

        print_delta(
            f"{model_name}_minus_static:",
            delta,
        )

        print(
            "  probability_quality_improvement: "
            f"{behavioural_increment_passes(candidate, static_result)}"
        )

    ranking = rank_validation_models(
        results
    )

    print()
    print(
        "=== VALIDATION RANKING ==="
    )

    for rank, result in enumerate(
        ranking,
        start=1,
    ):
        print(
            f"{rank}. "
            f"{result.model_name} "
            f"(brier={result.metrics.brier_score:.6f}, "
            f"log_loss={result.metrics.log_loss:.6f})"
        )

    print()
    print(
        "provisional_validation_champion: "
        f"{ranking[0].model_name}"
    )

    print(
        "final_test_metrics: DEFERRED"
    )
    print(
        "excluded_june_2026_metrics: DEFERRED"
    )
    print(
        "STEP 4 TEST-SET FIREWALL: PASS"
    )


if __name__ == "__main__":
    main()