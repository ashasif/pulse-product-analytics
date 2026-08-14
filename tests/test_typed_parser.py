"""Tests for Phase 3 Step 2 typed parsing and quarantine handling."""

from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.ingestion.raw_audit import (
    DEFAULT_CONFIG_PATH,
    DatasetContract,
    load_ingestion_contract,
)
from src.ingestion.typed_parser import (
    FieldParseError,
    ParsedRow,
    RejectedRow,
    TypedIngestionError,
    iter_typed_rows,
    parse_field,
    validate_dataset_types,
    validate_field_schema_contract,
)
from src.validation.field_schema import (
    DATASET_FIELD_RULES,
    FieldRule,
)


def _write_csv(
    path: Path,
    header: list[str],
    rows: list[list[str]],
) -> None:

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


INSTALLATION_COLUMNS = (
    "installation_id",
    "anonymous_id",
    "installed_at",
    "platform",
    "acquisition_channel",
    "country_code",
)


VALID_INSTALLATION_ROW = [
    "inst_000001",
    "anon_000001",
    "2024-01-01T10:00:00Z",
    "ios",
    "organic",
    "GB",
]


class FieldSchemaContractTests(
    unittest.TestCase
):

    def test_field_schema_matches_step1_columns(
        self,
    ):

        (
            _,
            contracts,
        ) = load_ingestion_contract(
            DEFAULT_CONFIG_PATH
        )

        validate_field_schema_contract(
            contracts
        )

        actual = {
            dataset_name: tuple(
                rules
            )
            for (
                dataset_name,
                rules,
            ) in (
                DATASET_FIELD_RULES.items()
            )
        }

        expected = {
            contract.name: (
                contract.columns
            )
            for contract in contracts
        }

        self.assertEqual(
            actual,
            expected,
        )

    def test_field_schema_mismatch_is_rejected(
        self,
    ):

        contract = DatasetContract(
            name="installations",
            filename=(
                "installations.csv"
            ),
            expected_rows=1,
            columns=(
                "installation_id",
            ),
        )

        with self.assertRaisesRegex(
            TypedIngestionError,
            (
                "Field-schema dataset mismatch"
                "|Field-schema column mismatch"
            ),
        ):
            validate_field_schema_contract(
                (
                    contract,
                )
            )


class FieldParsingTests(
    unittest.TestCase
):

    def test_valid_primitive_types_are_typed(
        self,
    ):

        timestamp = parse_field(
            "2025-06-01T12:30:45Z",
            FieldRule(
                kind="timestamp"
            ),
        )

        parsed_date = parse_field(
            "2025-06-01",
            FieldRule(
                kind="date"
            ),
        )

        integer = parse_field(
            "42",
            FieldRule(
                kind="integer"
            ),
        )

        decimal = parse_field(
            "11.99",
            FieldRule(
                kind="decimal"
            ),
        )

        boolean = parse_field(
            "true",
            FieldRule(
                kind="boolean"
            ),
        )

        self.assertEqual(
            timestamp,
            datetime(
                2025,
                6,
                1,
                12,
                30,
                45,
                tzinfo=UTC,
            ),
        )

        self.assertEqual(
            parsed_date,
            date(
                2025,
                6,
                1,
            ),
        )

        self.assertEqual(
            integer,
            42,
        )

        self.assertEqual(
            decimal,
            Decimal(
                "11.99"
            ),
        )

        self.assertIs(
            boolean,
            True,
        )

    def test_nullable_blank_returns_none(
        self,
    ):

        self.assertIsNone(
            parse_field(
                "",
                FieldRule(
                    kind="string",
                    nullable=True,
                ),
            )
        )

    def test_required_blank_is_rejected(
        self,
    ):

        with self.assertRaises(
            FieldParseError
        ) as context:

            parse_field(
                "",
                FieldRule(
                    kind="string"
                ),
            )

        self.assertEqual(
            context.exception.code,
            "NULL_NOT_ALLOWED",
        )

    def test_invalid_timestamp_is_rejected(
        self,
    ):

        with self.assertRaises(
            FieldParseError
        ) as context:

            parse_field(
                "2025-06-01 12:30:45",
                FieldRule(
                    kind="timestamp"
                ),
            )

        self.assertEqual(
            context.exception.code,
            "INVALID_TIMESTAMP",
        )

    def test_invalid_boolean_is_rejected(
        self,
    ):

        with self.assertRaises(
            FieldParseError
        ) as context:

            parse_field(
                "TRUE",
                FieldRule(
                    kind="boolean"
                ),
            )

        self.assertEqual(
            context.exception.code,
            "INVALID_BOOLEAN",
        )

    def test_invalid_domain_value_is_rejected(
        self,
    ):

        with self.assertRaises(
            FieldParseError
        ) as context:

            parse_field(
                "windows",
                FieldRule(
                    kind="string",
                    allowed_values=(
                        "ios",
                        "android",
                    ),
                ),
            )

        self.assertEqual(
            context.exception.code,
            "INVALID_DOMAIN",
        )

    def test_decimal_range_is_enforced(
        self,
    ):

        with self.assertRaises(
            FieldParseError
        ) as context:

            parse_field(
                "1.25",
                FieldRule(
                    kind="decimal",
                    minimum=Decimal(
                        "0"
                    ),
                    maximum=Decimal(
                        "1"
                    ),
                ),
            )

        self.assertEqual(
            context.exception.code,
            "OUT_OF_RANGE",
        )

    def test_integer_range_is_enforced(
        self,
    ):

        with self.assertRaises(
            FieldParseError
        ) as context:

            parse_field(
                "3",
                FieldRule(
                    kind="integer",
                    minimum=1,
                    maximum=2,
                ),
            )

        self.assertEqual(
            context.exception.code,
            "OUT_OF_RANGE",
        )


