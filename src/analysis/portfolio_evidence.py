"""Portfolio evidence generation for Pulse Phase 4.

Charts are generated as self-contained SVG using the Python standard library.
No KPI is recomputed from raw warehouse data; all values come from validated
Phase 4 outputs whose source of truth is reporting.*.
"""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


class PortfolioEvidenceError(ValueError):
    """Raised when Phase 4 analytical evidence is incomplete or inconsistent."""


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise PortfolioEvidenceError(
            f"Required Phase 4 output is missing: {path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise PortfolioEvidenceError(
            f"Required Phase 4 manifest is missing: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def validate_phase4_lineage(
    outputs_root: str | Path,
) -> dict[str, Any]:
    """Require Steps 2–4 to share identical production lineage."""

    root = Path(outputs_root)

    manifests = {
        step: _read_json(
            root
            / f"step{step}"
            / "analysis_manifest.json"
        )
        for step in (2, 3, 4)
    }

    reference = manifests[2]

    required = (
        "ingestion_batch_id",
        "analytics_build_run_id",
        "observation_cutoff_at",
        "source_schema",
        "synthetic_data",
    )

    for step, manifest in manifests.items():
        for field in required:
            if manifest.get(field) != reference.get(field):
                raise PortfolioEvidenceError(
                    f"Step {step} lineage mismatch for {field}."
                )

        if manifest["source_schema"] != "reporting":
            raise PortfolioEvidenceError(
                f"Step {step} is not reporting-sourced."
            )

        if manifest["synthetic_data"] is not True:
            raise PortfolioEvidenceError(
                f"Step {step} synthetic-data marker is missing."
            )

    if (
        manifests[4].get("experiment_interpretation")
        != "descriptive_only"
    ):
        raise PortfolioEvidenceError(
            "Step 4 experiment contract must remain descriptive_only."
        )

    return {
        "manifests": manifests,
        "ingestion_batch_id":
            int(reference["ingestion_batch_id"]),
        "analytics_build_run_id":
            int(reference["analytics_build_run_id"]),
        "observation_cutoff_at":
            reference["observation_cutoff_at"],
    }


def _escape(value: Any) -> str:
    return html.escape(str(value))


def _svg_document(
    *,
    width: int,
    height: int,
    title: str,
    body: str,
) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        f'<rect width="100%" height="100%" fill="white"/>\n'
        f'<text x="40" y="40" font-family="Arial, sans-serif" '
        f'font-size="22" font-weight="bold">'
        f'{_escape(title)}</text>\n'
        f'{body}\n'
        f'</svg>\n'
    )


def _bar_chart_svg(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    value_suffix: str = "",
    width: int = 900,
    height: int = 500,
) -> str:
    if not labels or len(labels) != len(values):
        raise PortfolioEvidenceError(
            "Bar chart requires aligned non-empty labels and values."
        )

    left = 190
    right = 70
    top = 80
    bottom = 50

    chart_width = width - left - right
    chart_height = height - top - bottom

    max_value = max(values)

    if max_value <= 0:
        max_value = 1.0

    row_height = chart_height / len(labels)
    bar_height = row_height * 0.58

    parts = []

    for index, (label, value) in enumerate(
        zip(labels, values)
    ):
        y = top + index * row_height
        bar_y = y + (row_height - bar_height) / 2
        bar_width = (
            max(0.0, value)
            / max_value
            * chart_width
        )

        parts.append(
            f'<text x="{left - 12}" '
            f'y="{y + row_height / 2 + 5:.1f}" '
            f'text-anchor="end" '
            f'font-family="Arial, sans-serif" '
            f'font-size="14">'
            f'{_escape(label)}</text>'
        )

        parts.append(
            f'<rect x="{left}" '
            f'y="{bar_y:.1f}" '
            f'width="{bar_width:.1f}" '
            f'height="{bar_height:.1f}" '
            f'fill="#4f6f8f"/>'
        )

        parts.append(
            f'<text x="{left + bar_width + 8:.1f}" '
            f'y="{y + row_height / 2 + 5:.1f}" '
            f'font-family="Arial, sans-serif" '
            f'font-size="13">'
            f'{value:.2f}{_escape(value_suffix)}</text>'
        )

    return _svg_document(
        width=width,
        height=height,
        title=title,
        body="\n".join(parts),
    )


