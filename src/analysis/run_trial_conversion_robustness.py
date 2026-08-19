"""Run Phase 6 Step 5 calibration, utility and robustness validation."""

from __future__ import annotations

from src.analysis.trial_conversion_baselines import (
    split_rows,
    target_vector,
    validate_temporal_splits,
)
from src.analysis.trial_conversion_dataset import (
    load_trial_conversion_rows,
    validate_trial_conversion_rows,
)
from src.analysis.trial_conversion_robustness import (
    CALIBRATION_METHODS,
    fit_calibration_candidates,
    reliability_bins,
    select_calibration_method,
    targeting_utility,
    validation_robustness,
)
from src.ingestion.database import connect_database


def _metric(value):
    if value is None:
        return "NA"

    return f"{value:.6f}"


def main() -> None:
    """Run Step 5 without scoring final-test populations."""

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
    validation_rows = splits[
        "validation"
    ]

    print(
        "=== PHASE 6 STEP 5 "
        "CALIBRATION / UTILITY / ROBUSTNESS ==="
    )

    print(
        f"training_rows: "
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
        f"boundary_rows_defined_not_scored: "
        f"{summaries['excluded'].row_count}"
    )

    (
        calibration_results,
        calibration_probabilities,
    ) = fit_calibration_candidates(
        train_rows,
        validation_rows,
    )

    print()
    print(
        "=== CALIBRATION COMPARISON ==="
    )

    for method in CALIBRATION_METHODS:
        result = calibration_results[
            method
        ]

        print(method)
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
            f"  probability_mean: "
            f"{result.probability_mean:.6f}"
        )
        print(
            f"  observed_rate: "
            f"{result.observed_rate:.6f}"
        )
        print(
            f"  mean_probability_bias: "
            f"{result.mean_probability_bias:+.6f}"
        )

    selected_method = (
        select_calibration_method(
            calibration_results
        )
    )

    selected_probabilities = (
        calibration_probabilities[
            selected_method
        ]
    )

    validation_targets = target_vector(
        validation_rows
    )

    print()
    print(
        "selected_calibration_method: "
        f"{selected_method}"
    )

    print()
    print(
        "=== RELIABILITY DECILES ==="
    )

    for item in reliability_bins(
        validation_targets,
        selected_probabilities,
    ):
        print(
            f"bin={item.bin_number}, "
            f"n={item.row_count}, "
            f"predicted="
            f"{item.mean_predicted_conversion:.4f}, "
            f"observed="
            f"{item.observed_conversion_rate:.4f}, "
            f"gap="
            f"{item.calibration_gap:+.4f}"
        )

    print()
    print(
        "=== NON-CONVERSION TARGETING UTILITY ==="
    )

    for item in targeting_utility(
        validation_targets,
        selected_probabilities,
    ):
        print(
            f"capacity={item.capacity:.0%}, "
            f"targeted={item.targeted_count}, "
            f"non_conversions_captured="
            f"{item.targeted_non_conversions}/"
            f"{item.total_non_conversions}, "
            f"capture_rate="
            f"{item.non_conversion_capture_rate:.4f}, "
            f"targeted_non_conversion_rate="
            f"{item.targeted_non_conversion_rate:.4f}, "
            f"population_non_conversion_rate="
            f"{item.overall_non_conversion_rate:.4f}, "
            f"lift="
            f"{item.lift_vs_population:.4f}"
        )

    print()
    print(
        "=== VALIDATION ROBUSTNESS ==="
    )

    robustness = validation_robustness(
        validation_rows,
        selected_probabilities,
    )

    for dimension in (
        "month",
        "platform",
        "billing_period",
        "acquisition_channel",
    ):
        print()
        print(
            f"[{dimension}]"
        )

        for item in robustness[
            dimension
        ]:
            print(
                f"{item.group}: "
                f"n={item.row_count}, "
                f"conversion="
                f"{item.conversion_rate:.4f}, "
                f"mean_pred="
                f"{item.mean_predicted_conversion:.4f}, "
                f"brier="
                f"{item.brier_score:.6f}, "
                f"log_loss="
                f"{item.log_loss:.6f}, "
                f"roc_auc="
                f"{_metric(item.roc_auc)}, "
                f"avg_precision="
                f"{_metric(item.average_precision)}"
            )

    print()
    print(
        "final_test_metrics: DEFERRED"
    )
    print(
        "excluded_june_2026_metrics: DEFERRED"
    )
    print(
        "STEP 5 TEST-SET FIREWALL: PASS"
    )


if __name__ == "__main__":
    main()
