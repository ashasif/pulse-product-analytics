"""Resampling inference for continuous experiment outcomes.

Designed for Phase 5 randomized-experiment outcomes whose business estimand
is a difference in arithmetic means but whose user-level distribution is
materially skewed, zero-inflated or otherwise poorly represented by a simple
Gaussian model.

No third-party numerical dependency is required.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from random import Random
from typing import Iterable

from src.analysis.experiment_inference import InferenceContractError


DEFAULT_BOOTSTRAP_REPLICATES = 10_000
DEFAULT_PERMUTATION_REPLICATES = 10_000
DEFAULT_RESAMPLING_SEED = 5_202_026


@dataclass(frozen=True, slots=True)
class MeanDifferenceInferenceResult:
    """Inference result for treatment-minus-control difference in means."""

    metric_name: str

    control_count: int
    treatment_count: int

    control_mean: float
    treatment_mean: float

    absolute_effect: float
    relative_effect: float | None

    confidence_level: float
    confidence_interval_low: float
    confidence_interval_high: float

    bootstrap_replicates: int
    bootstrap_seed: int

    permutation_replicates: int
    permutation_seed: int

    permutation_p_value: float
    alpha: float
    statistically_detectable: bool


def _validated_numeric_values(
    values: Iterable[object],
    *,
    group_name: str,
) -> list[float]:
    """Validate and convert one experiment group to finite floats."""

    converted: list[float] = []

    for value in values:
        if isinstance(value, bool):
            raise InferenceContractError(
                f"{group_name} values must be numeric, not boolean"
            )

        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise InferenceContractError(
                f"{group_name} contains a non-numeric value"
            ) from exc

        if not isfinite(numeric):
            raise InferenceContractError(
                f"{group_name} values must be finite"
            )

        converted.append(numeric)

    if not converted:
        raise InferenceContractError(
            f"{group_name} must contain at least one observation"
        )

    return converted


def _validate_alpha(alpha: object) -> float:
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
        raise InferenceContractError("alpha must be numeric")

    alpha = float(alpha)

    if not 0.0 < alpha < 1.0:
        raise InferenceContractError(
            "alpha must be strictly between 0 and 1"
        )

    return alpha


def _validate_replicates(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InferenceContractError(
            f"{name} must be an integer"
        )

    if value < 100:
        raise InferenceContractError(
            f"{name} must be at least 100"
        )

    return value


def _percentile(
    sorted_values: list[float],
    probability: float,
) -> float:
    """Linear-interpolated percentile for an already-sorted sequence."""

    if not sorted_values:
        raise InferenceContractError(
            "Cannot calculate a percentile from an empty sequence"
        )

    if not 0.0 <= probability <= 1.0:
        raise InferenceContractError(
            "Percentile probability must be between 0 and 1"
        )

    if len(sorted_values) == 1:
        return sorted_values[0]

    position = probability * (len(sorted_values) - 1)

    lower_index = int(position)
    upper_index = min(
        lower_index + 1,
        len(sorted_values) - 1,
    )

    fraction = position - lower_index

    lower = sorted_values[lower_index]
    upper = sorted_values[upper_index]

    return lower + fraction * (upper - lower)


def _bootstrap_mean_difference_interval(
    control_values: list[float],
    treatment_values: list[float],
    *,
    alpha: float,
    replicates: int,
    seed: int,
) -> tuple[float, float]:
    """Percentile bootstrap CI for treatment minus control mean."""

    rng = Random(seed)

    control_n = len(control_values)
    treatment_n = len(treatment_values)

    differences: list[float] = []

    for _ in range(replicates):
        control_mean = (
            sum(
                rng.choices(
                    control_values,
                    k=control_n,
                )
            )
            / control_n
        )

        treatment_mean = (
            sum(
                rng.choices(
                    treatment_values,
                    k=treatment_n,
                )
            )
            / treatment_n
        )

        differences.append(
            treatment_mean - control_mean
        )

    differences.sort()

    return (
        _percentile(
            differences,
            alpha / 2.0,
        ),
        _percentile(
            differences,
            1.0 - alpha / 2.0,
        ),
    )


def _permutation_mean_difference_p_value(
    control_values: list[float],
    treatment_values: list[float],
    *,
    replicates: int,
    seed: int,
) -> float:
    """Monte Carlo randomization p-value for difference in means."""

    rng = Random(seed)

    control_n = len(control_values)
    treatment_n = len(treatment_values)

    control_mean = sum(control_values) / control_n
    treatment_mean = sum(treatment_values) / treatment_n

    observed_difference = treatment_mean - control_mean
    observed_absolute = abs(observed_difference)

    pooled = control_values + treatment_values
    pooled_sum = sum(pooled)

    extreme_count = 0
    tolerance = 1e-15

    for _ in range(replicates):
        permuted_control = rng.sample(
            pooled,
            control_n,
        )

        control_sum = sum(permuted_control)
        treatment_sum = pooled_sum - control_sum

        permuted_difference = (
            treatment_sum / treatment_n
            - control_sum / control_n
        )

        if (
            abs(permuted_difference)
            >= observed_absolute - tolerance
        ):
            extreme_count += 1

    return (
        extreme_count + 1
    ) / (
        replicates + 1
    )


def infer_mean_difference_resampling(
    *,
    metric_name: str,
    control_values: Iterable[object],
    treatment_values: Iterable[object],
    alpha: float = 0.05,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    permutation_replicates: int = DEFAULT_PERMUTATION_REPLICATES,
    seed: int = DEFAULT_RESAMPLING_SEED,
) -> MeanDifferenceInferenceResult:
    """Infer treatment-minus-control mean difference using resampling."""

    if not metric_name or not metric_name.strip():
        raise InferenceContractError(
            "metric_name must be non-empty"
        )

    alpha = _validate_alpha(alpha)

    bootstrap_replicates = _validate_replicates(
        bootstrap_replicates,
        "bootstrap_replicates",
    )

    permutation_replicates = _validate_replicates(
        permutation_replicates,
        "permutation_replicates",
    )

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise InferenceContractError(
            "seed must be an integer"
        )

    control = _validated_numeric_values(
        control_values,
        group_name="control",
    )

    treatment = _validated_numeric_values(
        treatment_values,
        group_name="treatment",
    )

    control_mean = sum(control) / len(control)
    treatment_mean = sum(treatment) / len(treatment)

    absolute_effect = treatment_mean - control_mean

    if control_mean == 0.0:
        relative_effect = None
    else:
        relative_effect = (
            treatment_mean / control_mean - 1.0
        )

    bootstrap_seed = seed
    permutation_seed = seed + 1

    ci_low, ci_high = _bootstrap_mean_difference_interval(
        control,
        treatment,
        alpha=alpha,
        replicates=bootstrap_replicates,
        seed=bootstrap_seed,
    )

    p_value = _permutation_mean_difference_p_value(
        control,
        treatment,
        replicates=permutation_replicates,
        seed=permutation_seed,
    )

    return MeanDifferenceInferenceResult(
        metric_name=metric_name,
        control_count=len(control),
        treatment_count=len(treatment),
        control_mean=control_mean,
        treatment_mean=treatment_mean,
        absolute_effect=absolute_effect,
        relative_effect=relative_effect,
        confidence_level=1.0 - alpha,
        confidence_interval_low=ci_low,
        confidence_interval_high=ci_high,
        bootstrap_replicates=bootstrap_replicates,
        bootstrap_seed=bootstrap_seed,
        permutation_replicates=permutation_replicates,
        permutation_seed=permutation_seed,
        permutation_p_value=p_value,
        alpha=alpha,
        statistically_detectable=(
            p_value < alpha
        ),
    )