class StreamingTypedRowTests(
    unittest.TestCase
):

    def test_streaming_parser_preserves_source_row_lineage(
        self,
    ):

        with TemporaryDirectory() as directory:

            path = (
                Path(directory)
                / "installations.csv"
            )

            bad_row = list(
                VALID_INSTALLATION_ROW
            )

            bad_row[
                3
            ] = "windows"

            _write_csv(
                path,
                list(
                    INSTALLATION_COLUMNS
                ),
                [
                    VALID_INSTALLATION_ROW,
                    bad_row,
                ],
            )

            rows = list(
                iter_typed_rows(
                    dataset_name=(
                        "installations"
                    ),
                    path=path,
                    columns=(
                        INSTALLATION_COLUMNS
                    ),
                )
            )

            self.assertIsInstance(
                rows[0],
                ParsedRow,
            )

            self.assertEqual(
                rows[
                    0
                ].source_row_number,
                2,
            )

            self.assertEqual(
                rows[
                    0
                ].values[
                    "installed_at"
                ],
                datetime(
                    2024,
                    1,
                    1,
                    10,
                    0,
                    tzinfo=UTC,
                ),
            )

            self.assertIsInstance(
                rows[1],
                RejectedRow,
            )

            self.assertEqual(
                rows[
                    1
                ].source_row_number,
                3,
            )

            self.assertEqual(
                rows[
                    1
                ].issues[
                    0
                ].code,
                "INVALID_DOMAIN",
            )

            self.assertEqual(
                rows[
                    1
                ].issues[
                    0
                ].field,
                "platform",
            )

    def test_column_count_mismatch_is_rejected_as_a_row(
        self,
    ):

        with TemporaryDirectory() as directory:

            path = (
                Path(directory)
                / "installations.csv"
            )

            short_row = (
                VALID_INSTALLATION_ROW[
                    :-1
                ]
            )

            _write_csv(
                path,
                list(
                    INSTALLATION_COLUMNS
                ),
                [
                    short_row,
                ],
            )

            outcome = next(
                iter_typed_rows(
                    dataset_name=(
                        "installations"
                    ),
                    path=path,
                    columns=(
                        INSTALLATION_COLUMNS
                    ),
                )
            )

            self.assertIsInstance(
                outcome,
                RejectedRow,
            )

            self.assertEqual(
                outcome.issues[
                    0
                ].code,
                "COLUMN_COUNT_MISMATCH",
            )

    def test_one_row_can_report_multiple_field_errors(
        self,
    ):

        with TemporaryDirectory() as directory:

            path = (
                Path(directory)
                / "installations.csv"
            )

            bad_row = list(
                VALID_INSTALLATION_ROW
            )

            bad_row[
                2
            ] = "not-a-timestamp"

            bad_row[
                3
            ] = "windows"

            _write_csv(
                path,
                list(
                    INSTALLATION_COLUMNS
                ),
                [
                    bad_row,
                ],
            )

            outcome = next(
                iter_typed_rows(
                    dataset_name=(
                        "installations"
                    ),
                    path=path,
                    columns=(
                        INSTALLATION_COLUMNS
                    ),
                )
            )

            self.assertIsInstance(
                outcome,
                RejectedRow,
            )

            self.assertEqual(
                [
                    issue.code
                    for issue
                    in outcome.issues
                ],
                [
                    "INVALID_TIMESTAMP",
                    "INVALID_DOMAIN",
                ],
            )


