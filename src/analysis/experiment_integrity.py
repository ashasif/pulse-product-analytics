"""Randomisation-integrity controls for Pulse Phase 5 experimentation.

The functions in this module validate the randomized assignment structure
before outcome-level statistical inference is permitted.

Sample-ratio mismatch (SRM) testing uses the experiment's configured
allocation rather than assuming a universal 50/50 split.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import erfc, isclose, sqrt
from typing import Mapping, Sequence

from src.analysis.experiment_inference import (
    InferenceContractError,
    validate_variant_summary_rows,
)


DEFAULT_SRM_ALPHA = 0.001


@dataclass(frozen=True, slots=True)
class SampleRatioResult:
    """Result of a two-arm sample-ratio-mismatch diagnostic."""

    experiment_id: str
    control_count: int
    treatment_count: int
    total_count: int
    control_allocation: float
    treatment_allocation: float
    expected_control_count: float
    expected_treatment_count: float
    chi_square_statistic: float
    p_value: float
    alpha: float
    mismatch_detected: bool


def _validate_count(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InferenceContractError(f"{name} must be an integer")

    if value < 0:
        raise InferenceContractError(f"{name} cannot be negative")

    return value


def _validate_probability(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InferenceContractError(f"{name} must be numeric")

    value = float(value)

    if not 0.0 < value < 1.0:
        raise InferenceContractError(
            f"{name} must be strictly between 0 and 1"
        )

    return value


def calculate_sample_ratio_mismatch(
    *,
    experiment_id: str,
    control_count: int,
    treatment_count: int,
    control_allocation: float,
    treatment_allocation: float,
    alpha: float = DEFAULT_SRM_ALPHA,
) -> SampleRatioResult:
    """Evaluate two-arm sample-ratio mismatch against configured allocation.

    Pearson's chi-square statistic is used with one degree of freedom.

    For df=1, the survival probability can be evaluated exactly from the
    complementary error function:

        p = erfc(sqrt(chi_square / 2))

    Pulse experiment populations are large enough for this allocation
    diagnostic to be appropriate.
    """

    if not experiment_id or not experiment_id.strip():
        raise InferenceContractError("experiment_id must be non-empty")

    control_count = _validate_count(control_count, "control_count")
    treatment_count = _validate_count(treatment_count, "treatment_count")

    total_count = control_count + treatment_count

    if total_count <= 0:
        raise InferenceContractError(
            "Sample-ratio analysis requires at least one assignment"
        )

    control_allocation = _validate_probability(
        control_allocation,
        "control_allocation",
    )
    treatment_allocation = _validate_probability(
        treatment_allocation,
        "treatment_allocation",
    )

    if not isclose(
        control_allocation + treatment_allocation,
        1.0,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise InferenceContractError(
            "Control and treatment allocations must sum to 1"
        )

    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
        raise InferenceContractError("SRM alpha must be numeric")

    alpha = float(alpha)

    if not 0.0 < alpha < 1.0:
        raise InferenceContractError(
            "SRM alpha must be strictly between 0 and 1"
        )

    expected_control = total_count * control_allocation
    expected_treatment = total_count * treatment_allocation

    chi_square = (
        ((control_count - expected_control) ** 2) / expected_control
        + ((treatment_count - expected_treatment) ** 2)
        / expected_treatment
    )

    p_value = erfc(sqrt(chi_square / 2.0))

    return SampleRatioResult(
        experiment_id=experiment_id,
        control_count=control_count,
        treatment_count=treatment_count,
        total_count=total_count,
        control_allocation=control_allocation,
        treatment_allocation=treatment_allocation,
        expected_control_count=expected_control,
        expected_treatment_count=expected_treatment,
        chi_square_statistic=chi_square,
        p_value=p_value,
        alpha=alpha,
        mismatch_detected=p_value < alpha,
    )


def build_sample_ratio_result(
    rows: Sequence[Mapping[str, object]],
    *,
    count_field: str = "assigned_mature_count",
    alpha: float = DEFAULT_SRM_ALPHA,
) -> SampleRatioResult:
    """Build an SRM result from control/treatment variant summary rows."""

    validate_variant_summary_rows(rows)

    experiment_ids: set[str] = set()

    for row in rows:
        if "experiment_id" not in row:
            raise InferenceContractError(
                "Variant row is missing experiment_id"
            )

        experiment_id = str(row["experiment_id"]).strip()

        if not experiment_id:
            raise InferenceContractError(
                "experiment_id cannot be blank"
            )

        experiment_ids.add(experiment_id)

    if len(experiment_ids) != 1:
        raise InferenceContractError(
            "Variant rows must belong to one experiment"
        )

    by_variant = {
        str(row["variant"]).strip().lower(): row
        for row in rows
    }

    for variant in ("control", "treatment"):
        row = by_variant[variant]

        if count_field not in row:
            raise InferenceContractError(
                f"Variant row is missing {count_field}"
            )

        if "allocation_probability" not in row:
            raise InferenceContractError(
                "Variant row is missing allocation_probability"
            )

    control = by_variant["control"]
    treatment = by_variant["treatment"]

    return calculate_sample_ratio_mismatch(
        experiment_id=next(iter(experiment_ids)),
        control_count=_validate_count(
            control[count_field],
            f"control.{count_field}",
        ),
        treatment_count=_validate_count(
            treatment[count_field],
            f"treatment.{count_field}",
        ),
        control_allocation=_validate_probability(
            control["allocation_probability"],
            "control.allocation_probability",
        ),
        treatment_allocation=_validate_probability(
            treatment["allocation_probability"],
            "treatment.allocation_probability",
        ),
        alpha=alpha,
    )
