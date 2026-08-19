"""Single locked Phase 6 final holdout evaluation."""

from __future__ import annotations

from pathlib import Path

from src.analysis.trial_conversion_baselines import (
    split_rows,
    target_vector,
    validate_temporal_splits,
)
from src.analysis.trial_conversion_dataset import (
    load_trial_conversion_rows,
    validate_trial_conversion_rows,
)
from src.analysis.trial_conversion_final import (
    MODEL_BEHAVIOURAL_LOGISTIC,
    MODEL_STATIC_LOGISTIC,
    behavioural_generalisation_confirmed,
    fit_locked_models,
    paired_bootstrap_deltas,
    render_results_markdown,
    score_locked_models,
    write_results_once,
)
from src.analysis.trial_conversion_robustness import (
    reliability_bins,
    targeting_utility,
    validation_robustness,
)
from src.ingestion.database import connect_database


RESULT_PATH = Path(
    "docs/phase6-final-holdout-results.md"
)


def main() -> None:
    """Perform the one-time locked final evaluation."""

    if RESULT_PATH.exists():
        raise RuntimeError(
            "Final holdout results already exist. "
            "Refusing to rescore."
        )

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

    development_rows = sorted(
        [
            *splits["train"],
            *splits["validation"],
        ],
        key=lambda row: (
            row["trial_started_at"],
            row["subscription_key"],
        ),
    )

    final_test_rows = splits[
        "test"
    ]

    boundary_rows = splits[
        "excluded"
    ]

    if len(development_rows) != 6411:
        raise ValueError(
            "Unexpected development population."
        )

    if len(final_test_rows) != 1991:
        raise ValueError(
            "Unexpected final-test population."
        )

    if len(boundary_rows) != 201:
        raise ValueError(
            "Unexpected June boundary population."
        )

    print(
        "============================================================"
    )
    print(
        "FINAL HOLDOUT IS NOW OPEN"
    )
    print(
        "NO FURTHER MODEL SELECTION OR TUNING IS PERMITTED"
    )
    print(
        "============================================================"
    )

    models = fit_locked_models(
        development_rows
    )

    (
        final_results,
        final_probabilities,
    ) = score_locked_models(
        models,
        final_test_rows,
    )

    final_targets = target_vector(
        final_test_rows
    )

    behavioural_probabilities = (
        final_probabilities[
            MODEL_BEHAVIOURAL_LOGISTIC
        ]
    )

    static_probabilities = (
        final_probabilities[
            MODEL_STATIC_LOGISTIC
        ]
    )

    bootstrap = paired_bootstrap_deltas(
        final_targets,
        behavioural_probabilities,
        static_probabilities,
    )

    reliability = reliability_bins(
        final_targets,
        behavioural_probabilities,
    )

    targeting = targeting_utility(
        final_targets,
        behavioural_probabilities,
    )

    robustness = validation_robustness(
        final_test_rows,
        behavioural_probabilities,
    )

    # Boundary sensitivity occurs only after primary final-test scoring.
    (
        boundary_results,
        _,
    ) = score_locked_models(
        models,
        boundary_rows,
    )

    markdown = render_results_markdown(
        development_count=len(
            development_rows
        ),
        final_test_count=len(
            final_test_rows
        ),
        boundary_count=len(
            boundary_rows
        ),
        final_results=final_results,
        boundary_results=boundary_results,
        bootstrap=bootstrap,
        reliability=reliability,
        targeting=targeting,
        robustness=robustness,
    )

    write_results_once(
        RESULT_PATH,
        markdown,
    )

    print()
    print(markdown)

    print()
    print(
        "FINAL_TEST_PROBABILITY_QUALITY_CONFIRMED: "
        f"{behavioural_generalisation_confirmed(final_results)}"
    )

    print()
    print(
        "FINAL HOLDOUT RESULTS WRITTEN:"
    )
    print(
        RESULT_PATH
    )

    print()
    print(
        "FINAL TEST IS OPEN AND FROZEN"
    )


if __name__ == "__main__":
    main()