def _line_chart_svg(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    title: str,
    value_suffix: str = "%",
    width: int = 900,
    height: int = 500,
) -> str:
    if len(labels) < 2 or len(labels) != len(values):
        raise PortfolioEvidenceError(
            "Line chart requires at least two aligned points."
        )

    left = 80
    right = 60
    top = 80
    bottom = 70

    chart_width = width - left - right
    chart_height = height - top - bottom

    max_value = max(values)

    if max_value <= 0:
        max_value = 1.0

    points = []

    for index, value in enumerate(values):
        x = (
            left
            + index
            * chart_width
            / (len(values) - 1)
        )

        y = (
            top
            + chart_height
            - (value / max_value) * chart_height
        )

        points.append((x, y, value))

    parts = [
        (
            f'<line x1="{left}" y1="{top + chart_height}" '
            f'x2="{left + chart_width}" '
            f'y2="{top + chart_height}" '
            f'stroke="#555"/>'
        ),
        (
            f'<line x1="{left}" y1="{top}" '
            f'x2="{left}" y2="{top + chart_height}" '
            f'stroke="#555"/>'
        ),
        (
            '<polyline fill="none" stroke="#4f6f8f" '
            'stroke-width="3" points="'
            + " ".join(
                f"{x:.1f},{y:.1f}"
                for x, y, _ in points
            )
            + '"/>'
        ),
    ]

    for index, (x, y, value) in enumerate(points):
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" '
            f'r="5" fill="#4f6f8f"/>'
        )

        parts.append(
            f'<text x="{x:.1f}" '
            f'y="{y - 12:.1f}" '
            f'text-anchor="middle" '
            f'font-family="Arial, sans-serif" '
            f'font-size="13">'
            f'{value:.2f}{_escape(value_suffix)}</text>'
        )

        parts.append(
            f'<text x="{x:.1f}" '
            f'y="{top + chart_height + 30}" '
            f'text-anchor="middle" '
            f'font-family="Arial, sans-serif" '
            f'font-size="14">'
            f'{_escape(labels[index])}</text>'
        )

    return _svg_document(
        width=width,
        height=height,
        title=title,
        body="\n".join(parts),
    )


def _grouped_difference_svg(
    rows: Sequence[Mapping[str, str]],
    *,
    width: int = 1000,
    height: int = 520,
) -> str:
    """Show observed trial and paid conversion differences only."""

    if not rows:
        raise PortfolioEvidenceError(
            "Experiment comparison rows are required."
        )

    metrics = (
        (
            "trial_start_conversion_7d_difference_pp",
            "Trial 7d",
        ),
        (
            "paid_conversion_14d_difference_pp",
            "Paid 14d",
        ),
    )

    left = 220
    right = 80
    top = 90
    bottom = 70

    chart_width = width - left - right
    chart_height = height - top - bottom

    all_values = [
        float(row[key])
        for row in rows
        for key, _ in metrics
        if row[key] not in ("", None)
    ]

    max_abs = max(
        abs(value)
        for value in all_values
    )

    if max_abs == 0:
        max_abs = 1.0

    zero_x = left + chart_width / 2
    half_width = chart_width / 2

    group_height = chart_height / len(rows)
    bar_height = group_height * 0.22

    parts = [
        (
            f'<line x1="{zero_x:.1f}" y1="{top}" '
            f'x2="{zero_x:.1f}" '
            f'y2="{top + chart_height}" '
            f'stroke="#444" stroke-width="1.5"/>'
        )
    ]

    for row_index, row in enumerate(rows):
        group_top = top + row_index * group_height

        label = str(row["experiment_id"])

        parts.append(
            f'<text x="{left - 15}" '
            f'y="{group_top + group_height / 2:.1f}" '
            f'text-anchor="end" '
            f'font-family="Arial, sans-serif" '
            f'font-size="13">'
            f'{_escape(label)}</text>'
        )

        for metric_index, (key, short_name) in enumerate(
            metrics
        ):
            value = float(row[key])

            length = (
                abs(value)
                / max_abs
                * (half_width - 30)
            )

            y = (
                group_top
                + group_height * 0.25
                + metric_index * group_height * 0.32
            )

            x = zero_x if value >= 0 else zero_x - length

            fill = (
                "#4f6f8f"
                if metric_index == 0
                else "#8a6f4d"
            )

            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" '
                f'width="{length:.1f}" '
                f'height="{bar_height:.1f}" '
                f'fill="{fill}"/>'
            )

            value_x = (
                zero_x + length + 7
                if value >= 0
                else zero_x - length - 7
            )

            anchor = (
                "start"
                if value >= 0
                else "end"
            )

            parts.append(
                f'<text x="{value_x:.1f}" '
                f'y="{y + bar_height - 2:.1f}" '
                f'text-anchor="{anchor}" '
                f'font-family="Arial, sans-serif" '
                f'font-size="12">'
                f'{value:+.2f} pp</text>'
            )

    parts.extend(
        [
            (
                f'<text x="{left + 10}" '
                f'y="{height - 25}" '
                f'font-family="Arial, sans-serif" '
                f'font-size="13">'
                f'Trial 7d</text>'
            ),
            (
                f'<rect x="{left - 15}" '
                f'y="{height - 38}" '
                f'width="18" height="12" '
                f'fill="#4f6f8f"/>'
            ),
            (
                f'<text x="{left + 120}" '
                f'y="{height - 25}" '
                f'font-family="Arial, sans-serif" '
                f'font-size="13">'
                f'Paid 14d</text>'
            ),
            (
                f'<rect x="{left + 95}" '
                f'y="{height - 38}" '
                f'width="18" height="12" '
                f'fill="#8a6f4d"/>'
            ),
        ]
    )

    return _svg_document(
        width=width,
        height=height,
        title=(
            "Experiment observed differences "
            "(descriptive only)"
        ),
        body="\n".join(parts),
    )


