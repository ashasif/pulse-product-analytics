"""Transactional promotion from validated Pulse raw data into staging."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
from typing import Any

from src.ingestion.database import connect_database
from src.validation.field_schema import DATASET_FIELD_RULES


class StagingPromotionError(RuntimeError):
    """Raised when raw-to-staging promotion cannot complete safely."""


@dataclass(frozen=True)
class DatasetPromotionResult:
    """Reconciliation result for one promoted dataset."""

    dataset_name: str
    raw_row_count: int
    staging_row_count: int

    @property
    def reconciled(self) -> bool:
        return (
            self.raw_row_count
            == self.staging_row_count
        )


@dataclass(frozen=True)
class StagingPromotionResult:
    """Summary of one staging promotion."""

    promotion_run_id: int
    ingestion_batch_id: int
    validation_run_id: int
    snapshot_id: str
    status: str

    expected_dataset_count: int
    promoted_dataset_count: int

    expected_row_count: int
    promoted_row_count: int

    already_promoted: bool

    datasets: tuple[
        DatasetPromotionResult,
        ...
    ] = ()


PROMOTION_ORDER = (
    "installations",
    "users",
    "product_events",
    "subscriptions",
    "subscription_transactions",
    "experiment_assignments",
    "marketing_spend",
    "app_releases",
)

_IDENTIFIER_RE = re.compile(
    r"^[a-z_][a-z0-9_]*$"
)


def _identifier(value: str) -> str:
    """Validate an internal identifier before SQL interpolation."""

    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"Unsafe internal SQL identifier: {value!r}"
        )

    return value


def business_columns(
    dataset_name: str,
) -> tuple[str, ...]:
    """Return approved business columns in deterministic order."""

    try:
        rules = DATASET_FIELD_RULES[
            dataset_name
        ]
    except KeyError as exc:
        raise KeyError(
            "Unknown staging dataset: "
            f"{dataset_name}"
        ) from exc

    return tuple(rules)


def build_insert_statement(
    dataset_name: str,
) -> str:
    """Build deterministic INSERT SELECT promotion SQL."""

    table = _identifier(dataset_name)

    columns = tuple(
        _identifier(column)
        for column in business_columns(
            dataset_name
        )
    )

    target_columns = (
        *columns,
        "ingestion_batch_id",
        "source_file",
        "source_row_number",
        "raw_ingested_at",
        "row_hash",
        "validation_run_id",
    )

    target_sql = ",\n            ".join(
        target_columns
    )

    business_select_sql = ",\n            ".join(
        f"r.{column}"
        for column in columns
    )

    return f"""
        INSERT INTO staging.{table} (
            {target_sql}
        )
        SELECT
            {business_select_sql},
            r.ingestion_batch_id,
            r.source_file,
            r.source_row_number,
            r.ingested_at,
            r.row_hash,
            %s
        FROM raw.{table} AS r
        WHERE r.ingestion_batch_id = %s
        ORDER BY r.source_row_number
    """


def _acquire_promotion_lock(
    cursor,
    ingestion_batch_id: int,
) -> None:
    """Serialize promotion attempts for one ingestion batch."""

    cursor.execute(
        """
        SELECT pg_advisory_xact_lock(
            hashtextextended(
                'pulse-staging-promotion:'
                || %s::TEXT,
                0
            )
        )
        """,
        (ingestion_batch_id,),
    )


def _get_authorization(
    cursor,
    ingestion_batch_id: int,
) -> tuple[str, int, int]:
    """Resolve succeeded raw batch and succeeded validation run."""

    cursor.execute(
        """
        SELECT
            b.snapshot_id,
            b.accepted_row_count,
            v.validation_run_id
        FROM raw.ingestion_batches AS b
        JOIN validation.validation_runs AS v
          ON v.ingestion_batch_id
                = b.ingestion_batch_id
        WHERE b.ingestion_batch_id = %s
          AND b.status = 'succeeded'
          AND v.status = 'succeeded'
        ORDER BY v.validation_run_id
        LIMIT 1
        """,
        (ingestion_batch_id,),
    )

    row = cursor.fetchone()

    if row is None:
        raise StagingPromotionError(
            "The ingestion batch does not have "
            "a succeeded raw load and succeeded "
            "validation run."
        )

    snapshot_id = str(row[0])
    expected_row_count = int(row[1])
    validation_run_id = int(row[2])

    return (
        snapshot_id,
        expected_row_count,
        validation_run_id,
    )


def _find_successful_promotion(
    cursor,
    ingestion_batch_id: int,
) -> tuple[
    int,
    int,
    int,
    int,
    int,
] | None:
    """Return existing successful promotion metadata."""

    cursor.execute(
        """
        SELECT
            promotion_run_id,
            validation_run_id,
            expected_dataset_count,
            expected_row_count,
            promoted_row_count
        FROM staging.promotion_runs
        WHERE ingestion_batch_id = %s
          AND status = 'succeeded'
        ORDER BY promotion_run_id
        LIMIT 1
        """,
        (ingestion_batch_id,),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    return (
        int(row[0]),
        int(row[1]),
        int(row[2]),
        int(row[3]),
        int(row[4]),
    )


def _reconcile_staging(
    cursor,
    ingestion_batch_id: int,
) -> tuple[
    DatasetPromotionResult,
    ...
]:
    """Read deterministic raw-to-staging reconciliation."""

    cursor.execute(
        """
        SELECT
            dataset_name,
            raw_row_count,
            staging_row_count
        FROM validation.staging_reconciliation
        WHERE ingestion_batch_id = %s
        ORDER BY dataset_name
        """,
        (ingestion_batch_id,),
    )

    rows = cursor.fetchall()

    results = tuple(
        DatasetPromotionResult(
            dataset_name=str(row[0]),
            raw_row_count=int(row[1]),
            staging_row_count=int(row[2]),
        )
        for row in rows
    )

    expected_names = set(PROMOTION_ORDER)
    actual_names = {
        result.dataset_name
        for result in results
    }

    if actual_names != expected_names:
        raise StagingPromotionError(
            "Staging reconciliation did not "
            "return exactly the eight approved datasets."
        )

    return results


def _assert_staging_empty(
    cursor,
    ingestion_batch_id: int,
) -> None:
    """Reject unexplained partial staging state."""

    results = _reconcile_staging(
        cursor,
        ingestion_batch_id,
    )

    populated = [
        result
        for result in results
        if result.staging_row_count != 0
    ]

    if populated:
        details = ", ".join(
            (
                f"{result.dataset_name}="
                f"{result.staging_row_count}"
            )
            for result in populated
        )

        raise StagingPromotionError(
            "Staging already contains rows for "
            "a batch without successful promotion metadata: "
            f"{details}"
        )


def _create_promotion_run(
    cursor,
    *,
    ingestion_batch_id: int,
    validation_run_id: int,
    expected_row_count: int,
) -> int:
    """Create running promotion metadata."""

    cursor.execute(
        """
        INSERT INTO staging.promotion_runs (
            ingestion_batch_id,
            validation_run_id,
            status,
            expected_dataset_count,
            expected_row_count
        )
        VALUES (
            %s,
            %s,
            'running',
            %s,
            %s
        )
        RETURNING promotion_run_id
        """,
        (
            ingestion_batch_id,
            validation_run_id,
            len(PROMOTION_ORDER),
            expected_row_count,
        ),
    )

    row = cursor.fetchone()

    if row is None:
        raise StagingPromotionError(
            "PostgreSQL did not return promotion_run_id."
        )

    return int(row[0])


def _promote_dataset(
    cursor,
    *,
    dataset_name: str,
    ingestion_batch_id: int,
    validation_run_id: int,
) -> None:
    """Promote one dataset using INSERT SELECT."""

    cursor.execute(
        build_insert_statement(
            dataset_name
        ),
        (
            validation_run_id,
            ingestion_batch_id,
        ),
    )


def _assert_reconciled(
    results: tuple[
        DatasetPromotionResult,
        ...
    ],
    *,
    expected_row_count: int,
) -> int:
    """Require exact raw-to-staging reconciliation."""

    failures = [
        result
        for result in results
        if not result.reconciled
    ]

    if failures:
        details = ", ".join(
            (
                f"{result.dataset_name}: "
                f"raw={result.raw_row_count}, "
                f"staging={result.staging_row_count}"
            )
            for result in failures
        )

        raise StagingPromotionError(
            "Raw-to-staging reconciliation failed: "
            f"{details}"
        )

    promoted_row_count = sum(
        result.staging_row_count
        for result in results
    )

    if promoted_row_count != expected_row_count:
        raise StagingPromotionError(
            "Promoted total does not reconcile "
            "with the succeeded ingestion batch. "
            f"expected={expected_row_count}, "
            f"actual={promoted_row_count}"
        )

    return promoted_row_count


def _mark_promotion_succeeded(
    cursor,
    *,
    promotion_run_id: int,
    promoted_row_count: int,
) -> None:
    """Finalize successful promotion metadata."""

    cursor.execute(
        """
        UPDATE staging.promotion_runs
        SET
            status = 'succeeded',
            promoted_dataset_count = %s,
            promoted_row_count = %s,
            completed_at = clock_timestamp(),
            error_message = NULL
        WHERE promotion_run_id = %s
        """,
        (
            len(PROMOTION_ORDER),
            promoted_row_count,
            promotion_run_id,
        ),
    )


def _record_failed_promotion(
    connection,
    *,
    ingestion_batch_id: int,
    validation_run_id: int,
    expected_row_count: int,
    error_message: str,
) -> None:
    """Persist failure metadata after promotion rollback."""

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO staging.promotion_runs (
                    ingestion_batch_id,
                    validation_run_id,
                    status,
                    expected_dataset_count,
                    promoted_dataset_count,
                    expected_row_count,
                    promoted_row_count,
                    completed_at,
                    error_message
                )
                VALUES (
                    %s,
                    %s,
                    'failed',
                    %s,
                    0,
                    %s,
                    0,
                    clock_timestamp(),
                    %s
                )
                """,
                (
                    ingestion_batch_id,
                    validation_run_id,
                    len(PROMOTION_ORDER),
                    expected_row_count,
                    error_message[:4000],
                ),
            )

        connection.commit()

    except Exception:
        connection.rollback()


