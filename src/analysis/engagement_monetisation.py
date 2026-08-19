"""Engagement, monetisation and retention analysis for Pulse Phase 4.

All canonical business measures originate from reporting.*.
Aggregations preserve reporting denominators rather than averaging
pre-computed rates across incompatible grains.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.analysis.reporting_client import (
    ReportingContext,
    fetch_reporting_rows,
    get_reporting_context,
    require_supported_metrics,
)
from src.ingestion.database import DatabaseConfig


STEP3_SUPPORTED_METRICS = (
    "registered_dau",
    "session_count",
    "feature_use_event_count",
    "paywall_view_count",
    "trial_start_count",
    "paid_subscription_start_count",
    "trial_to_paid_conversion_rate",
    "successful_payment_revenue_gbp",
    "payment_failure_rate",
    "renewal_success_rate",
    "paid_retention_d30",
    "paid_retention_d90",
    "paid_retention_d180",
    "paid_retention_d365",
)


def _monthly_engagement(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            date_trunc('month', full_date)::date AS month_start,
            AVG(registered_dau)::numeric AS average_registered_dau,
            MAX(registered_dau)::bigint AS peak_registered_dau,
            SUM(session_count)::bigint AS session_count,
            SUM(feature_use_event_count)::bigint
                AS feature_use_event_count,
            SUM(paywall_view_count)::bigint AS paywall_view_count,
            SUM(trial_start_count)::bigint AS trial_start_count,
            SUM(paid_subscription_start_count)::bigint
                AS paid_subscription_start_count
        FROM reporting.vw_daily_product_kpis
        WHERE analytics_build_run_id = %s
        GROUP BY
            analytics_build_run_id,
            date_trunc('month', full_date)::date
        ORDER BY month_start
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _feature_engagement(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        WITH feature_totals AS (
            SELECT
                MIN(ingestion_batch_id)::bigint
                    AS ingestion_batch_id,
                analytics_build_run_id,
                feature_name,
                SUM(feature_use_event_count)::bigint
                    AS feature_use_event_count
            FROM reporting.vw_daily_feature_engagement
            WHERE analytics_build_run_id = %s
            GROUP BY
                analytics_build_run_id,
                feature_name
        )
        SELECT
            ingestion_batch_id,
            analytics_build_run_id,
            feature_name,
            feature_use_event_count,
            CASE
                WHEN SUM(feature_use_event_count) OVER () = 0
                    THEN NULL
                ELSE feature_use_event_count::numeric
                     / SUM(feature_use_event_count) OVER ()
            END AS feature_use_event_share
        FROM feature_totals
        ORDER BY
            feature_use_event_count DESC,
            feature_name
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _revenue_summary(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            SUM(payment_attempt_count)::bigint
                AS payment_attempt_count,
            SUM(successful_payment_count)::bigint
                AS successful_payment_count,
            SUM(failed_payment_count)::bigint
                AS failed_payment_count,
            CASE
                WHEN SUM(payment_attempt_count) = 0 THEN NULL
                ELSE SUM(failed_payment_count)::numeric
                     / SUM(payment_attempt_count)
            END AS payment_failure_rate,
            SUM(successful_payment_revenue_gbp)::numeric
                AS successful_payment_revenue_gbp,
            SUM(renewal_attempt_count)::bigint
                AS renewal_attempt_count,
            SUM(successful_renewal_count)::bigint
                AS successful_renewal_count,
            SUM(failed_renewal_count)::bigint
                AS failed_renewal_count,
            CASE
                WHEN SUM(renewal_attempt_count) = 0 THEN NULL
                ELSE SUM(successful_renewal_count)::numeric
                     / SUM(renewal_attempt_count)
            END AS renewal_success_rate,
            SUM(renewal_revenue_gbp)::numeric
                AS renewal_revenue_gbp
        FROM reporting.vw_daily_subscription_revenue
        WHERE analytics_build_run_id = %s
        GROUP BY analytics_build_run_id
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _monthly_revenue(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            date_trunc('month', full_date)::date AS month_start,
            SUM(payment_attempt_count)::bigint
                AS payment_attempt_count,
            SUM(successful_payment_count)::bigint
                AS successful_payment_count,
            SUM(failed_payment_count)::bigint
                AS failed_payment_count,
            CASE
                WHEN SUM(payment_attempt_count) = 0 THEN NULL
                ELSE SUM(failed_payment_count)::numeric
                     / SUM(payment_attempt_count)
            END AS payment_failure_rate,
            SUM(successful_payment_revenue_gbp)::numeric
                AS successful_payment_revenue_gbp,
            SUM(renewal_attempt_count)::bigint
                AS renewal_attempt_count,
            SUM(successful_renewal_count)::bigint
                AS successful_renewal_count,
            CASE
                WHEN SUM(renewal_attempt_count) = 0 THEN NULL
                ELSE SUM(successful_renewal_count)::numeric
                     / SUM(renewal_attempt_count)
            END AS renewal_success_rate
        FROM reporting.vw_daily_subscription_revenue
        WHERE analytics_build_run_id = %s
        GROUP BY
            analytics_build_run_id,
            date_trunc('month', full_date)::date
        ORDER BY month_start
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _trial_conversion_summary(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            SUM(trial_count)::bigint AS trial_count,
            SUM(mature_trial_count)::bigint AS mature_trial_count,
            SUM(immature_trial_count)::bigint AS immature_trial_count,
            SUM(mature_trial_paid_conversion_count)::bigint
                AS mature_trial_paid_conversion_count,
            CASE
                WHEN SUM(mature_trial_count) = 0 THEN NULL
                ELSE SUM(mature_trial_paid_conversion_count)::numeric
                     / SUM(mature_trial_count)
            END AS trial_to_paid_conversion_rate
        FROM reporting.vw_trial_conversion_cohorts
        WHERE analytics_build_run_id = %s
        GROUP BY analytics_build_run_id
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _retention_summary(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            SUM(paid_subscription_count)::bigint
                AS paid_subscription_count,

            SUM(mature_d30_count)::bigint AS eligible_d30_count,
            SUM(retained_d30_count)::bigint AS retained_d30_count,
            CASE
                WHEN SUM(mature_d30_count) = 0 THEN NULL
                ELSE SUM(retained_d30_count)::numeric
                     / SUM(mature_d30_count)
            END AS paid_retention_d30,

            SUM(mature_d90_count)::bigint AS eligible_d90_count,
            SUM(retained_d90_count)::bigint AS retained_d90_count,
            CASE
                WHEN SUM(mature_d90_count) = 0 THEN NULL
                ELSE SUM(retained_d90_count)::numeric
                     / SUM(mature_d90_count)
            END AS paid_retention_d90,

            SUM(mature_d180_count)::bigint AS eligible_d180_count,
            SUM(retained_d180_count)::bigint AS retained_d180_count,
            CASE
                WHEN SUM(mature_d180_count) = 0 THEN NULL
                ELSE SUM(retained_d180_count)::numeric
                     / SUM(mature_d180_count)
            END AS paid_retention_d180,

            SUM(mature_d365_count)::bigint AS eligible_d365_count,
            SUM(retained_d365_count)::bigint AS retained_d365_count,
            CASE
                WHEN SUM(mature_d365_count) = 0 THEN NULL
                ELSE SUM(retained_d365_count)::numeric
                     / SUM(mature_d365_count)
            END AS paid_retention_d365
        FROM reporting.vw_paid_retention_cohorts
        WHERE analytics_build_run_id = %s
        GROUP BY analytics_build_run_id
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _retention_by_billing_period(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            billing_period,
            SUM(paid_subscription_count)::bigint
                AS paid_subscription_count,

            SUM(mature_d30_count)::bigint AS eligible_d30_count,
            SUM(retained_d30_count)::bigint AS retained_d30_count,
            CASE
                WHEN SUM(mature_d30_count) = 0 THEN NULL
                ELSE SUM(retained_d30_count)::numeric
                     / SUM(mature_d30_count)
            END AS paid_retention_d30,

            SUM(mature_d90_count)::bigint AS eligible_d90_count,
            SUM(retained_d90_count)::bigint AS retained_d90_count,
            CASE
                WHEN SUM(mature_d90_count) = 0 THEN NULL
                ELSE SUM(retained_d90_count)::numeric
                     / SUM(mature_d90_count)
            END AS paid_retention_d90,

            SUM(mature_d180_count)::bigint AS eligible_d180_count,
            SUM(retained_d180_count)::bigint AS retained_d180_count,
            CASE
                WHEN SUM(mature_d180_count) = 0 THEN NULL
                ELSE SUM(retained_d180_count)::numeric
                     / SUM(mature_d180_count)
            END AS paid_retention_d180,

            SUM(mature_d365_count)::bigint AS eligible_d365_count,
            SUM(retained_d365_count)::bigint AS retained_d365_count,
            CASE
                WHEN SUM(mature_d365_count) = 0 THEN NULL
                ELSE SUM(retained_d365_count)::numeric
                     / SUM(mature_d365_count)
            END AS paid_retention_d365
        FROM reporting.vw_paid_retention_cohorts
        WHERE analytics_build_run_id = %s
        GROUP BY
            analytics_build_run_id,
            billing_period
        ORDER BY billing_period
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _retention_by_acquisition_channel(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            acquisition_channel,
            SUM(paid_subscription_count)::bigint
                AS paid_subscription_count,

            SUM(mature_d30_count)::bigint AS eligible_d30_count,
            SUM(retained_d30_count)::bigint AS retained_d30_count,
            CASE
                WHEN SUM(mature_d30_count) = 0 THEN NULL
                ELSE SUM(retained_d30_count)::numeric
                     / SUM(mature_d30_count)
            END AS paid_retention_d30,

            SUM(mature_d90_count)::bigint AS eligible_d90_count,
            SUM(retained_d90_count)::bigint AS retained_d90_count,
            CASE
                WHEN SUM(mature_d90_count) = 0 THEN NULL
                ELSE SUM(retained_d90_count)::numeric
                     / SUM(mature_d90_count)
            END AS paid_retention_d90,

            SUM(mature_d180_count)::bigint AS eligible_d180_count,
            SUM(retained_d180_count)::bigint AS retained_d180_count,
            CASE
                WHEN SUM(mature_d180_count) = 0 THEN NULL
                ELSE SUM(retained_d180_count)::numeric
                     / SUM(mature_d180_count)
            END AS paid_retention_d180,

            SUM(mature_d365_count)::bigint AS eligible_d365_count,
            SUM(retained_d365_count)::bigint AS retained_d365_count,
            CASE
                WHEN SUM(mature_d365_count) = 0 THEN NULL
                ELSE SUM(retained_d365_count)::numeric
                     / SUM(mature_d365_count)
            END AS paid_retention_d365
        FROM reporting.vw_paid_retention_cohorts
        WHERE analytics_build_run_id = %s
        GROUP BY
            analytics_build_run_id,
            acquisition_channel
        ORDER BY acquisition_channel
        """,
        (analytics_build_run_id,),
        config=config,
    )


