"""Run Phase 6 Step 2 point-in-time dataset validation."""

from __future__ import annotations

from src.analysis.trial_conversion_dataset import (
    PREDICTOR_COLUMNS,
    load_reporting_reconciliation,
    load_trial_conversion_rows,
    validate_reporting_reconciliation,
    validate_trial_conversion_rows,
)
from src.ingestion.database import connect_database


def main() -> None:
    """Build and validate the live Phase 6 modelling dataset."""

    with connect_database() as connection:
        reconciliation = load_reporting_reconciliation(
            connection
        )
        validate_reporting_reconciliation(
            reconciliation
        )

        rows = load_trial_conversion_rows(
            connection
        )
        summary = validate_trial_conversion_rows(
            rows
        )

    print("=== PHASE 6 STEP 2 LIVE DATASET ===")
    print(
        "reporting_reconciliation: PASS"
    )
    print(
        f"row_count: {summary.row_count}"
    )
    print(
        f"converted_to_paid: "
        f"{summary.converted_count}"
    )
    print(
        f"not_converted: "
        f"{summary.not_converted_count}"
    )
    print(
        f"conversion_rate: "
        f"{summary.conversion_rate:.4f}"
    )
    print(
        "earliest_prediction_at: "
        f"{summary.earliest_prediction_at.isoformat()}"
    )
    print(
        "latest_prediction_at: "
        f"{summary.latest_prediction_at.isoformat()}"
    )
    print(
        "zero_trial_session_count: "
        f"{summary.zero_trial_session_count}"
    )
    print(
        "zero_trial_feature_count: "
        f"{summary.zero_trial_feature_count}"
    )
    print(
        f"predictor_count: "
        f"{len(PREDICTOR_COLUMNS)}"
    )
    print(
        "predictors:"
    )
    for predictor in PREDICTOR_COLUMNS:
        print(
            f"  - {predictor}"
        )


if __name__ == "__main__":
    main()