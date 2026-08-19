"""Run Pulse Phase 4 Step 4 experiment and synthesis analysis."""

from __future__ import annotations

from pathlib import Path

from src.analysis.experiment_synthesis import (
    build_experiment_snapshot,
    export_experiment_synthesis,
    load_prior_business_context,
)


OUTPUT_ROOT = Path("outputs/phase4")
OUTPUT_DIR = OUTPUT_ROOT / "step4"


def main() -> None:
    snapshot = build_experiment_snapshot()
    context = snapshot["context"]

    prior = load_prior_business_context(
        OUTPUT_ROOT,
        context,
    )

    paths = export_experiment_synthesis(
        snapshot,
        prior,
        OUTPUT_DIR,
    )

    variants = snapshot["experiment_variant_summary"]
    maturity = snapshot["experiment_maturity_summary"]
    comparisons = snapshot[
        "experiment_descriptive_comparisons"
    ]

    experiment_ids = {
        row["experiment_id"]
        for row in variants
    }

    print("=== PHASE 4 STEP 4 ===")
    print(
        "analysis: descriptive experiments + business synthesis"
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
    print("=== EXPERIMENT SUMMARY ===")
    print(
        f"experiments: {len(experiment_ids)}"
    )
    print(
        f"variant_rows: {len(variants)}"
    )
    print(
        f"descriptive_comparisons: "
        f"{len(comparisons)}"
    )

    assigned = sum(
        int(row["assigned_user_count"])
        for row in maturity
    )

    exposed = sum(
        int(row["exposed_user_count"])
        for row in maturity
    )

    mature = sum(
        int(row["mature_analysis_window_count"])
        for row in maturity
    )

    print(
        f"assigned_users: {assigned}"
    )
    print(
        f"exposed_assignments: {exposed}"
    )
    print(
        f"mature_analysis_windows: {mature}"
    )

    print()
    print("=== GENERATED OUTPUTS ===")

    for name, path in paths.items():
        print(f"{name}: {path}")

    print()
    print("Prior Step 2 lineage: PASS")
    print("Prior Step 3 lineage: PASS")
    print("Experiment interpretation: DESCRIPTIVE ONLY")
    print("Phase 4 Step 4 analysis run: PASS")


if __name__ == "__main__":
    main()
