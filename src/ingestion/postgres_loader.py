"""PostgreSQL raw-layer ingestion for Pulse.

Phase 3 Step 3 responsibilities:

- audit the approved raw snapshot
- reuse Step 2 typed streaming validation
- detect already-loaded snapshots
- create auditable ingestion metadata
- stream typed rows through PostgreSQL COPY
- attach deterministic row hashes and lineage
- reconcile warehouse row counts
- protect against duplicate snapshot loads
- roll back raw data atomically on failure
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from psycopg import Connection

from src.ingestion.database import (
    DatabaseConfig,
    connect_database,
)
from src.ingestion.raw_audit import (
    DatasetContract,
    RawFileAudit,
    audit_raw_snapshot,
    load_ingestion_contract,
)
from src.ingestion.row_hash import compute_row_hash
from src.ingestion.typed_parser import (
    ParsedRow,
    RejectedRow,
    iter_typed_rows,
    validate_field_schema_contract,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CONFIG_PATH = (
    PROJECT_ROOT
    / "config"
    / "ingestion.toml"
)

_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z][a-z0-9_]*$"
)

_LINEAGE_COPY_COLUMNS = (
    "ingestion_batch_id",
    "source_file",
    "source_row_number",
    "row_hash",
)


class IngestionLoadError(RuntimeError):
    """Raised when PostgreSQL raw ingestion cannot complete safely."""


@dataclass(frozen=True)
class ExistingSuccessfulBatch:
    """Metadata for a snapshot already successfully loaded."""

    ingestion_batch_id: int
    accepted_rows: int
    rejected_rows: int


@dataclass(frozen=True)
class PostgresIngestionResult:
    """Summary returned by a PostgreSQL ingestion attempt."""

    snapshot_id: str
    ingestion_batch_id: int
    status: str
    already_loaded: bool
    accepted_rows: int
    rejected_rows: int


@dataclass
class _FileProgress:
    """In-memory progress used for failure audit metadata."""

    dataset_name: str
    source_file: str
    accepted_rows: int = 0
    rejected_rows: int = 0
    started: bool = False
    completed: bool = False


def _validate_identifier(identifier: str) -> str:
    """Validate a trusted PostgreSQL identifier."""

    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        raise IngestionLoadError(
            f"Unsafe PostgreSQL identifier: {identifier!r}"
        )

    return identifier


def copy_columns(
    contract: DatasetContract,
) -> tuple[str, ...]:
    """Return COPY columns in deterministic warehouse order."""

    return (
        *contract.columns,
        *_LINEAGE_COPY_COLUMNS,
    )


def build_copy_statement(
    contract: DatasetContract,
) -> str:
    """Build the PostgreSQL COPY statement for one raw dataset."""

    table_name = _validate_identifier(
        contract.name
    )

    columns = tuple(
        _validate_identifier(column)
        for column in copy_columns(contract)
    )

    quoted_columns = ", ".join(
        f'"{column}"'
        for column in columns
    )

    return (
        f'COPY "raw"."{table_name}" '
        f"({quoted_columns}) "
        "FROM STDIN"
    )


def build_count_statement(
    contract: DatasetContract,
) -> str:
    """Build a reconciliation count query for one raw table."""

    table_name = _validate_identifier(
        contract.name
    )

    return (
        f'SELECT COUNT(*) FROM "raw"."{table_name}" '
        "WHERE ingestion_batch_id = %s"
    )


def row_to_copy_values(
    *,
    contract: DatasetContract,
    row: ParsedRow,
    ingestion_batch_id: int,
) -> tuple[Any, ...]:
    """Convert a typed ParsedRow into COPY-ready values."""

    if row.dataset_name != contract.name:
        raise IngestionLoadError(
            "Parsed row dataset does not match contract: "
            f"{row.dataset_name!r} != {contract.name!r}"
        )

    row_hash = compute_row_hash(
        dataset_name=contract.name,
        values=row.values,
        columns=contract.columns,
    )

    source_values = tuple(
        row.values[column]
        for column in contract.columns
    )

    return (
        *source_values,
        ingestion_batch_id,
        row.source_file,
        row.source_row_number,
        row_hash,
    )


def rejected_row_message(
    row: RejectedRow,
) -> str:
    """Return a concise deterministic message for a rejected row."""

    issue_text = "; ".join(
        (
            f"{issue.code}"
            f"[{issue.field or '-'}]: "
            f"{issue.message}"
        )
        for issue in row.issues
    )

    return (
        f"{row.dataset_name} "
        f"{row.source_file} "
        f"row {row.source_row_number} "
        f"failed typed validation: "
        f"{issue_text}"
    )


def find_successful_batch(
    connection: Connection,
    snapshot_id: str,
) -> ExistingSuccessfulBatch | None:
    """Return a successful prior batch for the snapshot, if present."""

    row = connection.execute(
        """
        SELECT
            ingestion_batch_id,
            accepted_row_count,
            rejected_row_count
        FROM raw.ingestion_batches
        WHERE snapshot_id = %s
          AND status = 'succeeded'
        """,
        (snapshot_id,),
    ).fetchone()

    if row is None:
        return None

    return ExistingSuccessfulBatch(
        ingestion_batch_id=int(row[0]),
        accepted_rows=int(row[1]),
        rejected_rows=int(row[2]),
    )


def _acquire_snapshot_lock(
    connection: Connection,
    snapshot_id: str,
) -> None:
    """Serialise concurrent attempts for the same snapshot."""

    connection.execute(
        """
        SELECT pg_advisory_lock(
            hashtextextended(%s, 0)
        )
        """,
        (snapshot_id,),
    )


def _create_batch_metadata(
    *,
    connection: Connection,
    snapshot_id: str,
    contracts: tuple[DatasetContract, ...],
    audit_files: tuple[RawFileAudit, ...],
) -> int:
    """Create batch and file metadata before loading raw rows."""

    audit_by_dataset = {
        file.dataset_name: file
        for file in audit_files
    }

    contract_names = {
        contract.name
        for contract in contracts
    }

    audit_names = set(
        audit_by_dataset
    )

    if contract_names != audit_names:
        raise IngestionLoadError(
            "Audit datasets do not match ingestion contract."
        )

    expected_rows = sum(
        contract.expected_rows
        for contract in contracts
    )

    batch_row = connection.execute(
        """
        INSERT INTO raw.ingestion_batches (
            snapshot_id,
            status,
            expected_file_count,
            expected_row_count,
            accepted_row_count,
            rejected_row_count
        )
        VALUES (
            %s,
            'running',
            %s,
            %s,
            0,
            0
        )
        RETURNING ingestion_batch_id
        """,
        (
            snapshot_id,
            len(contracts),
            expected_rows,
        ),
    ).fetchone()

    if batch_row is None:
        raise IngestionLoadError(
            "PostgreSQL did not return an ingestion batch ID."
        )

    ingestion_batch_id = int(
        batch_row[0]
    )

    for contract in contracts:
        audited = audit_by_dataset[
            contract.name
        ]

        if (
            audited.row_count
            != contract.expected_rows
        ):
            raise IngestionLoadError(
                f"{contract.name}: audited row count "
                f"{audited.row_count} does not match "
                f"contract {contract.expected_rows}."
            )

        connection.execute(
            """
            INSERT INTO raw.ingestion_files (
                ingestion_batch_id,
                dataset_name,
                source_file,
                file_sha256,
                expected_row_count,
                accepted_row_count,
                rejected_row_count,
                status
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                0,
                0,
                'pending'
            )
            """,
            (
                ingestion_batch_id,
                contract.name,
                audited.filename,
                audited.sha256,
                contract.expected_rows,
            ),
        )

    return ingestion_batch_id


def _mark_file_loading(
    *,
    connection: Connection,
    ingestion_batch_id: int,
    source_file: str,
) -> None:
    """Mark one source file as actively loading."""

    connection.execute(
        """
        UPDATE raw.ingestion_files
        SET
            status = 'loading',
            started_at = clock_timestamp(),
            completed_at = NULL,
            error_message = NULL
        WHERE ingestion_batch_id = %s
          AND source_file = %s
        """,
        (
            ingestion_batch_id,
            source_file,
        ),
    )


def _mark_file_loaded(
    *,
    connection: Connection,
    ingestion_batch_id: int,
    progress: _FileProgress,
) -> None:
    """Mark a successfully copied source file as loaded."""

    connection.execute(
        """
        UPDATE raw.ingestion_files
        SET
            status = 'loaded',
            accepted_row_count = %s,
            rejected_row_count = %s,
            completed_at = clock_timestamp(),
            error_message = NULL
        WHERE ingestion_batch_id = %s
          AND source_file = %s
        """,
        (
            progress.accepted_rows,
            progress.rejected_rows,
            ingestion_batch_id,
            progress.source_file,
        ),
    )


def _mark_batch_succeeded(
    *,
    connection: Connection,
    ingestion_batch_id: int,
    accepted_rows: int,
    rejected_rows: int,
) -> None:
    """Finish a successful ingestion batch."""

    connection.execute(
        """
        UPDATE raw.ingestion_batches
        SET
            status = 'succeeded',
            accepted_row_count = %s,
            rejected_row_count = %s,
            completed_at = clock_timestamp(),
            error_message = NULL
        WHERE ingestion_batch_id = %s
        """,
        (
            accepted_rows,
            rejected_rows,
            ingestion_batch_id,
        ),
    )


def _record_failed_batch(
    *,
    connection: Connection,
    ingestion_batch_id: int,
    progress_by_dataset: dict[str, _FileProgress],
    failed_dataset: str | None,
    error: Exception,
) -> None:
    """Persist auditable failure metadata after raw rollback."""

    error_message = (
        f"{type(error).__name__}: {error}"
    )

    for progress in progress_by_dataset.values():
        if not progress.started:
            continue

        is_failed_file = (
            failed_dataset
            == progress.dataset_name
            and not progress.completed
        )

        status = (
            "failed"
            if is_failed_file
            else "rolled_back"
        )

        file_error = (
            error_message
            if is_failed_file
            else None
        )

        connection.execute(
            """
            UPDATE raw.ingestion_files
            SET
                status = %s,
                accepted_row_count = %s,
                rejected_row_count = %s,
                started_at = COALESCE(
                    started_at,
                    clock_timestamp()
                ),
                completed_at = clock_timestamp(),
                error_message = %s
            WHERE ingestion_batch_id = %s
              AND source_file = %s
            """,
            (
                status,
                progress.accepted_rows,
                progress.rejected_rows,
                file_error,
                ingestion_batch_id,
                progress.source_file,
            ),
        )

    accepted_rows = sum(
        progress.accepted_rows
        for progress
        in progress_by_dataset.values()
    )

    rejected_rows = sum(
        progress.rejected_rows
        for progress
        in progress_by_dataset.values()
    )

    connection.execute(
        """
        UPDATE raw.ingestion_batches
        SET
            status = 'failed',
            accepted_row_count = %s,
            rejected_row_count = %s,
            completed_at = clock_timestamp(),
            error_message = %s
        WHERE ingestion_batch_id = %s
        """,
        (
            accepted_rows,
            rejected_rows,
            error_message,
            ingestion_batch_id,
        ),
    )


def ingest_raw_snapshot(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    source_dir: Path | None = None,
    database_config: DatabaseConfig | None = None,
) -> PostgresIngestionResult:
    """Audit, validate, and load the approved snapshot into PostgreSQL.

    The complete raw-data load occurs in one PostgreSQL transaction.

    Metadata identifying the attempt is committed before the raw load.
    If the raw transaction fails, all raw rows are rolled back and the
    metadata is updated in a separate transaction to preserve the audit
    history.
    """

    settings, contracts = (
        load_ingestion_contract(
            config_path
        )
    )

    validate_field_schema_contract(
        contracts
    )

    audit = audit_raw_snapshot(
        config_path=config_path,
        source_dir=source_dir,
    )

    audit_by_dataset = {
        file.dataset_name: file
        for file in audit.files
    }

    progress_by_dataset = {
        contract.name: _FileProgress(
            dataset_name=contract.name,
            source_file=contract.filename,
        )
        for contract in contracts
    }

    with connect_database(
        database_config
    ) as connection:
        # Session-level lock persists across commits and is released
        # automatically when this dedicated connection closes.
        _acquire_snapshot_lock(
            connection,
            audit.snapshot_id,
        )

        existing = find_successful_batch(
            connection,
            audit.snapshot_id,
        )

        if existing is not None:
            return PostgresIngestionResult(
                snapshot_id=audit.snapshot_id,
                ingestion_batch_id=(
                    existing.ingestion_batch_id
                ),
                status="already_loaded",
                already_loaded=True,
                accepted_rows=(
                    existing.accepted_rows
                ),
                rejected_rows=(
                    existing.rejected_rows
                ),
            )

        ingestion_batch_id = (
            _create_batch_metadata(
                connection=connection,
                snapshot_id=audit.snapshot_id,
                contracts=contracts,
                audit_files=audit.files,
            )
        )

        # Make the running attempt auditable before beginning
        # the potentially long COPY transaction.
        connection.commit()

        failed_dataset: str | None = None

        try:
            for contract in contracts:
                failed_dataset = (
                    contract.name
                )

                audited_file = (
                    audit_by_dataset[
                        contract.name
                    ]
                )

                progress = (
                    progress_by_dataset[
                        contract.name
                    ]
                )

                progress.started = True

                _mark_file_loading(
                    connection=connection,
                    ingestion_batch_id=(
                        ingestion_batch_id
                    ),
                    source_file=(
                        audited_file.filename
                    ),
                )

                copy_statement = (
                    build_copy_statement(
                        contract
                    )
                )

                with connection.cursor() as cursor:
                    with cursor.copy(
                        copy_statement
                    ) as copy:
                        for item in iter_typed_rows(
                            dataset_name=(
                                contract.name
                            ),
                            path=(
                                audited_file.path
                            ),
                            columns=(
                                contract.columns
                            ),
                            encoding=(
                                settings[
                                    "encoding"
                                ]
                            ),
                            delimiter=(
                                settings[
                                    "delimiter"
                                ]
                            ),
                        ):
                            if isinstance(
                                item,
                                RejectedRow,
                            ):
                                (
                                    progress
                                    .rejected_rows
                                ) += 1

                                raise (
                                    IngestionLoadError(
                                        rejected_row_message(
                                            item
                                        )
                                    )
                                )

                            if not isinstance(
                                item,
                                ParsedRow,
                            ):
                                raise (
                                    IngestionLoadError(
                                        "Unexpected typed "
                                        "parser result."
                                    )
                                )

                            values = (
                                row_to_copy_values(
                                    contract=contract,
                                    row=item,
                                    ingestion_batch_id=(
                                        ingestion_batch_id
                                    ),
                                )
                            )

                            copy.write_row(
                                values
                            )

                            (
                                progress
                                .accepted_rows
                            ) += 1

                if (
                    progress.accepted_rows
                    + progress.rejected_rows
                    != contract.expected_rows
                ):
                    raise IngestionLoadError(
                        f"{contract.name}: "
                        "loader row reconciliation "
                        "failed. "
                        f"expected="
                        f"{contract.expected_rows}, "
                        f"accepted="
                        f"{progress.accepted_rows}, "
                        f"rejected="
                        f"{progress.rejected_rows}"
                    )

                database_row = (
                    connection.execute(
                        build_count_statement(
                            contract
                        ),
                        (
                            ingestion_batch_id,
                        ),
                    ).fetchone()
                )

                database_count = (
                    int(database_row[0])
                    if database_row
                    is not None
                    else -1
                )

                if (
                    database_count
                    != progress.accepted_rows
                ):
                    raise IngestionLoadError(
                        f"{contract.name}: "
                        "PostgreSQL row count "
                        "does not match copied rows. "
                        f"database="
                        f"{database_count}, "
                        f"copied="
                        f"{progress.accepted_rows}"
                    )

                _mark_file_loaded(
                    connection=connection,
                    ingestion_batch_id=(
                        ingestion_batch_id
                    ),
                    progress=progress,
                )

                progress.completed = True

            # A failure after this point is batch-level rather
            # than attributable to one particular source file.
            failed_dataset = None

            accepted_rows = sum(
                progress.accepted_rows
                for progress
                in progress_by_dataset.values()
            )

            rejected_rows = sum(
                progress.rejected_rows
                for progress
                in progress_by_dataset.values()
            )

            expected_rows = sum(
                contract.expected_rows
                for contract in contracts
            )

            if (
                accepted_rows
                + rejected_rows
                != expected_rows
            ):
                raise IngestionLoadError(
                    "Snapshot row reconciliation "
                    "failed before commit."
                )

            _mark_batch_succeeded(
                connection=connection,
                ingestion_batch_id=(
                    ingestion_batch_id
                ),
                accepted_rows=(
                    accepted_rows
                ),
                rejected_rows=(
                    rejected_rows
                ),
            )

            # Atomic commit of all eight raw datasets plus their
            # successful file/batch state changes.
            connection.commit()

            return PostgresIngestionResult(
                snapshot_id=audit.snapshot_id,
                ingestion_batch_id=(
                    ingestion_batch_id
                ),
                status="succeeded",
                already_loaded=False,
                accepted_rows=accepted_rows,
                rejected_rows=rejected_rows,
            )

        except Exception as exc:
            # Removes every raw row written by the current attempt.
            connection.rollback()

            try:
                _record_failed_batch(
                    connection=connection,
                    ingestion_batch_id=(
                        ingestion_batch_id
                    ),
                    progress_by_dataset=(
                        progress_by_dataset
                    ),
                    failed_dataset=(
                        failed_dataset
                    ),
                    error=exc,
                )

                connection.commit()

            except Exception as metadata_exc:
                connection.rollback()

                raise IngestionLoadError(
                    "Raw ingestion failed and "
                    "failure metadata could not "
                    "be persisted: "
                    f"{metadata_exc}"
                ) from exc

            if isinstance(
                exc,
                IngestionLoadError,
            ):
                raise

            raise IngestionLoadError(
                "PostgreSQL raw ingestion failed: "
                f"{exc}"
            ) from exc


def print_ingestion_result(
    result: PostgresIngestionResult,
) -> None:
    """Print a concise ingestion summary."""

    print(
        "=== POSTGRESQL RAW INGESTION ==="
    )
    print(
        f"Snapshot ID: {result.snapshot_id}"
    )
    print(
        "Ingestion batch ID: "
        f"{result.ingestion_batch_id}"
    )
    print(
        f"Status: {result.status}"
    )
    print(
        f"Accepted rows: "
        f"{result.accepted_rows:,}"
    )
    print(
        f"Rejected rows: "
        f"{result.rejected_rows:,}"
    )
    print(
        "Already loaded: "
        f"{result.already_loaded}"
    )


def main() -> None:
    """CLI entry point."""

    result = ingest_raw_snapshot()
    print_ingestion_result(
        result
    )


if __name__ == "__main__":
    main()