def build_engagement_monetisation_snapshot(
    *,
    config: DatabaseConfig | None = None,
) -> dict[str, Any]:
    """Load the complete Phase 4 Step 3 reporting snapshot."""

    require_supported_metrics(
        STEP3_SUPPORTED_METRICS,
        config=config,
    )

    context = get_reporting_context(config=config)
    build_id = context.analytics_build_run_id

    return {
        "context": context,
        "monthly_engagement": _monthly_engagement(
            build_id,
            config=config,
        ),
        "feature_engagement": _feature_engagement(
            build_id,
            config=config,
        ),
        "revenue_summary": _revenue_summary(
            build_id,
            config=config,
        ),
        "monthly_revenue": _monthly_revenue(
            build_id,
            config=config,
        ),
        "trial_conversion_summary": _trial_conversion_summary(
            build_id,
            config=config,
        ),
        "retention_summary": _retention_summary(
            build_id,
            config=config,
        ),
        "retention_by_billing_period":
            _retention_by_billing_period(
                build_id,
                config=config,
            ),
        "retention_by_acquisition_channel":
            _retention_by_acquisition_channel(
                build_id,
                config=config,
            ),
    }


def feature_highlight(
    rows: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Return the feature with the most canonical feature-use events."""

    if not rows:
        return None

    return max(
        rows,
        key=lambda row: (
            int(row["feature_use_event_count"]),
            str(row["feature_name"]),
        ),
    )


def _count(value: Any) -> str:
    return f"{int(value):,}"


def _gbp(value: Any) -> str:
    return f"£{float(value):,.2f}"


def _rate(value: Any) -> str:
    if value is None:
        return "n/a"

    return f"{float(value) * 100:.2f}%"


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    if not rows:
        raise ValueError(
            f"Cannot write empty analytical dataset: {path.name}"
        )

    fieldnames = list(rows[0].keys())

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )
        writer.writeheader()
        writer.writerows(rows)


def render_findings_report(
    snapshot: Mapping[str, Any],
) -> str:
    """Render the Step 3 business findings."""

    context: ReportingContext = snapshot["context"]

    monthly = snapshot["monthly_engagement"]
    features = snapshot["feature_engagement"]
    revenue = snapshot["revenue_summary"][0]
    trial = snapshot["trial_conversion_summary"][0]
    retention = snapshot["retention_summary"][0]

    top_feature = feature_highlight(features)

    total_sessions = sum(
        int(row["session_count"])
        for row in monthly
    )

    total_feature_events = sum(
        int(row["feature_use_event_count"])
        for row in monthly
    )

    average_daily_dau = (
        sum(
            float(row["average_registered_dau"])
            for row in monthly
        )
        / len(monthly)
    )

    lines = [
        "# Pulse Phase 4 — Engagement, Monetisation & Retention Findings",
        "",
        "> Pulse and all analysed data are synthetic and exist solely "
        "for portfolio and learning purposes.",
        "",
        "## Analysis context",
        "",
        f"- Ingestion batch: `{context.ingestion_batch_id}`",
        f"- Analytics build: `{context.analytics_build_run_id}`",
        (
            "- Observation cutoff: "
            f"`{context.observation_cutoff_at.isoformat()}`"
        ),
        "- Business source of truth: `reporting.*`",
        "",
        "## Product engagement",
        "",
        (
            f"- Sessions started: "
            f"**{_count(total_sessions)}**"
        ),
        (
            f"- Feature-use events: "
            f"**{_count(total_feature_events)}**"
        ),
        (
            "- Average of monthly average registered DAU: "
            f"**{average_daily_dau:,.0f}**"
        ),
    ]

    if top_feature is not None:
        lines.extend(
            [
                (
                    f"- Highest-volume feature: "
                    f"**{top_feature['feature_name']}** "
                    f"({_count(top_feature['feature_use_event_count'])} "
                    "feature-use events)"
                ),
                (
                    "- Share of all feature-use events: "
                    f"**{_rate(top_feature['feature_use_event_share'])}**"
                ),
            ]
        )

    lines.extend(
        [
            "",
            "The DAU figure above is an average of canonical daily active "
            "user measurements. It is not monthly active users and does "
            "not deduplicate users across calendar days.",
            "",
            "## Billing and successful payment collection",
            "",
            (
                f"- Payment attempts: "
                f"**{_count(revenue['payment_attempt_count'])}**"
            ),
            (
                f"- Successful payments: "
                f"**{_count(revenue['successful_payment_count'])}**"
            ),
            (
                f"- Failed payments: "
                f"**{_count(revenue['failed_payment_count'])}**"
            ),
            (
                f"- Payment failure rate: "
                f"**{_rate(revenue['payment_failure_rate'])}**"
            ),
            (
                "- Successful billed payment collection: "
                f"**{_gbp(revenue['successful_payment_revenue_gbp'])}**"
            ),
            (
                f"- Renewal attempts: "
                f"**{_count(revenue['renewal_attempt_count'])}**"
            ),
            (
                f"- Renewal success rate: "
                f"**{_rate(revenue['renewal_success_rate'])}**"
            ),
            "",
            "`successful_payment_revenue_gbp` is successful billed payment "
            "collection. It is not accounting-recognised revenue, "
            "net revenue or profit.",
            "",
            "## Trial conversion",
            "",
            (
                f"- Trials: **{_count(trial['trial_count'])}**"
            ),
            (
                f"- Mature trials: "
                f"**{_count(trial['mature_trial_count'])}**"
            ),
            (
                f"- Immature trials excluded from denominator: "
                f"**{_count(trial['immature_trial_count'])}**"
            ),
            (
                f"- Mature paid conversions: "
                f"**{_count(trial['mature_trial_paid_conversion_count'])}**"
            ),
            (
                f"- Mature trial → paid: "
                f"**{_rate(trial['trial_to_paid_conversion_rate'])}**"
            ),
            "",
            "## Paid retention",
            "",
            "| Horizon | Eligible | Retained | Rate |",
            "|---|---:|---:|---:|",
            (
                "| D30 | "
                f"{_count(retention['eligible_d30_count'])} | "
                f"{_count(retention['retained_d30_count'])} | "
                f"{_rate(retention['paid_retention_d30'])} |"
            ),
            (
                "| D90 | "
                f"{_count(retention['eligible_d90_count'])} | "
                f"{_count(retention['retained_d90_count'])} | "
                f"{_rate(retention['paid_retention_d90'])} |"
            ),
            (
                "| D180 | "
                f"{_count(retention['eligible_d180_count'])} | "
                f"{_count(retention['retained_d180_count'])} | "
                f"{_rate(retention['paid_retention_d180'])} |"
            ),
            (
                "| D365 | "
                f"{_count(retention['eligible_d365_count'])} | "
                f"{_count(retention['retained_d365_count'])} | "
                f"{_rate(retention['paid_retention_d365'])} |"
            ),
            "",
            "Each retention denominator contains only subscriptions mature "
            "enough to have reached the relevant observation horizon.",
            "",
            "## Decision-oriented interpretation",
            "",
            "1. Acquisition growth should be evaluated together with "
            "downstream product engagement rather than install volume alone.",
            "2. Payment failure and renewal performance identify commercial "
            "friction after customers have already entered the paid lifecycle.",
            "3. The decline from D30 through D365 retention should be "
            "treated as a lifecycle problem requiring cohort and segment "
            "comparison, not as evidence of one specific cause.",
            "4. Acquisition-channel efficiency from Step 2 should be "
            "compared with channel-level paid retention before any "
            "synthetic budget reallocation recommendation.",
            "",
            "## Interpretation boundaries",
            "",
            "- No monthly active user metric is invented.",
            "- No customer LTV is inferred.",
            "- No recognised or net revenue is inferred.",
            "- Retention rates use mature denominators.",
            "- Rates are rolled up from canonical numerator and denominator "
            "components rather than averaged across cohorts.",
            "- No causal claim is made from descriptive segment differences.",
            "",
        ]
    )

    return "\n".join(lines)


def export_engagement_monetisation_snapshot(
    snapshot: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    """Persist reproducible Step 3 analytical evidence."""

    directory = Path(output_dir)
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    datasets = {
        "monthly_engagement":
            snapshot["monthly_engagement"],
        "feature_engagement":
            snapshot["feature_engagement"],
        "revenue_summary":
            snapshot["revenue_summary"],
        "monthly_revenue":
            snapshot["monthly_revenue"],
        "trial_conversion_summary":
            snapshot["trial_conversion_summary"],
        "retention_summary":
            snapshot["retention_summary"],
        "retention_by_billing_period":
            snapshot["retention_by_billing_period"],
        "retention_by_acquisition_channel":
            snapshot["retention_by_acquisition_channel"],
    }

    paths: dict[str, Path] = {}

    for name, rows in datasets.items():
        path = directory / f"{name}.csv"
        _write_csv(path, rows)
        paths[name] = path

    findings_path = (
        directory / "engagement_monetisation_findings.md"
    )

    findings_path.write_text(
        render_findings_report(snapshot),
        encoding="utf-8",
    )

    paths["findings"] = findings_path

    context: ReportingContext = snapshot["context"]

    manifest = {
        "phase": 4,
        "step": 3,
        "analysis": "engagement_monetisation_retention",
        "synthetic_data": True,
        "ingestion_batch_id": context.ingestion_batch_id,
        "analytics_build_run_id":
            context.analytics_build_run_id,
        "observation_cutoff_at":
            context.observation_cutoff_at.isoformat(),
        "metric_contracts": list(STEP3_SUPPORTED_METRICS),
        "source_schema": "reporting",
        "datasets": {
            name: {
                "file": paths[name].name,
                "row_count": len(rows),
            }
            for name, rows in datasets.items()
        },
    }

    manifest_path = directory / "analysis_manifest.json"

    with manifest_path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            manifest,
            handle,
            indent=2,
        )
        handle.write("\n")

    paths["manifest"] = manifest_path

    return paths
