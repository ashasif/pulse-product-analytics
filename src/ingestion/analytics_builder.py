"""Controlled PostgreSQL staging-to-analytics warehouse build."""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from src.ingestion.database import connect_database


class AnalyticsBuildError(RuntimeError):
    """Raised when a PostgreSQL analytics build fails."""


@dataclass(frozen=True)
class DatasetAnalyticsResult:
    """One staging-to-analytics reconciliation result."""

    dataset_name: str
    staging_row_count: int
    analytics_row_count: int

    @property
    def reconciled(self) -> bool:
        return (
            self.staging_row_count
            == self.analytics_row_count
        )


@dataclass(frozen=True)
class AnalyticsBuildResult:
    """Summary of one analytics warehouse build."""

    analytics_build_run_id: int
    ingestion_batch_id: int
    validation_run_id: int
    promotion_run_id: int

    snapshot_id: str
    status: str

    source_staging_row_count: int
    analytics_row_count: int

    experiment_count: int
    date_count: int

    already_built: bool

    datasets: tuple[
        DatasetAnalyticsResult,
        ...
    ] = ()


def _read_reconciliation(
    cursor,
    ingestion_batch_id: int,
) -> tuple[DatasetAnalyticsResult, ...]:
    """Read deterministic staging-to-analytics reconciliation."""

    cursor.execute(
        """
        SELECT
            dataset_name,
            staging_row_count,
            analytics_row_count
        FROM validation.analytics_reconciliation
        WHERE ingestion_batch_id = %s
        ORDER BY dataset_name
        """,
        (ingestion_batch_id,),
    )

    return tuple(
        DatasetAnalyticsResult(
            dataset_name=str(row[0]),
            staging_row_count=int(row[1]),
            analytics_row_count=int(row[2]),
        )
        for row in cursor.fetchall()
    )


def build_analytics_batch(
    ingestion_batch_id: int,
    *,
    connection=None,
) -> AnalyticsBuildResult:
    """Build one successfully promoted staging batch."""

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

    try:

        with resolved_connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT
                    result_build_run_id,
                    result_status,
                    result_already_built,
                    result_validation_run_id,
                    result_promotion_run_id,
                    result_source_staging_rows,
                    result_analytics_rows,
                    result_error_message
                FROM analytics.build_promoted_batch(%s)
                """,
                (ingestion_batch_id,),
            )

            row = cursor.fetchone()

            if row is None:
                raise AnalyticsBuildError(
                    "PostgreSQL returned no analytics build result."
                )

            (
                analytics_build_run_id,
                status,
                already_built,
                validation_run_id,
                promotion_run_id,
                source_staging_row_count,
                analytics_row_count,
                error_message,
            ) = row

            if status == "failed":
                resolved_connection.commit()

                raise AnalyticsBuildError(
                    "Analytics build failed and was rolled back: "
                    f"{error_message}"
                )

            cursor.execute(
                """
                SELECT snapshot_id
                FROM raw.ingestion_batches
                WHERE ingestion_batch_id = %s
                """,
                (ingestion_batch_id,),
            )

            snapshot_row = cursor.fetchone()

            if snapshot_row is None:
                raise AnalyticsBuildError(
                    "Ingestion snapshot metadata disappeared."
                )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM analytics.dim_experiment
                WHERE ingestion_batch_id = %s
                """,
                (ingestion_batch_id,),
            )

            experiment_count = int(
                cursor.fetchone()[0]
            )

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM analytics.dim_date
                """
            )

            date_count = int(
                cursor.fetchone()[0]
            )

            datasets = _read_reconciliation(
                cursor,
                ingestion_batch_id,
            )

        resolved_connection.commit()

        return AnalyticsBuildResult(
            analytics_build_run_id=int(
                analytics_build_run_id
            ),
            ingestion_batch_id=ingestion_batch_id,
            validation_run_id=int(
                validation_run_id
            ),
            promotion_run_id=int(
                promotion_run_id
            ),
            snapshot_id=str(
                snapshot_row[0]
            ),
            status=str(status),
            source_staging_row_count=int(
                source_staging_row_count
            ),
            analytics_row_count=int(
                analytics_row_count
            ),
            experiment_count=experiment_count,
            date_count=date_count,
            already_built=bool(
                already_built
            ),
            datasets=datasets,
        )

    except AnalyticsBuildError:
        if resolved_connection.info.transaction_status:
            resolved_connection.rollback()
        raise

    except Exception as exc:
        resolved_connection.rollback()

        raise AnalyticsBuildError(
            "PostgreSQL analytics build failed operationally."
        ) from exc

    finally:
        if owns_connection:
            resolved_connection.close()


def print_build_result(
    result: AnalyticsBuildResult,
) -> None:
    """Print the analytics build summary."""

    print(
        "=== POSTGRESQL ANALYTICS BUILD ==="
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
        "Analytics build run ID:",
        result.analytics_build_run_id,
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
        "Source staging rows:",
        f"{result.source_staging_row_count:,}",
    )

    print(
        "Analytics batch rows:",
        f"{result.analytics_row_count:,}",
    )

    print(
        "Experiment dimension rows:",
        result.experiment_count,
    )

    print(
        "Date dimension rows:",
        result.date_count,
    )

    print(
        "Already built:",
        result.already_built,
    )

    print()
    print(
        "Dataset reconciliation:"
    )

    for dataset in result.datasets:
        print(
            f"  {dataset.dataset_name}: "
            f"staging="
            f"{dataset.staging_row_count:,} "
            f"analytics="
            f"{dataset.analytics_row_count:,} "
            f"reconciled="
            f"{dataset.reconciled}"
        )


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Build one successfully promoted "
            "Pulse staging batch into analytics."
        )
    )

    parser.add_argument(
        "--batch-id",
        type=int,
        required=True,
        help=(
            "Succeeded and promoted ingestion "
            "batch ID."
        ),
    )

    args = parser.parse_args()

    result = build_analytics_batch(
        args.batch_id
    )

    print_build_result(result)


if __name__ == "__main__":
    main()