class QuarantineTests(
    unittest.TestCase
):

    def test_invalid_rows_are_written_to_deterministic_quarantine(
        self,
    ):

        with TemporaryDirectory() as directory:

            root = Path(
                directory
            )

            source_dir = (
                root
                / "raw"
            )

            quarantine_dir = (
                root
                / "quarantine"
            )

            bad_row = list(
                VALID_INSTALLATION_ROW
            )

            bad_row[
                3
            ] = "windows"

            _write_csv(
                (
                    source_dir
                    / "installations.csv"
                ),
                list(
                    INSTALLATION_COLUMNS
                ),
                [
                    VALID_INSTALLATION_ROW,
                    bad_row,
                ],
            )

            contract = DatasetContract(
                name="installations",
                filename=(
                    "installations.csv"
                ),
                expected_rows=2,
                columns=(
                    INSTALLATION_COLUMNS
                ),
            )

            result = validate_dataset_types(
                contract=contract,
                source_dir=(
                    source_dir
                ),
                quarantine_dir=(
                    quarantine_dir
                ),
                encoding="utf-8",
                delimiter=",",
            )

            self.assertEqual(
                result.accepted_rows,
                1,
            )

            self.assertEqual(
                result.rejected_rows,
                1,
            )

            self.assertIsNotNone(
                result.quarantine_path
            )

            quarantine_text = (
                result.quarantine_path
                .read_text(
                    encoding="utf-8"
                )
            )

            self.assertIn(
                "INVALID_DOMAIN",
                quarantine_text,
            )

            self.assertIn(
                "platform",
                quarantine_text,
            )

            self.assertIn(
                "windows",
                quarantine_text,
            )

            self.assertIn(
                ",3,",
                quarantine_text,
            )

    def test_clean_rerun_removes_stale_quarantine_file(
        self,
    ):

        with TemporaryDirectory() as directory:

            root = Path(
                directory
            )

            source_dir = (
                root
                / "raw"
            )

            quarantine_dir = (
                root
                / "quarantine"
            )

            quarantine_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            stale = (
                quarantine_dir
                / "installations_rejected.csv"
            )

            stale.write_text(
                "stale\n",
                encoding="utf-8",
            )

            _write_csv(
                (
                    source_dir
                    / "installations.csv"
                ),
                list(
                    INSTALLATION_COLUMNS
                ),
                [
                    VALID_INSTALLATION_ROW,
                ],
            )

            contract = DatasetContract(
                name="installations",
                filename=(
                    "installations.csv"
                ),
                expected_rows=1,
                columns=(
                    INSTALLATION_COLUMNS
                ),
            )

            result = validate_dataset_types(
                contract=contract,
                source_dir=(
                    source_dir
                ),
                quarantine_dir=(
                    quarantine_dir
                ),
                encoding="utf-8",
                delimiter=",",
            )

            self.assertEqual(
                result.accepted_rows,
                1,
            )

            self.assertEqual(
                result.rejected_rows,
                0,
            )

            self.assertIsNone(
                result.quarantine_path
            )

            self.assertFalse(
                stale.exists()
            )


if __name__ == "__main__":
    unittest.main()