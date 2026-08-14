"""Audit the approved Pulse raw CSV snapshot before warehouse ingestion."""

from __future__ import annotations

import argparse
import csv
import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "ingestion.toml"
)


class RawAuditError(ValueError):
    """Raised when the raw snapshot does not match the ingestion contract."""


@dataclass(frozen=True)
class DatasetContract:
    """Expected structure for one approved raw dataset."""

    name: str
    filename: str
    expected_rows: int
    columns: tuple[str, ...]


@dataclass(frozen=True)
class RawFileAudit:
    """Audit metadata calculated for one raw file."""

    dataset_name: str
    filename: str
    path: Path
    row_count: int
    byte_size: int
    sha256: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class RawSnapshotAudit:
    """Audit result for the complete raw snapshot."""

    snapshot_id: str
    source_dir: Path
    files: tuple[RawFileAudit, ...]

    @property
    def total_rows(self) -> int:
        """Return total data rows across all audited files."""

        return sum(
            file.row_count
            for file in self.files
        )


def _require_mapping(
    value: Any,
    label: str,
) -> dict[str, Any]:
    """Require a TOML table."""

    if not isinstance(value, dict):
        raise RawAuditError(
            f"{label} must be a TOML table"
        )

    return value


def load_ingestion_contract(
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> tuple[
    dict[str, Any],
    tuple[DatasetContract, ...],
]:
    """Load and validate the Phase 3 ingestion contract."""

    config_path = Path(config_path)

    with config_path.open("rb") as file:
        config = tomllib.load(file)

    ingestion = _require_mapping(
        config.get("ingestion"),
        "[ingestion]",
    )

    datasets = _require_mapping(
        config.get("datasets"),
        "[datasets]",
    )

    required_ingestion_fields = {
        "source_dir",
        "quarantine_dir",
        "encoding",
        "delimiter",
        "reject_unexpected_csv_files",
    }

    missing_fields = (
        required_ingestion_fields
        - set(ingestion)
    )

    if missing_fields:
        raise RawAuditError(
            "Ingestion config is missing fields: "
            f"{sorted(missing_fields)}"
        )

    for field in (
        "source_dir",
        "quarantine_dir",
        "encoding",
    ):
        value = ingestion[field]

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            raise RawAuditError(
                f"ingestion.{field} must be "
                "a non-empty string"
            )

    delimiter = ingestion["delimiter"]

    if (
        not isinstance(delimiter, str)
        or len(delimiter) != 1
    ):
        raise RawAuditError(
            "ingestion.delimiter must be "
            "exactly one character"
        )

    if not isinstance(
        ingestion["reject_unexpected_csv_files"],
        bool,
    ):
        raise RawAuditError(
            "ingestion.reject_unexpected_csv_files "
            "must be true or false"
        )

    contracts: list[DatasetContract] = []
    filenames: set[str] = set()

    for (
        dataset_name,
        raw_contract,
    ) in datasets.items():

        table = _require_mapping(
            raw_contract,
            f"[datasets.{dataset_name}]",
        )

        filename = table.get("filename")
        expected_rows = table.get(
            "expected_rows"
        )
        columns = table.get("columns")

        if (
            not isinstance(filename, str)
            or not filename.endswith(".csv")
        ):
            raise RawAuditError(
                f"datasets.{dataset_name}.filename "
                "must be a CSV filename"
            )

        if filename in filenames:
            raise RawAuditError(
                "Duplicate configured filename: "
                f"{filename}"
            )

        filenames.add(filename)

        if (
            not isinstance(expected_rows, int)
            or expected_rows < 0
        ):
            raise RawAuditError(
                f"datasets.{dataset_name}."
                "expected_rows must be a "
                "non-negative integer"
            )

        if (
            not isinstance(columns, list)
            or not columns
            or not all(
                isinstance(column, str)
                and column
                for column in columns
            )
        ):
            raise RawAuditError(
                f"datasets.{dataset_name}.columns "
                "must be a non-empty string list"
            )

        if len(columns) != len(set(columns)):
            raise RawAuditError(
                f"datasets.{dataset_name}.columns "
                "contains duplicate names"
            )

        contracts.append(
            DatasetContract(
                name=dataset_name,
                filename=filename,
                expected_rows=expected_rows,
                columns=tuple(columns),
            )
        )

    if not contracts:
        raise RawAuditError(
            "At least one dataset contract "
            "is required"
        )

    return (
        ingestion,
        tuple(contracts),
    )


def _resolve_source_dir(
    config_path: Path,
    configured_source_dir: str,
) -> Path:
    """Resolve source path relative to project root."""

    path = Path(
        configured_source_dir
    )

    if path.is_absolute():
        return path

    config_path = Path(
        config_path
    ).resolve()

    project_root = (
        config_path
        .parent
        .parent
    )

    return (
        project_root
        / path
    ).resolve()


def _sha256(
    path: Path,
) -> str:
    """Calculate SHA-256 without loading the whole file into memory."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def _read_header_and_count_rows(
    path: Path,
    *,
    encoding: str,
    delimiter: str,
) -> tuple[
    tuple[str, ...],
    int,
]:
    """Read a CSV header and count data records."""

    try:
        with path.open(
            "r",
            encoding=encoding,
            newline="",
        ) as file:

            reader = csv.reader(
                file,
                delimiter=delimiter,
                strict=True,
            )

            try:
                header = next(reader)

            except StopIteration as exc:
                raise RawAuditError(
                    "Raw file is empty: "
                    f"{path.name}"
                ) from exc

            row_count = sum(
                1
                for _ in reader
            )

    except UnicodeDecodeError as exc:
        raise RawAuditError(
            "Raw file is not valid "
            f"{encoding}: {path.name}"
        ) from exc

    except csv.Error as exc:
        raise RawAuditError(
            "Malformed CSV structure in "
            f"{path.name}: {exc}"
        ) from exc

    return (
        tuple(header),
        row_count,
    )


def audit_raw_snapshot(
    config_path: Path = DEFAULT_CONFIG_PATH,
    source_dir: Path | None = None,
) -> RawSnapshotAudit:
    """Audit the complete approved raw snapshot."""

    config_path = Path(
        config_path
    )

    (
        ingestion,
        contracts,
    ) = load_ingestion_contract(
        config_path
    )

    if source_dir is None:
        source_dir = _resolve_source_dir(
            config_path,
            str(
                ingestion[
                    "source_dir"
                ]
            ),
        )

    else:
        source_dir = Path(
            source_dir
        ).resolve()

    if not source_dir.is_dir():
        raise RawAuditError(
            "Raw source directory does "
            f"not exist: {source_dir}"
        )

    expected_files = {
        contract.filename
        for contract in contracts
    }

    actual_csv_files = {
        path.name
        for path in source_dir.glob(
            "*.csv"
        )
        if path.is_file()
    }

    missing_files = sorted(
        expected_files
        - actual_csv_files
    )

    if missing_files:
        raise RawAuditError(
            "Missing raw CSV files: "
            f"{missing_files}"
        )

    if ingestion[
        "reject_unexpected_csv_files"
    ]:
        unexpected_files = sorted(
            actual_csv_files
            - expected_files
        )

        if unexpected_files:
            raise RawAuditError(
                "Unexpected raw CSV files "
                "are present: "
                f"{unexpected_files}"
            )

    encoding = str(
        ingestion["encoding"]
    )

    delimiter = str(
        ingestion["delimiter"]
    )

    audits: list[
        RawFileAudit
    ] = []

    for contract in contracts:

        path = (
            source_dir
            / contract.filename
        )

        (
            header,
            row_count,
        ) = _read_header_and_count_rows(
            path,
            encoding=encoding,
            delimiter=delimiter,
        )

        if header != contract.columns:
            raise RawAuditError(
                "Header mismatch for "
                f"{contract.filename}: "
                f"expected="
                f"{list(contract.columns)}, "
                f"actual={list(header)}"
            )

        if (
            row_count
            != contract.expected_rows
        ):
            raise RawAuditError(
                "Row-count mismatch for "
                f"{contract.filename}: "
                f"expected="
                f"{contract.expected_rows:,}, "
                f"actual={row_count:,}"
            )

        audits.append(
            RawFileAudit(
                dataset_name=(
                    contract.name
                ),
                filename=(
                    contract.filename
                ),
                path=path,
                row_count=row_count,
                byte_size=(
                    path.stat().st_size
                ),
                sha256=_sha256(path),
                columns=header,
            )
        )

    fingerprint = (
        hashlib.sha256()
    )

    for audit in sorted(
        audits,
        key=lambda item: (
            item.dataset_name
        ),
    ):

        fingerprint.update(
            audit.dataset_name.encode(
                "utf-8"
            )
        )

        fingerprint.update(b"\0")

        fingerprint.update(
            audit.filename.encode(
                "utf-8"
            )
        )

        fingerprint.update(b"\0")

        fingerprint.update(
            str(
                audit.row_count
            ).encode("ascii")
        )

        fingerprint.update(b"\0")

        fingerprint.update(
            audit.sha256.encode(
                "ascii"
            )
        )

        fingerprint.update(b"\n")

    snapshot_id = (
        "raw_"
        + fingerprint.hexdigest()
    )

    return RawSnapshotAudit(
        snapshot_id=snapshot_id,
        source_dir=source_dir,
        files=tuple(audits),
    )


def print_audit(
    audit: RawSnapshotAudit,
) -> None:
    """Print a compact audit report."""

    print(
        "=== PHASE 3 STEP 1 "
        "— RAW SNAPSHOT AUDIT ==="
    )

    print(
        f"Source: {audit.source_dir}"
    )

    print(
        "Snapshot ID: "
        f"{audit.snapshot_id}"
    )

    print()

    for file in audit.files:
        print(
            f"{file.dataset_name}: "
            f"{file.row_count:,} rows | "
            f"{file.byte_size:,} bytes | "
            "sha256="
            f"{file.sha256[:16]}..."
        )

    print()

    print(
        f"Total rows: "
        f"{audit.total_rows:,}"
    )

    print(
        "Expected files: PASS"
    )

    print(
        "Headers / column order: PASS"
    )

    print(
        "Approved row counts: PASS"
    )

    print(
        "CSV readability: PASS"
    )

    print(
        "Deterministic snapshot "
        "fingerprint: PASS"
    )

    print(
        "Raw snapshot audit: PASS"
    )


def main() -> None:
    """Run the command-line raw audit."""

    parser = argparse.ArgumentParser(
        description=(
            "Audit the approved Pulse "
            "raw CSV snapshot before "
            "warehouse ingestion."
        )
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=(
            DEFAULT_CONFIG_PATH
        ),
        help=(
            "Path to the Phase 3 "
            "ingestion TOML contract."
        ),
    )

    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help=(
            "Optional raw source "
            "directory override."
        ),
    )

    args = parser.parse_args()

    audit = audit_raw_snapshot(
        config_path=args.config,
        source_dir=args.source_dir,
    )

    print_audit(
        audit
    )


if __name__ == "__main__":
    main()