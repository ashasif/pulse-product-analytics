"""Statistical-inference contract controls for Pulse Phase 5.

This module intentionally contains no hypothesis-test implementation yet.

Step 1 establishes the analysis-policy, metric-type, maturity, variant and
lineage controls that later inferential calculations must pass through.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


PRIMARY_POPULATION = "assigned_mature"
SUPPLEMENTARY_EXPOSED_POPULATION = "exposed_mature"

ALLOWED_METRIC_KINDS = frozenset(
    {
        "binary",
        "continuous",
        "count",
    }
)

ALLOWED_METRIC_ROLES = frozenset(
    {
        "primary",
        "secondary",
        "commercial",
        "guardrail",
    }
)

ALLOWED_MULTIPLICITY_METHODS = frozenset(
    {
        "holm",
    }
)

REQUIRED_LINEAGE_FIELDS = (
    "ingestion_batch_id",
    "analytics_build_run_id",
    "observation_cutoff_at",
)


class InferenceContractError(ValueError):
    """Raised when Phase 5 inference-contract requirements are violated."""


@dataclass(frozen=True, slots=True)
class InferencePolicy:
    """Global statistical-policy controls for Phase 5."""

    alpha: float = 0.05
    primary_population: str = PRIMARY_POPULATION
    require_mature_window: bool = True
    allow_exposure_conditioned_primary: bool = False
    multiplicity_method: str = "holm"

    def __post_init__(self) -> None:
        if not isinstance(self.alpha, (int, float)):
            raise InferenceContractError("alpha must be numeric")

        if not 0.0 < float(self.alpha) < 1.0:
            raise InferenceContractError("alpha must be strictly between 0 and 1")

        if self.primary_population != PRIMARY_POPULATION:
            raise InferenceContractError(
                "Phase 5 primary inference must use the assigned_mature population"
            )

        if not self.require_mature_window:
            raise InferenceContractError(
                "Phase 5 primary inference must require mature analysis windows"
            )

        if self.allow_exposure_conditioned_primary:
            raise InferenceContractError(
                "Exposure-conditioned analysis cannot be the Phase 5 primary estimand"
            )

        if self.multiplicity_method not in ALLOWED_MULTIPLICITY_METHODS:
            raise InferenceContractError(
                f"Unsupported multiplicity method: {self.multiplicity_method}"
            )

    @property
    def confidence_level(self) -> float:
        """Return the confidence level implied by alpha."""

        return 1.0 - float(self.alpha)


@dataclass(frozen=True, slots=True)
class MetricInferenceSpec:
    """Statistical metadata for an existing reporting-layer outcome.

    This class does not define or calculate the business metric. It records
    only the statistical outcome type and experiment role required to choose
    an inferential method.
    """

    metric_name: str
    metric_kind: str
    metric_role: str

    def __post_init__(self) -> None:
        if not self.metric_name or not self.metric_name.strip():
            raise InferenceContractError("metric_name must be non-empty")

        if self.metric_kind not in ALLOWED_METRIC_KINDS:
            raise InferenceContractError(
                f"Unsupported metric kind: {self.metric_kind}"
            )

        if self.metric_role not in ALLOWED_METRIC_ROLES:
            raise InferenceContractError(
                f"Unsupported metric role: {self.metric_role}"
            )


def validate_common_lineage(
    rows: Sequence[Mapping[str, object]],
    *,
    required_fields: Sequence[str] = REQUIRED_LINEAGE_FIELDS,
) -> None:
    """Require all supplied rows to belong to the same production lineage."""

    if not rows:
        raise InferenceContractError("At least one row is required")

    for field in required_fields:
        if field not in rows[0]:
            raise InferenceContractError(
                f"Required lineage field is missing: {field}"
            )

        expected = rows[0][field]

        if expected is None:
            raise InferenceContractError(
                f"Required lineage field cannot be NULL: {field}"
            )

        for row in rows[1:]:
            if field not in row:
                raise InferenceContractError(
                    f"Required lineage field is missing: {field}"
                )

            if row[field] is None:
                raise InferenceContractError(
                    f"Required lineage field cannot be NULL: {field}"
                )

            if row[field] != expected:
                raise InferenceContractError(
                    f"Incompatible production lineage for field: {field}"
                )


def validate_variant_summary_rows(
    rows: Sequence[Mapping[str, object]],
) -> None:
    """Require exactly one control and one treatment summary row."""

    if len(rows) != 2:
        raise InferenceContractError(
            "A two-arm experiment summary must contain exactly two rows"
        )

    variants: list[str] = []

    for row in rows:
        if "variant" not in row:
            raise InferenceContractError("Variant summary row is missing variant")

        variant = str(row["variant"]).strip().lower()

        if not variant:
            raise InferenceContractError("Variant cannot be blank")

        variants.append(variant)

    if set(variants) != {"control", "treatment"}:
        raise InferenceContractError(
            "Two-arm Phase 5 inference requires control and treatment variants"
        )

    if len(set(variants)) != 2:
        raise InferenceContractError(
            "Control and treatment summary rows must be unique"
        )


def require_all_mature(
    rows: Sequence[Mapping[str, object]],
    *,
    maturity_field: str = "analysis_window_mature",
) -> None:
    """Reject any primary-analysis row with an immature analysis window."""

    if not rows:
        raise InferenceContractError("At least one row is required")

    for row in rows:
        if maturity_field not in row:
            raise InferenceContractError(
                f"Maturity field is missing: {maturity_field}"
            )

        if row[maturity_field] is not True:
            raise InferenceContractError(
                "Primary inference cannot include immature analysis windows"
            )

# ---------------------------------------------------------------------------
# Binary-outcome inference
# ---------------------------------------------------------------------------

from math import erfc, sqrt
from statistics import NormalDist


@dataclass(frozen=True, slots=True)
class BinaryInferenceResult:
    """Two-arm inference result for a binary randomized outcome."""

    metric_name: str

    control_successes: int
    control_total: int
    treatment_successes: int
    treatment_total: int

    control_rate: float
    treatment_rate: float

    absolute_effect: float
    percentage_point_effect: float
    relative_effect: float | None

    confidence_level: float
    confidence_interval_low: float
    confidence_interval_high: float

    z_statistic: float
    p_value: float
    alpha: float
    statistically_detectable: bool


@dataclass(frozen=True, slots=True)
class AdjustedPValue:
    """Multiplicity-adjusted p-value for one supportive metric."""

    metric_name: str
    raw_p_value: float
    adjusted_p_value: float
    alpha: float
    statistically_detectable_after_adjustment: bool


def _validate_binary_group(
    successes: object,
    total: object,
    *,
    group_name: str,
) -> tuple[int, int]:
    """Validate a binary outcome numerator and denominator."""

    if isinstance(successes, bool) or not isinstance(successes, int):
        raise InferenceContractError(
            f"{group_name} successes must be an integer"
        )

    if isinstance(total, bool) or not isinstance(total, int):
        raise InferenceContractError(
            f"{group_name} total must be an integer"
        )

    if total <= 0:
        raise InferenceContractError(
            f"{group_name} total must be greater than zero"
        )

    if successes < 0:
        raise InferenceContractError(
            f"{group_name} successes cannot be negative"
        )

    if successes > total:
        raise InferenceContractError(
            f"{group_name} successes cannot exceed total"
        )

    return successes, total


def _validate_inference_alpha(alpha: object) -> float:
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
        raise InferenceContractError("alpha must be numeric")

    alpha = float(alpha)

    if not 0.0 < alpha < 1.0:
        raise InferenceContractError(
            "alpha must be strictly between 0 and 1"
        )

    return alpha


def _wilson_interval(
    successes: int,
    total: int,
    *,
    alpha: float,
) -> tuple[float, float]:
    """Wilson score interval for a single binomial proportion."""

    proportion = successes / total
    z = NormalDist().inv_cdf(1.0 - alpha / 2.0)

    denominator = 1.0 + (z * z) / total

    centre = (
        proportion
        + (z * z) / (2.0 * total)
    ) / denominator

    half_width = (
        z
        * sqrt(
            (
                proportion * (1.0 - proportion) / total
                + (z * z) / (4.0 * total * total)
            )
        )
        / denominator
    )

    return (
        max(0.0, centre - half_width),
        min(1.0, centre + half_width),
    )


def _newcombe_difference_interval(
    *,
    control_successes: int,
    control_total: int,
    treatment_successes: int,
    treatment_total: int,
    alpha: float,
) -> tuple[float, float]:
    """Newcombe score interval for treatment minus control proportion.

    The interval combines Wilson score intervals for the two independent
    binomial proportions without using the unstable simple Wald interval.
    """

    control_rate = control_successes / control_total
    treatment_rate = treatment_successes / treatment_total
    difference = treatment_rate - control_rate

    control_low, control_high = _wilson_interval(
        control_successes,
        control_total,
        alpha=alpha,
    )

    treatment_low, treatment_high = _wilson_interval(
        treatment_successes,
        treatment_total,
        alpha=alpha,
    )

    lower = difference - sqrt(
        (treatment_rate - treatment_low) ** 2
        + (control_high - control_rate) ** 2
    )

    upper = difference + sqrt(
        (treatment_high - treatment_rate) ** 2
        + (control_rate - control_low) ** 2
    )

    return max(-1.0, lower), min(1.0, upper)


def infer_binary_outcome(
    *,
    metric_name: str,
    control_successes: int,
    control_total: int,
    treatment_successes: int,
    treatment_total: int,
    alpha: float = 0.05,
) -> BinaryInferenceResult:
    """Perform two-arm inference for a binary randomized outcome.

    Effect direction is always:

        treatment - control

    The hypothesis-test p-value comes from the conventional pooled
    two-proportion z-test.

    The confidence interval is the Newcombe/Wilson score interval for the
    difference between independent proportions.
    """

    if not metric_name or not metric_name.strip():
        raise InferenceContractError("metric_name must be non-empty")

    alpha = _validate_inference_alpha(alpha)

    control_successes, control_total = _validate_binary_group(
        control_successes,
        control_total,
        group_name="control",
    )

    treatment_successes, treatment_total = _validate_binary_group(
        treatment_successes,
        treatment_total,
        group_name="treatment",
    )

    control_rate = control_successes / control_total
    treatment_rate = treatment_successes / treatment_total

    absolute_effect = treatment_rate - control_rate
    percentage_point_effect = absolute_effect * 100.0

    relative_effect: float | None

    if control_rate == 0.0:
        relative_effect = None
    else:
        relative_effect = treatment_rate / control_rate - 1.0

    pooled_rate = (
        control_successes + treatment_successes
    ) / (
        control_total + treatment_total
    )

    pooled_variance = (
        pooled_rate
        * (1.0 - pooled_rate)
        * (
            1.0 / control_total
            + 1.0 / treatment_total
        )
    )

    if pooled_variance == 0.0:
        z_statistic = 0.0
        p_value = 1.0
    else:
        standard_error = sqrt(pooled_variance)
        z_statistic = absolute_effect / standard_error
        p_value = erfc(abs(z_statistic) / sqrt(2.0))

    confidence_low, confidence_high = _newcombe_difference_interval(
        control_successes=control_successes,
        control_total=control_total,
        treatment_successes=treatment_successes,
        treatment_total=treatment_total,
        alpha=alpha,
    )

    return BinaryInferenceResult(
        metric_name=metric_name,
        control_successes=control_successes,
        control_total=control_total,
        treatment_successes=treatment_successes,
        treatment_total=treatment_total,
        control_rate=control_rate,
        treatment_rate=treatment_rate,
        absolute_effect=absolute_effect,
        percentage_point_effect=percentage_point_effect,
        relative_effect=relative_effect,
        confidence_level=1.0 - alpha,
        confidence_interval_low=confidence_low,
        confidence_interval_high=confidence_high,
        z_statistic=z_statistic,
        p_value=p_value,
        alpha=alpha,
        statistically_detectable=p_value < alpha,
    )


def holm_adjust_p_values(
    p_values: Mapping[str, float],
    *,
    alpha: float = 0.05,
) -> list[AdjustedPValue]:
    """Apply Holm's step-down family-wise error-rate adjustment.

    Returned rows preserve the original mapping iteration order.

    The primary metric should not be mixed silently into a supportive metric
    family. The caller is responsible for supplying the intended family.
    """

    alpha = _validate_inference_alpha(alpha)

    if not p_values:
        raise InferenceContractError(
            "At least one p-value is required for Holm adjustment"
        )

    validated: list[tuple[str, float]] = []

    for metric_name, p_value in p_values.items():
        if not metric_name or not metric_name.strip():
            raise InferenceContractError(
                "Holm metric names must be non-empty"
            )

        if isinstance(p_value, bool) or not isinstance(
            p_value,
            (int, float),
        ):
            raise InferenceContractError(
                f"p-value for {metric_name} must be numeric"
            )

        p_value = float(p_value)

        if not 0.0 <= p_value <= 1.0:
            raise InferenceContractError(
                f"p-value for {metric_name} must be between 0 and 1"
            )

        validated.append((metric_name, p_value))

    ordered = sorted(
        validated,
        key=lambda item: item[1],
    )

    family_size = len(ordered)
    adjusted_by_metric: dict[str, float] = {}

    running_max = 0.0

    for index, (metric_name, raw_p_value) in enumerate(ordered):
        multiplier = family_size - index
        candidate = min(1.0, raw_p_value * multiplier)

        running_max = max(running_max, candidate)

        adjusted_by_metric[metric_name] = running_max

    return [
        AdjustedPValue(
            metric_name=metric_name,
            raw_p_value=raw_p_value,
            adjusted_p_value=adjusted_by_metric[metric_name],
            alpha=alpha,
            statistically_detectable_after_adjustment=(
                adjusted_by_metric[metric_name] < alpha
            ),
        )
        for metric_name, raw_p_value in validated
    ]
