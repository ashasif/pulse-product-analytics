"""Streaming typed validation and quarantine handling for Pulse raw CSV files."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterator

from src.ingestion.raw_audit import (
    DEFAULT_CONFIG_PATH,
    DatasetContract,
    RawAuditError,
    audit_raw_snapshot,
    load_ingestion_contract,
)
from src.validation.field_schema import (
    DATASET_FIELD_RULES,
    FieldRule,
    get_field_rules,
)


INTEGER_RE = re.compile(
    r"^-?(?:0|[1-9]\d*)$"
)

DECIMAL_RE = re.compile(
    r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$"
)


class TypedIngestionError(ValueError):
    """Raised when typed ingestion cannot safely continue."""


class FieldParseError(ValueError):
    """Internal exception carrying a stable validation code."""

    def __init__(
        self,
        code: str,
        message: str,
    ):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class RowIssue:
    """One deterministic field or structural validation problem."""

    code: str
    field: str | None
    message: str


@dataclass(frozen=True)
class ParsedRow:
    """One accepted source row with typed Python values and lineage."""

    dataset_name: str
    source_file: str
    source_row_number: int
    values: dict[str, Any]


@dataclass(frozen=True)
class RejectedRow:
    """One rejected source row and the reasons it was rejected."""

    dataset_name: str
    source_file: str
    source_row_number: int
    raw_values: tuple[str, ...]
    issues: tuple[RowIssue, ...]


@dataclass(frozen=True)
class DatasetParseResult:
    """Typed-validation outcome for one dataset."""

    dataset_name: str
    filename: str
    accepted_rows: int
    rejected_rows: int
    quarantine_path: Path | None


@dataclass(frozen=True)
class SnapshotParseResult:
    """Typed-validation outcome for the complete raw snapshot."""

    snapshot_id: str
    files: tuple[
        DatasetParseResult,
        ...,
    ]

    @property
    def total_accepted_rows(
        self,
    ) -> int:
        return sum(
            item.accepted_rows
            for item in self.files
        )

    @property
    def total_rejected_rows(
        self,
    ) -> int:
        return sum(
            item.rejected_rows
            for item in self.files
        )


ParsedOrRejected = (
    ParsedRow
    | RejectedRow
)


def _resolve_project_relative_path(
    config_path: Path,
    configured_path: str,
) -> Path:
    """Resolve a configured path relative to the repository root."""

    path = Path(
        configured_path
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


def validate_field_schema_contract(
    contracts: tuple[
        DatasetContract,
        ...,
    ],
) -> None:
    """Ensure field-level rules cover exactly the Step 1 column contract."""

    expected_datasets = {
        contract.name
        for contract in contracts
    }

    actual_datasets = set(
        DATASET_FIELD_RULES
    )

    if (
        actual_datasets
        != expected_datasets
    ):
        raise TypedIngestionError(
            "Field-schema dataset mismatch: "
            f"missing="
            f"{sorted(expected_datasets - actual_datasets)}, "
            f"extra="
            f"{sorted(actual_datasets - expected_datasets)}"
        )

    for contract in contracts:

        rules = get_field_rules(
            contract.name
        )

        if (
            tuple(rules)
            != contract.columns
        ):
            raise TypedIngestionError(
                "Field-schema column mismatch "
                f"for {contract.name}: "
                f"expected={list(contract.columns)}, "
                f"actual={list(rules)}"
            )


def _reject_surrounding_whitespace(
    raw_value: str,
) -> None:
    if (
        raw_value
        != raw_value.strip()
    ):
        raise FieldParseError(
            "SURROUNDING_WHITESPACE",
            (
                "value contains leading "
                "or trailing whitespace"
            ),
        )


def parse_field(
    raw_value: str,
    rule: FieldRule,
) -> Any:
    """Parse one raw CSV value according to a field rule."""

    if raw_value == "":
        if rule.nullable:
            return None

        raise FieldParseError(
            "NULL_NOT_ALLOWED",
            "blank value is not allowed",
        )

    _reject_surrounding_whitespace(
        raw_value
    )

    if rule.kind == "string":

        value: Any = raw_value

    elif rule.kind == "timestamp":

        try:
            value = datetime.strptime(
                raw_value,
                "%Y-%m-%dT%H:%M:%SZ",
            ).replace(
                tzinfo=UTC
            )

        except ValueError as exc:
            raise FieldParseError(
                "INVALID_TIMESTAMP",
                (
                    "expected UTC timestamp "
                    "in YYYY-MM-DDTHH:MM:SSZ "
                    "format"
                ),
            ) from exc

    elif rule.kind == "date":

        try:
            if len(raw_value) != 10:
                raise ValueError

            value = date.fromisoformat(
                raw_value
            )

        except ValueError as exc:
            raise FieldParseError(
                "INVALID_DATE",
                (
                    "expected date in "
                    "YYYY-MM-DD format"
                ),
            ) from exc

    elif rule.kind == "integer":

        if not INTEGER_RE.fullmatch(
            raw_value
        ):
            raise FieldParseError(
                "INVALID_INTEGER",
                (
                    "expected a base-10 "
                    "integer"
                ),
            )

        value = int(
            raw_value
        )

    elif rule.kind == "decimal":

        if not DECIMAL_RE.fullmatch(
            raw_value
        ):
            raise FieldParseError(
                "INVALID_DECIMAL",
                (
                    "expected a plain "
                    "base-10 decimal"
                ),
            )

        try:
            value = Decimal(
                raw_value
            )

        except InvalidOperation as exc:
            raise FieldParseError(
                "INVALID_DECIMAL",
                "expected a valid decimal",
            ) from exc

        if not value.is_finite():
            raise FieldParseError(
                "INVALID_DECIMAL",
                "decimal must be finite",
            )

    elif rule.kind == "boolean":

        if raw_value == "true":
            value = True

        elif raw_value == "false":
            value = False

        else:
            raise FieldParseError(
                "INVALID_BOOLEAN",
                (
                    "expected lowercase "
                    "true or false"
                ),
            )

    else:
        raise TypedIngestionError(
            "Unsupported field kind: "
            f"{rule.kind}"
        )

    if (
        rule.allowed_values
        is not None
        and value
        not in rule.allowed_values
    ):
        raise FieldParseError(
            "INVALID_DOMAIN",
            (
                "value must be one of "
                f"{list(rule.allowed_values)}"
            ),
        )

    if (
        rule.minimum is not None
        and value < rule.minimum
    ):
        raise FieldParseError(
            "OUT_OF_RANGE",
            (
                "value must be >= "
                f"{rule.minimum}"
            ),
        )

    if (
        rule.maximum is not None
        and value > rule.maximum
    ):
        raise FieldParseError(
            "OUT_OF_RANGE",
            (
                "value must be <= "
                f"{rule.maximum}"
            ),
        )

    return value


def _parse_data_row(
    *,
    dataset_name: str,
    source_file: str,
    source_row_number: int,
    columns: tuple[str, ...],
    raw_values: list[str],
) -> ParsedOrRejected:
    """Parse one CSV data row without loading any other rows into memory."""

    if (
        len(raw_values)
        != len(columns)
    ):
        return RejectedRow(
            dataset_name=(
                dataset_name
            ),
            source_file=(
                source_file
            ),
            source_row_number=(
                source_row_number
            ),
            raw_values=tuple(
                raw_values
            ),
            issues=(
                RowIssue(
                    code=(
                        "COLUMN_COUNT_MISMATCH"
                    ),
                    field=None,
                    message=(
                        f"expected "
                        f"{len(columns)} "
                        "columns, "
                        f"received "
                        f"{len(raw_values)}"
                    ),
                ),
            ),
        )

    rules = get_field_rules(
        dataset_name
    )

    parsed: dict[
        str,
        Any,
    ] = {}

    issues: list[
        RowIssue
    ] = []

    for (
        column,
        raw_value,
    ) in zip(
        columns,
        raw_values,
        strict=True,
    ):

        try:
            parsed[
                column
            ] = parse_field(
                raw_value,
                rules[column],
            )

        except FieldParseError as exc:
            issues.append(
                RowIssue(
                    code=exc.code,
                    field=column,
                    message=str(exc),
                )
            )

    if issues:
        return RejectedRow(
            dataset_name=(
                dataset_name
            ),
            source_file=(
                source_file
            ),
            source_row_number=(
                source_row_number
            ),
            raw_values=tuple(
                raw_values
            ),
            issues=tuple(
                issues
            ),
        )

    return ParsedRow(
        dataset_name=(
            dataset_name
        ),
        source_file=(
            source_file
        ),
        source_row_number=(
            source_row_number
        ),
        values=parsed,
    )


def iter_typed_rows(
    *,
    dataset_name: str,
    path: Path,
    columns: tuple[str, ...],
    encoding: str = "utf-8",
    delimiter: str = ",",
) -> Iterator[
    ParsedOrRejected
]:
    """Yield accepted or rejected rows from a raw CSV in source order."""

    path = Path(
        path
    )

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
                header = tuple(
                    next(reader)
                )

            except StopIteration as exc:
                raise TypedIngestionError(
                    "Raw file is empty: "
                    f"{path.name}"
                ) from exc

            if (
                header
                != columns
            ):
                raise TypedIngestionError(
                    "Header mismatch for "
                    f"{path.name}: "
                    f"expected="
                    f"{list(columns)}, "
                    f"actual="
                    f"{list(header)}"
                )

            for (
                source_row_number,
                raw_values,
            ) in enumerate(
                reader,
                start=2,
            ):

                yield _parse_data_row(
                    dataset_name=(
                        dataset_name
                    ),
                    source_file=(
                        path.name
                    ),
                    source_row_number=(
                        source_row_number
                    ),
                    columns=columns,
                    raw_values=(
                        raw_values
                    ),
                )

    except UnicodeDecodeError as exc:
        raise TypedIngestionError(
            "Raw file is not valid "
            f"{encoding}: "
            f"{path.name}"
        ) from exc

    except csv.Error as exc:
        raise TypedIngestionError(
            "Malformed CSV structure "
            f"in {path.name}: "
            f"{exc}"
        ) from exc


def _raw_record_json(
    rejected: RejectedRow,
    columns: tuple[str, ...],
) -> str:

    if (
        len(rejected.raw_values)
        == len(columns)
    ):
        payload: dict[
            str,
            Any,
        ] = dict(
            zip(
                columns,
                rejected.raw_values,
                strict=True,
            )
        )

    else:
        payload = {
            "values": list(
                rejected.raw_values
            )
        }

    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )


def _write_quarantine_header(
    writer: csv.writer,
) -> None:

    writer.writerow(
        [
            "dataset_name",
            "source_file",
            "source_row_number",
            "error_codes",
            "error_details",
            "raw_record_json",
        ]
    )


def validate_dataset_types(
    *,
    contract: DatasetContract,
    source_dir: Path,
    quarantine_dir: Path,
    encoding: str,
    delimiter: str,
) -> DatasetParseResult:
    """Validate one dataset and deterministically quarantine invalid rows."""

    source_path = (
        source_dir
        / contract.filename
    )

    quarantine_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    quarantine_path = (
        quarantine_dir
        / (
            f"{contract.name}"
            "_rejected.csv"
        )
    )

    temporary_path = (
        quarantine_dir
        / (
            f".{contract.name}"
            "_rejected.tmp"
        )
    )

    if temporary_path.exists():
        temporary_path.unlink()

    accepted_rows = 0
    rejected_rows = 0

    writer: (
        csv.writer
        | None
    ) = None

    quarantine_file = None

    try:

        for outcome in iter_typed_rows(
            dataset_name=(
                contract.name
            ),
            path=source_path,
            columns=(
                contract.columns
            ),
            encoding=encoding,
            delimiter=delimiter,
        ):

            if isinstance(
                outcome,
                ParsedRow,
            ):
                accepted_rows += 1
                continue

            rejected_rows += 1

            if (
                quarantine_file
                is None
            ):

                quarantine_file = (
                    temporary_path.open(
                        "w",
                        encoding="utf-8",
                        newline="",
                    )
                )

                writer = csv.writer(
                    quarantine_file,
                    lineterminator="\n",
                )

                _write_quarantine_header(
                    writer
                )

            assert writer is not None

            writer.writerow(
                [
                    outcome.dataset_name,
                    outcome.source_file,
                    outcome.source_row_number,
                    "|".join(
                        issue.code
                        for issue
                        in outcome.issues
                    ),
                    " | ".join(
                        (
                            (
                                f"{issue.field}: "
                                f"{issue.message}"
                            )
                            if (
                                issue.field
                                is not None
                            )
                            else issue.message
                        )
                        for issue
                        in outcome.issues
                    ),
                    _raw_record_json(
                        outcome,
                        contract.columns,
                    ),
                ]
            )

    except Exception:

        if (
            quarantine_file
            is not None
        ):
            quarantine_file.close()

        if temporary_path.exists():
            temporary_path.unlink()

        raise

    else:

        if (
            quarantine_file
            is not None
        ):
            quarantine_file.close()

    if rejected_rows:

        temporary_path.replace(
            quarantine_path
        )

        final_quarantine_path: (
            Path
            | None
        ) = quarantine_path

    else:

        if temporary_path.exists():
            temporary_path.unlink()

        if quarantine_path.exists():
            quarantine_path.unlink()

        final_quarantine_path = None

    processed_rows = (
        accepted_rows
        + rejected_rows
    )

    if (
        processed_rows
        != contract.expected_rows
    ):
        raise TypedIngestionError(
            "Typed validation row "
            "reconciliation failed for "
            f"{contract.name}: "
            f"expected="
            f"{contract.expected_rows:,}, "
            f"processed="
            f"{processed_rows:,}"
        )

    return DatasetParseResult(
        dataset_name=(
            contract.name
        ),
        filename=(
            contract.filename
        ),
        accepted_rows=(
            accepted_rows
        ),
        rejected_rows=(
            rejected_rows
        ),
        quarantine_path=(
            final_quarantine_path
        ),
    )


def validate_raw_snapshot_types(
    config_path: Path = (
        DEFAULT_CONFIG_PATH
    ),
    *,
    source_dir: Path | None = None,
    quarantine_dir: Path | None = None,
) -> SnapshotParseResult:
    """Audit, type-check and quarantine the complete approved raw snapshot."""

    config_path = Path(
        config_path
    )

    (
        ingestion,
        contracts,
    ) = load_ingestion_contract(
        config_path
    )

    validate_field_schema_contract(
        contracts
    )

    audit = audit_raw_snapshot(
        config_path=config_path,
        source_dir=source_dir,
    )

    resolved_source_dir = (
        audit.source_dir
    )

    if quarantine_dir is None:

        resolved_quarantine_dir = (
            _resolve_project_relative_path(
                config_path,
                str(
                    ingestion[
                        "quarantine_dir"
                    ]
                ),
            )
        )

    else:

        resolved_quarantine_dir = (
            Path(
                quarantine_dir
            ).resolve()
        )

    encoding = str(
        ingestion[
            "encoding"
        ]
    )

    delimiter = str(
        ingestion[
            "delimiter"
        ]
    )

    results = tuple(
        validate_dataset_types(
            contract=contract,
            source_dir=(
                resolved_source_dir
            ),
            quarantine_dir=(
                resolved_quarantine_dir
            ),
            encoding=encoding,
            delimiter=delimiter,
        )
        for contract in contracts
    )

    return SnapshotParseResult(
        snapshot_id=(
            audit.snapshot_id
        ),
        files=results,
    )


def print_validation_result(
    result: SnapshotParseResult,
) -> None:
    """Print a compact Step 2 validation report."""

    print(
        "=== PHASE 3 STEP 2 "
        "— TYPED SCHEMA VALIDATION ==="
    )

    print(
        "Snapshot ID: "
        f"{result.snapshot_id}"
    )

    print()

    for item in result.files:

        quarantine = (
            str(
                item.quarantine_path
            )
            if (
                item.quarantine_path
                is not None
            )
            else "none"
        )

        print(
            f"{item.dataset_name}: "
            f"accepted="
            f"{item.accepted_rows:,} | "
            f"rejected="
            f"{item.rejected_rows:,} | "
            f"quarantine="
            f"{quarantine}"
        )

    print()

    print(
        "Total accepted rows: "
        f"{result.total_accepted_rows:,}"
    )

    print(
        "Total rejected rows: "
        f"{result.total_rejected_rows:,}"
    )

    print(
        "Streaming typed parsing: PASS"
    )

    print(
        "Row reconciliation: PASS"
    )

    if (
        result.total_rejected_rows
        == 0
    ):

        print(
            "Nullability / type / "
            "domain checks: PASS"
        )

        print(
            "Quarantine rejections: 0"
        )

        print(
            "Typed schema validation: PASS"
        )

    else:

        print(
            "Nullability / type / "
            "domain checks: FAIL"
        )

        print(
            "Rejected rows quarantined: PASS"
        )

        print(
            "Typed schema validation: FAIL"
        )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Stream the approved Pulse "
            "raw CSV snapshot through "
            "typed field validation and "
            "quarantine invalid records."
        )
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=(
            DEFAULT_CONFIG_PATH
        ),
    )

    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--quarantine-dir",
        type=Path,
        default=None,
    )

    args = parser.parse_args()

    try:

        result = (
            validate_raw_snapshot_types(
                config_path=(
                    args.config
                ),
                source_dir=(
                    args.source_dir
                ),
                quarantine_dir=(
                    args.quarantine_dir
                ),
            )
        )

    except (
        RawAuditError,
        TypedIngestionError,
    ) as exc:

        print(
            "Typed schema validation: "
            f"ERROR — {exc}"
        )

        raise SystemExit(
            1
        ) from exc

    print_validation_result(
        result
    )

    if (
        result.total_rejected_rows
    ):
        raise SystemExit(
            1
        )


if __name__ == "__main__":
    main()