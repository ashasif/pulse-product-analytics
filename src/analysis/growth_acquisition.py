"""Growth, funnel and acquisition analysis for Pulse Phase 4.

All business measures originate from the validated reporting semantic layer.
This module performs aggregation, comparison and ranking only; it does not
redefine warehouse KPI contracts.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.analysis.reporting_client import (
    ReportingContext,
    fetch_reporting_rows,
    get_reporting_context,
    require_supported_metrics,
)
from src.ingestion.database import DatabaseConfig


STEP2_SUPPORTED_METRICS = (
    "installation_count",
    "signup_count",
    "install_to_signup_rate",
    "onboarding_start_rate",
    "onboarding_completion_rate",
    "trial_start_count",
    "paid_subscription_start_count",
    "marketing_spend_gbp",
    "marketing_ctr",
    "marketing_cpc_gbp",
    "cost_per_install_gbp",
)


def _monthly_growth(
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
            SUM(installation_count)::bigint AS installation_count,
            SUM(signup_count)::bigint AS signup_count,
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


def _funnel_summary(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        WITH installation_funnel AS (
            SELECT
                MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
                analytics_build_run_id,
                SUM(installation_count)::bigint AS installation_count,
                SUM(installations_with_signup)::bigint
                    AS installations_with_signup
            FROM reporting.vw_installation_cohort_funnel
            WHERE analytics_build_run_id = %s
            GROUP BY analytics_build_run_id
        ),
        signup_funnel AS (
            SELECT
                analytics_build_run_id,
                SUM(registered_user_count)::bigint
                    AS registered_user_count,
                SUM(onboarding_started_user_count)::bigint
                    AS onboarding_started_user_count,
                SUM(onboarding_completed_user_count)::bigint
                    AS onboarding_completed_user_count
            FROM reporting.vw_signup_cohort_funnel
            WHERE analytics_build_run_id = %s
            GROUP BY analytics_build_run_id
        )
        SELECT
            i.ingestion_batch_id,
            i.analytics_build_run_id,
            i.installation_count,
            i.installations_with_signup,
            CASE
                WHEN i.installation_count = 0 THEN NULL
                ELSE i.installations_with_signup::numeric
                     / i.installation_count
            END AS install_to_signup_rate,
            s.registered_user_count,
            s.onboarding_started_user_count,
            s.onboarding_completed_user_count,
            CASE
                WHEN s.registered_user_count = 0 THEN NULL
                ELSE s.onboarding_started_user_count::numeric
                     / s.registered_user_count
            END AS onboarding_start_rate,
            CASE
                WHEN s.registered_user_count = 0 THEN NULL
                ELSE s.onboarding_completed_user_count::numeric
                     / s.registered_user_count
            END AS onboarding_completion_rate
        FROM installation_funnel i
        JOIN signup_funnel s
          ON s.analytics_build_run_id = i.analytics_build_run_id
        """,
        (
            analytics_build_run_id,
            analytics_build_run_id,
        ),
        config=config,
    )