def build_portfolio_evidence(
    outputs_root: str | Path,
    output_dir: str | Path,
) -> dict[str, Path]:
    """Build final Phase 4 portfolio evidence from validated outputs."""

    root = Path(outputs_root)
    destination = Path(output_dir)

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    lineage = validate_phase4_lineage(root)

    channels = _read_csv(
        root
        / "step2"
        / "acquisition_channel_performance.csv"
    )

    retention = _read_csv(
        root
        / "step3"
        / "retention_summary.csv"
    )[0]

    features = _read_csv(
        root
        / "step3"
        / "feature_engagement.csv"
    )

    comparisons = _read_csv(
        root
        / "step4"
        / "experiment_descriptive_comparisons.csv"
    )

    channel_svg = _bar_chart_svg(
        [
            row["acquisition_channel"]
            for row in channels
        ],
        [
            float(row["install_to_signup_rate"]) * 100.0
            for row in channels
        ],
        title="Install-to-signup rate by acquisition channel",
        value_suffix="%",
    )

    channel_path = (
        destination
        / "acquisition_channel_performance.svg"
    )

    channel_path.write_text(
        channel_svg,
        encoding="utf-8",
    )

    retention_labels = [
        "D30",
        "D90",
        "D180",
        "D365",
    ]

    retention_values = [
        float(retention["paid_retention_d30"]) * 100.0,
        float(retention["paid_retention_d90"]) * 100.0,
        float(retention["paid_retention_d180"]) * 100.0,
        float(retention["paid_retention_d365"]) * 100.0,
    ]

    retention_path = (
        destination / "paid_retention_curve.svg"
    )

    retention_path.write_text(
        _line_chart_svg(
            retention_labels,
            retention_values,
            title="Maturity-controlled paid retention",
        ),
        encoding="utf-8",
    )

    feature_path = (
        destination / "feature_engagement.svg"
    )

    feature_path.write_text(
        _bar_chart_svg(
            [
                row["feature_name"]
                for row in features
            ],
            [
                float(row["feature_use_event_share"]) * 100.0
                for row in features
            ],
            title="Share of feature-use events",
            value_suffix="%",
        ),
        encoding="utf-8",
    )

    experiment_path = (
        destination
        / "experiment_observed_differences.svg"
    )

    experiment_path.write_text(
        _grouped_difference_svg(
            comparisons
        ),
        encoding="utf-8",
    )

    business_synthesis = (
        root
        / "step4"
        / "business_synthesis.md"
    ).read_text(
        encoding="utf-8"
    )

    summary_lines = [
        "# Pulse Phase 4 — Portfolio Analysis Summary",
        "",
        "> Pulse and all data in this project are synthetic and created "
        "solely for portfolio and learning purposes.",
        "",
        "## What Phase 4 demonstrates",
        "",
        "Phase 4 converts the validated PostgreSQL reporting semantic "
        "layer into reproducible business analysis while preserving "
        "metric contracts, warehouse lineage, cohort maturity and "
        "read-only consumer boundaries.",
        "",
        "The analysis covers acquisition, onboarding, engagement, "
        "subscription conversion, successful billed payment collection, "
        "maturity-controlled paid retention and descriptive experiment "
        "outcomes.",
        "",
        "## Portfolio evidence",
        "",
        "- `acquisition_channel_performance.svg` — acquisition quality "
        "comparison using canonical install-to-signup rates.",
        "- `paid_retention_curve.svg` — maturity-controlled D30/D90/D180/"
        "D365 paid retention.",
        "- `feature_engagement.svg` — distribution of canonical feature-use "
        "events.",
        "- `experiment_observed_differences.svg` — observed trial and paid "
        "conversion differences, explicitly descriptive only.",
        "",
        "## Key business synthesis",
        "",
        business_synthesis,
        "",
    ]

    summary_path = (
        destination / "phase4_portfolio_summary.md"
    )

    summary_path.write_text(
        "\n".join(summary_lines),
        encoding="utf-8",
    )

    manifest = {
        "phase": 4,
        "status": "validation_pending",
        "synthetic_data": True,
        "source_schema": "reporting",
        "ingestion_batch_id":
            lineage["ingestion_batch_id"],
        "analytics_build_run_id":
            lineage["analytics_build_run_id"],
        "observation_cutoff_at":
            lineage["observation_cutoff_at"],
        "experiment_interpretation":
            "descriptive_only",
        "phase4_steps": {
            "1": "analysis_foundation",
            "2": "growth_funnel_acquisition",
            "3": "engagement_monetisation_retention",
            "4": "descriptive_experiments_business_synthesis",
            "5": "portfolio_evidence_validation_closure",
        },
        "portfolio_files": [
            channel_path.name,
            retention_path.name,
            feature_path.name,
            experiment_path.name,
            summary_path.name,
        ],
    }

    manifest_path = (
        destination / "phase4_manifest.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "acquisition_chart": channel_path,
        "retention_chart": retention_path,
        "feature_chart": feature_path,
        "experiment_chart": experiment_path,
        "summary": summary_path,
        "manifest": manifest_path,
    }
