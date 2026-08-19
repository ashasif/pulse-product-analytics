"""Run Pulse Phase 4 Step 3 analysis."""

from __future__ import annotations

from pathlib import Path

from src.analysis.engagement_monetisation import (
    build_engagement_monetisation_snapshot,
    export_engagement_monetisation_snapshot,
    feature_highlight,
)


OUTPUT_DIR = Path("outputs/phase4/step3")


def main() -> None:
    snapshot = build_engagement_monetisation_snapshot()

    paths = export_engagement_monetisation_snapshot(
        snapshot,
        OUTPUT_DIR,
    )

    context = snapshot["context"]
    revenue = snapshot["revenue_summary"][0]
    trial = snapshot["trial_conversion_summary"][0]
    retention = snapshot["retention_summary"][0]
    feature = feature_highlight(
        snapshot["feature_engagement"]
    )

    print("=== PHASE 4 STEP 3 ===")
    print(
        "analysis: engagement, monetisation and retention"
    )
    print(
        f"ingestion_batch_id: "
        f"{context.ingestion_batch_id}"
    )
    print(
        f"analytics_build_run_id: "
        f"{context.analytics_build_run_id}"
    )
    print(
        f"observation_cutoff_at: "
        f"{context.observation_cutoff_at}"
    )

    print()
    print("=== DATASET ROW COUNTS ===")

    for name in (
        "monthly_engagement",
        "feature_engagement",
        "revenue_summary",
        "monthly_revenue",
        "trial_conversion_summary",
        "retention_summary",
        "retention_by_billing_period",
        "retention_by_acquisition_channel",
    ):
        print(
            f"{name}: {len(snapshot[name])}"
        )

    print()
    print("=== COMMERCIAL SUMMARY ===")
    print(
        f"payment_attempts: "
        f"{revenue['payment_attempt_count']}"
    )
    print(
        f"successful_payment_revenue_gbp: "
        f"{revenue['successful_payment_revenue_gbp']}"
    )
    print(
        f"payment_failure_rate: "
        f"{revenue['payment_failure_rate']}"
    )
    print(
        f"renewal_success_rate: "
        f"{revenue['renewal_success_rate']}"
    )
    print(
        f"trial_to_paid_conversion_rate: "
        f"{trial['trial_to_paid_conversion_rate']}"
    )

    print()
    print("=== RETENTION ===")

    for horizon in (30, 90, 180, 365):
        print(
            f"D{horizon}: "
            f"{retention[f'paid_retention_d{horizon}']}"
        )

    print()
    print("=== FEATURE HIGHLIGHT ===")

    if feature is None:
        print("top_feature: n/a")
    else:
        print(
            f"top_feature: "
            f"{feature['feature_name']}"
        )
        print(
            f"feature_use_events: "
            f"{feature['feature_use_event_count']}"
        )

    print()
    print("=== GENERATED OUTPUTS ===")

    for name, path in paths.items():
        print(f"{name}: {path}")

    print()
    print("Phase 4 Step 3 analysis run: PASS")


if __name__ == "__main__":
    main()
