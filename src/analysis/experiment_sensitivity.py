"""Design-sensitivity diagnostics for Pulse Phase 5 experiments.

These functions calculate approximate minimum detectable effects (MDEs).

They do NOT calculate retrospective observed power.

Binary outcomes use a local normal approximation around the control rate.
Continuous outcomes use the observed arm-specific sample standard deviations.

The results are design-sensitivity diagnostics, not guarantees that a given
effect would be detected in every repeated experiment.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import NormalDist

from src.analysis.experiment_inference import InferenceContractError


DEFAULT_ALPHA = 0.05
DEFAULT_POWER = 0.80


@dataclass(frozen=True, slots=True)
class BinaryMdeResult:
    metric_key: str
    control_rate: float
    control_count: int
    treatment_count: int
    alpha: float
    target_power: float
    mde_absolute: float | None
    mde_percentage_points: float | None
    status: str


@dataclass(frozen=True, slots=True)
class MeanMdeResult:
    metric_key: str
    control_stddev: float
    treatment_stddev: float
    control_count: int
    treatment_count: int
    alpha: float
    target_power: float
    mde_absolute: float
    status: str


def _validate_probability(
    value: object,
    *,
    name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise InferenceContractError(
            f"{name} must be numeric"
        )

    result = float(value)

    if not 0.0 < result < 1.0:
        raise InferenceContractError(
            f"{name} must be strictly between 0 and 1"
        )

    return result


def _validate_count(
    value: object,
    *,
    name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(
        value,
        int,
    ):
        raise InferenceContractError(
            f"{name} must be an integer"
        )

    if value <= 1:
        raise InferenceContractError(
            f"{name} must be greater than 1"
        )

    return value


def binary_mde(
    *,
    metric_key: str,
    control_rate: float,
    control_count: int,
    treatment_count: int,
    alpha: float = DEFAULT_ALPHA,
    target_power: float = DEFAULT_POWER,
) -> BinaryMdeResult:
    """Approximate binary MDE around the observed control baseline."""

    if not metric_key or not metric_key.strip():
        raise InferenceContractError(
            "metric_key must be non-empty"
        )

    if isinstance(control_rate, bool) or not isinstance(
        control_rate,
        (int, float),
    ):
        raise InferenceContractError(
            "control_rate must be numeric"
        )

    control_rate = float(control_rate)

    if not 0.0 <= control_rate <= 1.0:
        raise InferenceContractError(
            "control_rate must be between 0 and 1"
        )

    control_count = _validate_count(
        control_count,
        name="control_count",
    )

    treatment_count = _validate_count(
        treatment_count,
        name="treatment_count",
    )

    alpha = _validate_probability(
        alpha,
        name="alpha",
    )

    target_power = _validate_probability(
        target_power,
        name="target_power",
    )

    if control_rate in (0.0, 1.0):
        return BinaryMdeResult(
            metric_key=metric_key,
            control_rate=control_rate,
            control_count=control_count,
            treatment_count=treatment_count,
            alpha=alpha,
            target_power=target_power,
            mde_absolute=None,
            mde_percentage_points=None,
            status="not_estimable_saturated_baseline",
        )

    z_alpha = NormalDist().inv_cdf(
        1.0 - alpha / 2.0
    )

    z_power = NormalDist().inv_cdf(
        target_power
    )

    standard_error = sqrt(
        control_rate
        * (1.0 - control_rate)
        * (
            1.0 / control_count
            + 1.0 / treatment_count
        )
    )

    mde = (
        z_alpha + z_power
    ) * standard_error

    return BinaryMdeResult(
        metric_key=metric_key,
        control_rate=control_rate,
        control_count=control_count,
        treatment_count=treatment_count,
        alpha=alpha,
        target_power=target_power,
        mde_absolute=mde,
        mde_percentage_points=mde * 100.0,
        status="estimated",
    )


def mean_mde(
    *,
    metric_key: str,
    control_stddev: float,
    treatment_stddev: float,
    control_count: int,
    treatment_count: int,
    alpha: float = DEFAULT_ALPHA,
    target_power: float = DEFAULT_POWER,
) -> MeanMdeResult:
    """Approximate MDE for a treatment-minus-control mean difference."""

    if not metric_key or not metric_key.strip():
        raise InferenceContractError(
            "metric_key must be non-empty"
        )

    for name, value in (
        ("control_stddev", control_stddev),
        ("treatment_stddev", treatment_stddev),
    ):
        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise InferenceContractError(
                f"{name} must be numeric"
            )

        value = float(value)

        if not isfinite(value) or value < 0.0:
            raise InferenceContractError(
                f"{name} must be finite and non-negative"
            )

    control_stddev = float(
        control_stddev
    )

    treatment_stddev = float(
        treatment_stddev
    )

    control_count = _validate_count(
        control_count,
        name="control_count",
    )

    treatment_count = _validate_count(
        treatment_count,
        name="treatment_count",
    )

    alpha = _validate_probability(
        alpha,
        name="alpha",
    )

    target_power = _validate_probability(
        target_power,
        name="target_power",
    )

    z_alpha = NormalDist().inv_cdf(
        1.0 - alpha / 2.0
    )

    z_power = NormalDist().inv_cdf(
        target_power
    )

    standard_error = sqrt(
        control_stddev ** 2
        / control_count
        +
        treatment_stddev ** 2
        / treatment_count
    )

    mde = (
        z_alpha + z_power
    ) * standard_error

    return MeanMdeResult(
        metric_key=metric_key,
        control_stddev=control_stddev,
        treatment_stddev=treatment_stddev,
        control_count=control_count,
        treatment_count=treatment_count,
        alpha=alpha,
        target_power=target_power,
        mde_absolute=mde,
        status="estimated",
    )
