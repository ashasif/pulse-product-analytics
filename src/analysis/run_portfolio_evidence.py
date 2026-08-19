"""Run Pulse Phase 4 Step 5 portfolio evidence generation."""

from pathlib import Path

from src.analysis.portfolio_evidence import (
    build_portfolio_evidence,
    validate_phase4_lineage,
)


OUTPUT_ROOT = Path("outputs/phase4")
PORTFOLIO_DIR = OUTPUT_ROOT / "portfolio"


def main() -> None:
    lineage = validate_phase4_lineage(
        OUTPUT_ROOT
    )

    paths = build_portfolio_evidence(
        OUTPUT_ROOT,
        PORTFOLIO_DIR,
    )

    print("=== PHASE 4 STEP 5 ===")
    print("analysis: portfolio evidence + closure validation")
    print(
        f"ingestion_batch_id: "
        f"{lineage['ingestion_batch_id']}"
    )
    print(
        f"analytics_build_run_id: "
        f"{lineage['analytics_build_run_id']}"
    )
    print(
        f"observation_cutoff_at: "
        f"{lineage['observation_cutoff_at']}"
    )

    print()
    print("=== GENERATED PORTFOLIO EVIDENCE ===")

    for name, path in paths.items():
        print(f"{name}: {path}")

    print()
    print("Phase 4 shared lineage: PASS")
    print("Portfolio evidence generation: PASS")


if __name__ == "__main__":
    main()
