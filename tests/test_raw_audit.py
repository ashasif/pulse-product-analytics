"""Tests for the Phase 3 raw snapshot audit foundation."""

from __future__ import annotations

import csv
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.generation.export_pipeline import (
    DATASET_SCHEMAS,
)

from src.ingestion.raw_audit import (
    DEFAULT_CONFIG_PATH,
    RawAuditError,
    audit_raw_snapshot,
    load_ingestion_contract,
)


APPROVED_ROW_COUNTS = {
    "installations": 100_000,
    "users": 62_176,
    "product_events": 3_502_815,
    "subscriptions": 8_663,
    "subscription_transactions": 9_350,
    "experiment_assignments": 20_006,
    "marketing_spend": 655,
    "app_releases": 16,
}


def _write_config(
    root: Path,
    *,
    alpha_rows: int = 2,
    beta_rows: int = 1,
) -> Path:
    """Write a small ingestion contract for isolated tests."""

    config_dir = (
        root
        / "config"
    )

    config_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        config_dir
        / "ingestion.toml"
    )

    path.write_text(
        f"""
[ingestion]
source_dir = "data/raw"
quarantine_dir = "data/quarantine"
encoding = "utf-8"
delimiter = ","
reject_unexpected_csv_files = true

[datasets.alpha]
filename = "alpha.csv"
expected_rows = {alpha_rows}
columns = ["id", "value"]

[datasets.beta]
filename = "beta.csv"
expected_rows = {beta_rows}
columns = ["id", "name"]
""".strip()
        + "\n",
        encoding="utf-8",
    )

    return path


def _write_csv(
    path: Path,
    header: list[str],
    rows: list[list[str]],
) -> None:
    """Write deterministic CSV test data."""

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:

        writer = csv.writer(
            file,
            lineterminator="\n",
        )

        writer.writerow(
            header
        )

        writer.writerows(
            rows
        )


class ApprovedIngestionContractTests(
    unittest.TestCase
):
    """Protect continuity between Phase 2 exports and Phase 3 ingestion."""

    def test_phase3_headers_match_phase2_export_contract(
        self,
    ):
        (
            _,
            contracts,
        ) = load_ingestion_contract(
            DEFAULT_CONFIG_PATH
        )

        phase3_schemas = {
            contract.name: (
                contract.columns
            )
            for contract in contracts
        }

        self.assertEqual(
            phase3_schemas,
            DATASET_SCHEMAS,
        )

    def test_phase3_contract_anchors_approved_final_row_counts(
        self,
    ):
        (
            _,
            contracts,
        ) = load_ingestion_contract(
            DEFAULT_CONFIG_PATH
        )

        actual = {
            contract.name: (
                contract.expected_rows
            )
            for contract in contracts
        }

        self.assertEqual(
            actual,
            APPROVED_ROW_COUNTS,
        )


class RawSnapshotAuditTests(
    unittest.TestCase
):
    """Validate source auditing without touching production raw files."""

    def _valid_fixture(
        self,
        root: Path,
    ) -> Path:
        config = _write_config(
            root
        )

        raw_dir = (
            root
            / "data"
            / "raw"
        )

        _write_csv(
            raw_dir / "alpha.csv",
            ["id", "value"],
            [
                ["1", "x"],
                ["2", "y"],
            ],
        )

        _write_csv(
            raw_dir / "beta.csv",
            ["id", "name"],
            [
                ["b1", "Pulse"],
            ],
        )

        return config

    def test_valid_snapshot_passes_and_is_deterministic(
        self,
    ):
        with TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            config = (
                self._valid_fixture(
                    root
                )
            )

            first = (
                audit_raw_snapshot(
                    config
                )
            )

            second = (
                audit_raw_snapshot(
                    config
                )
            )

            self.assertEqual(
                first.snapshot_id,
                second.snapshot_id,
            )

            self.assertEqual(
                first.total_rows,
                3,
            )

            self.assertEqual(
                [
                    file.dataset_name
                    for file
                    in first.files
                ],
                [
                    "alpha",
                    "beta",
                ],
            )

            self.assertTrue(
                all(
                    len(
                        file.sha256
                    )
                    == 64
                    for file
                    in first.files
                )
            )

    def test_content_change_changes_snapshot_id(
        self,
    ):
        with TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            config = (
                self._valid_fixture(
                    root
                )
            )

            first = (
                audit_raw_snapshot(
                    config
                )
            )

            _write_csv(
                (
                    root
                    / "data"
                    / "raw"
                    / "alpha.csv"
                ),
                ["id", "value"],
                [
                    ["1", "changed"],
                    ["2", "y"],
                ],
            )

            second = (
                audit_raw_snapshot(
                    config
                )
            )

            self.assertNotEqual(
                first.snapshot_id,
                second.snapshot_id,
            )

    def test_missing_file_is_rejected(
        self,
    ):
        with TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            config = (
                self._valid_fixture(
                    root
                )
            )

            (
                root
                / "data"
                / "raw"
                / "beta.csv"
            ).unlink()

            with self.assertRaisesRegex(
                RawAuditError,
                "Missing raw CSV files",
            ):
                audit_raw_snapshot(
                    config
                )

    def test_unexpected_csv_file_is_rejected(
        self,
    ):
        with TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            config = (
                self._valid_fixture(
                    root
                )
            )

            _write_csv(
                (
                    root
                    / "data"
                    / "raw"
                    / "extra.csv"
                ),
                ["id"],
                [["1"]],
            )

            with self.assertRaisesRegex(
                RawAuditError,
                "Unexpected raw CSV files",
            ):
                audit_raw_snapshot(
                    config
                )

    def test_header_mismatch_is_rejected(
        self,
    ):
        with TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            config = (
                self._valid_fixture(
                    root
                )
            )

            _write_csv(
                (
                    root
                    / "data"
                    / "raw"
                    / "alpha.csv"
                ),
                ["value", "id"],
                [
                    ["x", "1"],
                    ["y", "2"],
                ],
            )

            with self.assertRaisesRegex(
                RawAuditError,
                "Header mismatch",
            ):
                audit_raw_snapshot(
                    config
                )

    def test_row_count_mismatch_is_rejected(
        self,
    ):
        with TemporaryDirectory() as directory:
            root = Path(
                directory
            )

            config = (
                self._valid_fixture(
                    root
                )
            )

            _write_csv(
                (
                    root
                    / "data"
                    / "raw"
                    / "alpha.csv"
                ),
                ["id", "value"],
                [
                    ["1", "x"],
                ],
            )

            with self.assertRaisesRegex(
                RawAuditError,
                "Row-count mismatch",
            ):
                audit_raw_snapshot(
                    config
                )


if __name__ == "__main__":
    unittest.main()