def promote_validated_batch(
    ingestion_batch_id: int,
    *,
    connection=None,
) -> StagingPromotionResult:
    """Promote one successfully validated raw batch transactionally."""

    if ingestion_batch_id <= 0:
        raise ValueError(
            "ingestion_batch_id must be greater than zero."
        )

    owns_connection = connection is None

    resolved_connection = (
        connect_database()
        if owns_connection
        else connection
    )

    validation_run_id: int | None = None
    expected_row_count: int | None = None
    promotion_run_created = False

    try:
        with resolved_connection.cursor() as cursor:

            _acquire_promotion_lock(
                cursor,
                ingestion_batch_id,
            )

            (
                snapshot_id,
                expected_row_count,
                validation_run_id,
            ) = _get_authorization(
                cursor,
                ingestion_batch_id,
            )

            existing = _find_successful_promotion(
                cursor,
                ingestion_batch_id,
            )

            if existing is not None:
                (
                    promotion_run_id,
                    existing_validation_run_id,
                    expected_dataset_count,
                    stored_expected_rows,
                    stored_promoted_rows,
                ) = existing

                if (
                    existing_validation_run_id
                    != validation_run_id
                ):
                    raise StagingPromotionError(
                        "Successful promotion references "
                        "a different validation run."
                    )

                results = _reconcile_staging(
                    cursor,
                    ingestion_batch_id,
                )

                actual_rows = _assert_reconciled(
                    results,
                    expected_row_count=
                        expected_row_count,
                )

                if (
                    expected_dataset_count
                    != len(PROMOTION_ORDER)
                    or stored_expected_rows
                    != expected_row_count
                    or stored_promoted_rows
                    != actual_rows
                ):
                    raise StagingPromotionError(
                        "Successful promotion metadata "
                        "does not match current staging state."
                    )

                resolved_connection.rollback()

                return StagingPromotionResult(
                    promotion_run_id=
                        promotion_run_id,
                    ingestion_batch_id=
                        ingestion_batch_id,
                    validation_run_id=
                        validation_run_id,
                    snapshot_id=snapshot_id,
                    status="succeeded",
                    expected_dataset_count=
                        expected_dataset_count,
                    promoted_dataset_count=
                        len(results),
                    expected_row_count=
                        expected_row_count,
                    promoted_row_count=
                        actual_rows,
                    already_promoted=True,
                    datasets=results,
                )

            _assert_staging_empty(
                cursor,
                ingestion_batch_id,
            )

            promotion_run_id = (
                _create_promotion_run(
                    cursor,
                    ingestion_batch_id=
                        ingestion_batch_id,
                    validation_run_id=
                        validation_run_id,
                    expected_row_count=
                        expected_row_count,
                )
            )

            promotion_run_created = True

            for dataset_name in PROMOTION_ORDER:
                _promote_dataset(
                    cursor,
                    dataset_name=
                        dataset_name,
                    ingestion_batch_id=
                        ingestion_batch_id,
                    validation_run_id=
                        validation_run_id,
                )

            results = _reconcile_staging(
                cursor,
                ingestion_batch_id,
            )

            promoted_row_count = (
                _assert_reconciled(
                    results,
                    expected_row_count=
                        expected_row_count,
                )
            )

            _mark_promotion_succeeded(
                cursor,
                promotion_run_id=
                    promotion_run_id,
                promoted_row_count=
                    promoted_row_count,
            )

        resolved_connection.commit()

        return StagingPromotionResult(
            promotion_run_id=promotion_run_id,
            ingestion_batch_id=
                ingestion_batch_id,
            validation_run_id=
                validation_run_id,
            snapshot_id=snapshot_id,
            status="succeeded",
            expected_dataset_count=
                len(PROMOTION_ORDER),
            promoted_dataset_count=
                len(results),
            expected_row_count=
                expected_row_count,
            promoted_row_count=
                promoted_row_count,
            already_promoted=False,
            datasets=results,
        )

    except Exception as exc:
        resolved_connection.rollback()

        if (
            promotion_run_created
            and validation_run_id is not None
            and expected_row_count is not None
        ):
            _record_failed_promotion(
                resolved_connection,
                ingestion_batch_id=
                    ingestion_batch_id,
                validation_run_id=
                    validation_run_id,
                expected_row_count=
                    expected_row_count,
                error_message=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        if isinstance(
            exc,
            StagingPromotionError,
        ):
            raise

        raise StagingPromotionError(
            "PostgreSQL staging promotion "
            "failed operationally."
        ) from exc

    finally:
        if owns_connection:
            resolved_connection.close()


def print_promotion_result(
    result: StagingPromotionResult,
) -> None:
    """Print a deterministic promotion summary."""

    print(
        "=== POSTGRESQL STAGING PROMOTION ==="
    )

    print(
        "Ingestion batch ID:",
        result.ingestion_batch_id,
    )

    print(
        "Validation run ID:",
        result.validation_run_id,
    )

    print(
        "Promotion run ID:",
        result.promotion_run_id,
    )

    print(
        "Snapshot ID:",
        result.snapshot_id,
    )

    print(
        "Status:",
        result.status,
    )

    print(
        "Expected datasets:",
        result.expected_dataset_count,
    )

    print(
        "Promoted datasets:",
        result.promoted_dataset_count,
    )

    print(
        "Expected rows:",
        f"{result.expected_row_count:,}",
    )

    print(
        "Promoted rows:",
        f"{result.promoted_row_count:,}",
    )

    print(
        "Already promoted:",
        result.already_promoted,
    )

    print()
    print("Dataset reconciliation:")

    for dataset in result.datasets:
        print(
            f"  {dataset.dataset_name}: "
            f"raw={dataset.raw_row_count:,} "
            f"staging={dataset.staging_row_count:,} "
            f"reconciled={dataset.reconciled}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Promote a successfully validated Pulse "
            "raw batch into PostgreSQL staging."
        )
    )

    parser.add_argument(
        "--batch-id",
        required=True,
        type=int,
        help="Succeeded and validated ingestion batch ID.",
    )

    args = parser.parse_args()

    result = promote_validated_batch(
        args.batch_id,
    )

    print_promotion_result(result)


if __name__ == "__main__":
    main()