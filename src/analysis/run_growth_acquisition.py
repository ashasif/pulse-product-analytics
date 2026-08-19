"""Run Pulse Phase 4 Step 2 growth and acquisition analysis."""

from __future__ import annotations

from pathlib import Path

from src.analysis.growth_acquisition import (
    build_growth_acquisition_snapshot,
    channel_highlights,
    compare_periods,
    export_growth_acquisition_snapshot,
)


OUTPUT_DIR = Path("outputs/phase4/step2")


def main() -> None:
    snapshot = build_growth_acquisition_snapshot()

    paths = export_growth_acquisition_snapshot(
        snapshot,
        OUTPUT_DIR,
    )

    context = snapshot["context"]
    comparison = compare_periods(
        snapshot["monthly_growth"]
    )
    highlights = channel_highlights(
        snapshot["acquisition_channel_performance"]
    )

    print("=== PHASE 4 STEP 2 ===")
    print(
        "analysis: growth, funnel and acquisition"
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
        "monthly_growth",
        "funnel_summary",
        "acquisition_channel_performance",
        "platform_funnel_performance",
        "country_funnel_performance",
    ):
        print(
            f"{name}: {len(snapshot[name])}"
        )

    print()
    print("=== H1 2024 -> H1 2026 CHANGE ===")

    for metric, value in (
        comparison["percent_change"].items()
    ):
        display = (
            "n/a"
            if value is None
            else f"{value:+.2f}%"
        )
        print(f"{metric}: {display}")

    print()
    print("=== CHANNEL HIGHLIGHTS ===")

    for label, row in highlights.items():
        if row is None:
            print(f"{label}: n/a")
        else:
            print(
                f"{label}: "
                f"{row['acquisition_channel']}"
            )

    print()
    print("=== GENERATED OUTPUTS ===")

    for name, path in paths.items():
        print(f"{name}: {path}")

    print()
    print("Phase 4 Step 2 analysis run: PASS")


if __name__ == "__main__":
    main()