def _acquisition_channel_performance(
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
            COUNT(*)::bigint AS marketing_period_count,
            SUM(marketing_spend_gbp)::numeric
                AS marketing_spend_gbp,
            SUM(impressions)::bigint AS impressions,
            SUM(clicks)::bigint AS clicks,
            SUM(installation_count)::bigint AS installation_count,
            SUM(installations_with_signup)::bigint
                AS installations_with_signup,
            CASE
                WHEN SUM(impressions) = 0 THEN NULL
                ELSE SUM(clicks)::numeric / SUM(impressions)
            END AS click_through_rate,
            CASE
                WHEN SUM(clicks) = 0 THEN NULL
                ELSE SUM(marketing_spend_gbp)::numeric / SUM(clicks)
            END AS cost_per_click_gbp,
            CASE
                WHEN SUM(installation_count) = 0 THEN NULL
                ELSE SUM(marketing_spend_gbp)::numeric
                     / SUM(installation_count)
            END AS cost_per_install_gbp,
            CASE
                WHEN SUM(installation_count) = 0 THEN NULL
                ELSE SUM(installations_with_signup)::numeric
                     / SUM(installation_count)
            END AS install_to_signup_rate
        FROM reporting.vw_weekly_acquisition_performance
        WHERE analytics_build_run_id = %s
        GROUP BY
            analytics_build_run_id,
            acquisition_channel
        ORDER BY acquisition_channel
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _platform_funnel_performance(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            platform,
            SUM(installation_count)::bigint AS installation_count,
            SUM(installations_with_signup)::bigint
                AS installations_with_signup,
            CASE
                WHEN SUM(installation_count) = 0 THEN NULL
                ELSE SUM(installations_with_signup)::numeric
                     / SUM(installation_count)
            END AS install_to_signup_rate
        FROM reporting.vw_installation_cohort_funnel
        WHERE analytics_build_run_id = %s
        GROUP BY
            analytics_build_run_id,
            platform
        ORDER BY platform
        """,
        (analytics_build_run_id,),
        config=config,
    )


def _country_funnel_performance(
    analytics_build_run_id: int,
    *,
    config: DatabaseConfig | None = None,
) -> list[dict[str, Any]]:
    return fetch_reporting_rows(
        """
        SELECT
            MIN(ingestion_batch_id)::bigint AS ingestion_batch_id,
            analytics_build_run_id,
            country_code,
            SUM(installation_count)::bigint AS installation_count,
            SUM(installations_with_signup)::bigint
                AS installations_with_signup,
            CASE
                WHEN SUM(installation_count) = 0 THEN NULL
                ELSE SUM(installations_with_signup)::numeric
                     / SUM(installation_count)
            END AS install_to_signup_rate
        FROM reporting.vw_installation_cohort_funnel
        WHERE analytics_build_run_id = %s
        GROUP BY
            analytics_build_run_id,
            country_code
        ORDER BY country_code
        """,
        (analytics_build_run_id,),
        config=config,
    )


def build_growth_acquisition_snapshot(
    *,
    config: DatabaseConfig | None = None,
) -> dict[str, Any]:
    """Load the complete Step 2 reporting snapshot."""

    require_supported_metrics(
        STEP2_SUPPORTED_METRICS,
        config=config,
    )

    context = get_reporting_context(config=config)
    build_id = context.analytics_build_run_id

    return {
        "context": context,
        "monthly_growth": _monthly_growth(
            build_id,
            config=config,
        ),
        "funnel_summary": _funnel_summary(
            build_id,
            config=config,
        ),
        "acquisition_channel_performance":
            _acquisition_channel_performance(
                build_id,
                config=config,
            ),
        "platform_funnel_performance":
            _platform_funnel_performance(
                build_id,
                config=config,
            ),
        "country_funnel_performance":
            _country_funnel_performance(
                build_id,
                config=config,
            ),
    }


def _pct_change(
    previous: int | Decimal,
    current: int | Decimal,
) -> float | None:
    previous_value = float(previous)
    current_value = float(current)

    if previous_value == 0:
        return None

    return (
        (current_value - previous_value)
        / previous_value
        * 100.0
    )


def compare_periods(
    monthly_rows: Sequence[Mapping[str, Any]],
    *,
    baseline_year: int = 2024,
    comparison_year: int = 2026,
    months: Sequence[int] = (1, 2, 3, 4, 5, 6),
) -> dict[str, Any]:
    """Compare aligned calendar months using canonical monthly counts."""

    fields = (
        "installation_count",
        "signup_count",
        "trial_start_count",
        "paid_subscription_start_count",
    )

    month_set = set(months)

    def totals_for(year: int) -> dict[str, int]:
        selected = [
            row
            for row in monthly_rows
            if row["month_start"].year == year
            and row["month_start"].month in month_set
        ]

        return {
            field: sum(
                int(row[field])
                for row in selected
            )
            for field in fields
        }

    baseline = totals_for(baseline_year)
    comparison = totals_for(comparison_year)

    changes = {
        field: _pct_change(
            baseline[field],
            comparison[field],
        )
        for field in fields
    }

    return {
        "baseline_year": baseline_year,
        "comparison_year": comparison_year,
        "months": tuple(months),
        "baseline": baseline,
        "comparison": comparison,
        "percent_change": changes,
    }


def channel_highlights(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any] | None]:
    """Select descriptive channel leaders from canonical measures."""

    if not rows:
        return {
            "highest_install_volume": None,
            "highest_signup_conversion": None,
            "lowest_cost_per_install": None,
            "highest_marketing_spend": None,
        }

    highest_volume = max(
        rows,
        key=lambda row: (
            int(row["installation_count"]),
            str(row["acquisition_channel"]),
        ),
    )

    conversion_rows = [
        row
        for row in rows
        if row["install_to_signup_rate"] is not None
    ]

    cpi_rows = [
        row
        for row in rows
        if row["cost_per_install_gbp"] is not None
        and float(row["cost_per_install_gbp"]) > 0
    ]

    highest_spend = max(
        rows,
        key=lambda row: (
            float(row["marketing_spend_gbp"]),
            str(row["acquisition_channel"]),
        ),
    )

    return {
        "highest_install_volume": highest_volume,
        "highest_signup_conversion": (
            max(
                conversion_rows,
                key=lambda row: (
                    float(row["install_to_signup_rate"]),
                    str(row["acquisition_channel"]),
                ),
            )
            if conversion_rows
            else None
        ),
        "lowest_cost_per_install": (
            min(
                cpi_rows,
                key=lambda row: (
                    float(row["cost_per_install_gbp"]),
                    str(row["acquisition_channel"]),
                ),
            )
            if cpi_rows
            else None
        ),
        "highest_marketing_spend": highest_spend,
    }


def _format_count(value: Any) -> str:
    return f"{int(value):,}"


def _format_gbp(value: Any) -> str:
    return f"£{float(value):,.2f}"


def _format_rate(value: Any) -> str:
    if value is None:
        return "n/a"

    return f"{float(value) * 100:.2f}%"


def _format_change(value: float | None) -> str:
    if value is None:
        return "n/a"

    return f"{value:+.2f}%"


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
    """Render the Step 2 decision-oriented business summary."""

    context: ReportingContext = snapshot["context"]
    monthly_rows = snapshot["monthly_growth"]
    funnel = snapshot["funnel_summary"][0]
    channels = snapshot["acquisition_channel_performance"]

    comparison = compare_periods(monthly_rows)
    highlights = channel_highlights(channels)

    baseline = comparison["baseline"]
    current = comparison["comparison"]
    changes = comparison["percent_change"]

    volume = highlights["highest_install_volume"]
    conversion = highlights["highest_signup_conversion"]
    cpi = highlights["lowest_cost_per_install"]
    spend = highlights["highest_marketing_spend"]

    lines = [
        "# Pulse Phase 4 — Growth, Funnel & Acquisition Findings",
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
        "## Growth: H1 2024 vs H1 2026",
        "",
        "| Measure | H1 2024 | H1 2026 | Change |",
        "|---|---:|---:|---:|",
        (
            "| Installations | "
            f"{_format_count(baseline['installation_count'])} | "
            f"{_format_count(current['installation_count'])} | "
            f"{_format_change(changes['installation_count'])} |"
        ),
        (
            "| Signups | "
            f"{_format_count(baseline['signup_count'])} | "
            f"{_format_count(current['signup_count'])} | "
            f"{_format_change(changes['signup_count'])} |"
        ),
        (
            "| Trial starts | "
            f"{_format_count(baseline['trial_start_count'])} | "
            f"{_format_count(current['trial_start_count'])} | "
            f"{_format_change(changes['trial_start_count'])} |"
        ),
        (
            "| Paid subscription starts | "
            f"{_format_count(baseline['paid_subscription_start_count'])} | "
            f"{_format_count(current['paid_subscription_start_count'])} | "
            f"{_format_change(changes['paid_subscription_start_count'])} |"
        ),
        "",
        "The comparison uses the same January-to-June calendar window "
        "in each year so the incomplete 2026 calendar year is not "
        "compared with a full prior year.",
        "",
        "## Core acquisition and onboarding funnel",
        "",
        (
            f"- Installations: "
            f"**{_format_count(funnel['installation_count'])}**"
        ),
        (
            f"- Installations with signup: "
            f"**{_format_count(funnel['installations_with_signup'])}**"
        ),
        (
            f"- Install → signup: "
            f"**{_format_rate(funnel['install_to_signup_rate'])}**"
        ),
        (
            f"- Registered users: "
            f"**{_format_count(funnel['registered_user_count'])}**"
        ),
        (
            f"- Onboarding started: "
            f"**{_format_count(funnel['onboarding_started_user_count'])}**"
        ),
        (
            f"- Onboarding start rate: "
            f"**{_format_rate(funnel['onboarding_start_rate'])}**"
        ),
        (
            f"- Onboarding completed: "
            f"**{_format_count(funnel['onboarding_completed_user_count'])}**"
        ),
        (
            f"- Onboarding completion rate: "
            f"**{_format_rate(funnel['onboarding_completion_rate'])}**"
        ),
        "",
        "## Acquisition channel performance",
        "",
        "| Channel | Spend | Installs | Install → signup | CPI | CTR |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for row in channels:
        lines.append(
            "| "
            f"{row['acquisition_channel']} | "
            f"{_format_gbp(row['marketing_spend_gbp'])} | "
            f"{_format_count(row['installation_count'])} | "
            f"{_format_rate(row['install_to_signup_rate'])} | "
            f"{_format_gbp(row['cost_per_install_gbp'])} | "
            f"{_format_rate(row['click_through_rate'])} |"
        )

    lines.extend(
        [
            "",
            "## Decision-oriented observations",
            "",
        ]
    )

    if volume is not None:
        lines.append(
            "1. **Acquisition scale:** "
            f"`{volume['acquisition_channel']}` generated the highest "
            "installation volume in the approved snapshot "
            f"({_format_count(volume['installation_count'])} installs)."
        )

    if conversion is not None:
        lines.append(
            "2. **Signup efficiency:** "
            f"`{conversion['acquisition_channel']}` had the highest "
            "aggregated install-to-signup rate "
            f"({_format_rate(conversion['install_to_signup_rate'])})."
        )

    if cpi is not None:
        lines.append(
            "3. **Acquisition cost efficiency:** "
            f"`{cpi['acquisition_channel']}` had the lowest aggregated "
            "cost per install among channels with a positive measured CPI "
            f"({_format_gbp(cpi['cost_per_install_gbp'])})."
        )

    if spend is not None:
        lines.append(
            "4. **Spend concentration:** "
            f"`{spend['acquisition_channel']}` received the highest "
            "total marketing spend "
            f"({_format_gbp(spend['marketing_spend_gbp'])})."
        )

    lines.extend(
        [
            "",
            "These are descriptive relationships in synthetic data. "
            "They do not establish that acquisition channel caused "
            "downstream behaviour.",
            "",
            "## What should be investigated next?",
            "",
            "- Compare acquisition efficiency with downstream trial and "
            "paid retention before recommending budget changes.",
            "- Investigate whether platform differences explain part of "
            "the observed install-to-signup variation.",
            "- Examine engagement and feature-use patterns after signup "
            "to determine where acquired users create product value.",
            "- Preserve cohort maturity rules when moving into "
            "subscription conversion and retention analysis.",
            "",
            "## Interpretation boundaries",
            "",
            "- Cost per install is channel-level, not campaign-attributed CAC.",
            "- Successful payment collection is not analysed in this step.",
            "- No LTV, recognised revenue or net revenue is inferred.",
            "- No statistical or causal claims are made.",
            "",
        ]
    )

    return "\n".join(lines)


def export_growth_acquisition_snapshot(
    snapshot: Mapping[str, Any],
    output_dir: str | Path,
) -> dict[str, Path]:
    """Persist reproducible Step 2 analytical evidence."""

    directory = Path(output_dir)
    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    datasets = {
        "monthly_growth":
            snapshot["monthly_growth"],
        "funnel_summary":
            snapshot["funnel_summary"],
        "acquisition_channel_performance":
            snapshot["acquisition_channel_performance"],
        "platform_funnel_performance":
            snapshot["platform_funnel_performance"],
        "country_funnel_performance":
            snapshot["country_funnel_performance"],
    }

    paths: dict[str, Path] = {}

    for name, rows in datasets.items():
        path = directory / f"{name}.csv"
        _write_csv(path, rows)
        paths[name] = path

    report_path = directory / "growth_acquisition_findings.md"
    report_path.write_text(
        render_findings_report(snapshot),
        encoding="utf-8",
    )
    paths["findings"] = report_path

    context: ReportingContext = snapshot["context"]

    manifest = {
        "phase": 4,
        "step": 2,
        "analysis": "growth_funnel_acquisition",
        "synthetic_data": True,
        "ingestion_batch_id": context.ingestion_batch_id,
        "analytics_build_run_id":
            context.analytics_build_run_id,
        "observation_cutoff_at":
            context.observation_cutoff_at.isoformat(),
        "metric_contracts": list(STEP2_SUPPORTED_METRICS),
        "source_schema": "reporting",
        "datasets": {
            name: {
                "file": path.name,
                "row_count": len(datasets[name]),
            }
            for name, path in paths.items()
            if name in datasets
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
