"""Field-level schema contract for approved Pulse Phase 2 raw exports."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


FieldKind = Literal[
    "string",
    "timestamp",
    "date",
    "integer",
    "decimal",
    "boolean",
]


@dataclass(frozen=True)
class FieldRule:
    """Validation and parsing rules for one raw CSV field."""

    kind: FieldKind
    nullable: bool = False
    allowed_values: tuple[str, ...] | None = None
    minimum: int | Decimal | None = None
    maximum: int | Decimal | None = None


def _string(
    *,
    nullable: bool = False,
    allowed: tuple[str, ...] | None = None,
) -> FieldRule:
    return FieldRule(
        kind="string",
        nullable=nullable,
        allowed_values=allowed,
    )


def _timestamp(*, nullable: bool = False) -> FieldRule:
    return FieldRule(
        kind="timestamp",
        nullable=nullable,
    )


def _date(*, nullable: bool = False) -> FieldRule:
    return FieldRule(
        kind="date",
        nullable=nullable,
    )


def _integer(
    *,
    nullable: bool = False,
    minimum: int | None = None,
    maximum: int | None = None,
) -> FieldRule:
    return FieldRule(
        kind="integer",
        nullable=nullable,
        minimum=minimum,
        maximum=maximum,
    )


def _decimal(
    *,
    nullable: bool = False,
    minimum: str | None = None,
    maximum: str | None = None,
) -> FieldRule:
    return FieldRule(
        kind="decimal",
        nullable=nullable,
        minimum=(
            Decimal(minimum)
            if minimum is not None
            else None
        ),
        maximum=(
            Decimal(maximum)
            if maximum is not None
            else None
        ),
    )


def _boolean(
    *,
    nullable: bool = False,
) -> FieldRule:
    return FieldRule(
        kind="boolean",
        nullable=nullable,
    )


PLATFORMS = (
    "ios",
    "android",
)

ACQUISITION_CHANNELS = (
    "organic",
    "paid_social",
    "paid_search",
    "referral",
    "content",
)

COUNTRY_CODES = (
    "GB",
    "US",
    "CA",
    "AU",
    "DE",
    "FR",
    "IN",
    "SG",
    "OTHER",
)

FEATURE_NAMES = (
    "ai_assistant",
    "smart_tasks",
    "document_summarizer",
    "focus_session",
    "ai_notes",
)

EVENT_NAMES = (
    "app_install",
    "signup",
    "onboarding_started",
    "onboarding_completed",
    "session_started",
    "feature_used",
    "paywall_viewed",
    "trial_started",
    "subscription_started",
    "subscription_renewed",
    "cancellation_requested",
    "subscription_expired",
    "payment_failed",
)

BILLING_PERIODS = (
    "monthly",
    "annual",
)

SUBSCRIPTION_STATUSES = (
    "trialing",
    "active",
    "past_due",
    "expired",
    "cancel_at_period_end",
)

SUBSCRIPTION_END_REASONS = (
    "trial_no_conversion",
    "payment_failure",
    "voluntary_cancellation",
)

TRANSACTION_TYPES = (
    "initial_charge",
    "renewal",
)

PAYMENT_STATUSES = (
    "succeeded",
    "failed",
)

EXPERIMENT_VARIANTS = (
    "control",
    "treatment",
)

MARKETING_SPEND_TYPES = (
    "zero_direct",
    "paid_media",
    "indirect",
)

MARKETING_CAMPAIGN_TYPES = (
    "organic_unpaid",
    "always_on_social",
    "always_on_search",
    "referral_incentives",
    "content_program",
    "seasonal_push",
    "tactical_push",
)

RELEASE_TYPES = (
    "major",
    "minor",
    "patch",
)

ROLLOUT_STRATEGIES = (
    "full",
    "phased",
)

RELEASE_FEATURE_AREAS = (
    "onboarding",
    "core_platform",
    "smart_tasks",
    "document_summarizer",
    "ai_notes",
    "ai_assistant",
    "focus_session",
)


DATASET_FIELD_RULES: dict[
    str,
    dict[str, FieldRule],
] = {
    "installations": {
        "installation_id": _string(),
        "anonymous_id": _string(),
        "installed_at": _timestamp(),
        "platform": _string(
            allowed=PLATFORMS,
        ),
        "acquisition_channel": _string(
            allowed=ACQUISITION_CHANNELS,
        ),
        "country_code": _string(
            allowed=COUNTRY_CODES,
        ),
    },
    "users": {
        "user_id": _string(),
        "installation_id": _string(),
        "anonymous_id": _string(),
        "signed_up_at": _timestamp(),
        "onboarding_started_at": _timestamp(
            nullable=True,
        ),
        "onboarding_completed_at": _timestamp(
            nullable=True,
        ),
    },
    "product_events": {
        "event_id": _string(),
        "event_name": _string(
            allowed=EVENT_NAMES,
        ),
        "occurred_at": _timestamp(),
        "installation_id": _string(),
        "anonymous_id": _string(),
        "user_id": _string(
            nullable=True,
        ),
        "session_id": _string(
            nullable=True,
        ),
        "feature_name": _string(
            nullable=True,
            allowed=FEATURE_NAMES,
        ),
    },
    "subscriptions": {
        "subscription_id": _string(),
        "user_id": _string(),
        "installation_id": _string(),
        "billing_period": _string(
            allowed=BILLING_PERIODS,
        ),
        "price_gbp": _decimal(
            minimum="0",
        ),
        "currency": _string(
            allowed=("GBP",),
        ),
        "status": _string(
            allowed=SUBSCRIPTION_STATUSES,
        ),
        "trial_started_at": _timestamp(),
        "trial_ends_at": _timestamp(),
        "subscription_started_at": _timestamp(
            nullable=True,
        ),
        "current_period_start_at": _timestamp(
            nullable=True,
        ),
        "current_period_end_at": _timestamp(
            nullable=True,
        ),
        "cancellation_requested_at": _timestamp(
            nullable=True,
        ),
        "expired_at": _timestamp(
            nullable=True,
        ),
        "auto_renew": _boolean(),
        "end_reason": _string(
            nullable=True,
            allowed=SUBSCRIPTION_END_REASONS,
        ),
    },
    "subscription_transactions": {
        "transaction_id": _string(),
        "subscription_id": _string(),
        "user_id": _string(),
        "installation_id": _string(),
        "transaction_type": _string(
            allowed=TRANSACTION_TYPES,
        ),
        "attempted_at": _timestamp(),
        "billing_period": _string(
            allowed=BILLING_PERIODS,
        ),
        "amount_gbp": _decimal(
            minimum="0",
        ),
        "currency": _string(
            allowed=("GBP",),
        ),
        "payment_status": _string(
            allowed=PAYMENT_STATUSES,
        ),
        "billing_cycle_number": _integer(
            minimum=1,
        ),
        "attempt_number": _integer(
            minimum=1,
            maximum=2,
        ),
    },
    "experiment_assignments": {
        "assignment_id": _string(),
        "experiment_id": _string(),
        "experiment_name": _string(),
        "user_id": _string(),
        "installation_id": _string(),
        "randomization_unit": _string(
            allowed=("user",),
        ),
        "variant": _string(
            allowed=EXPERIMENT_VARIANTS,
        ),
        "allocation_probability": _decimal(
            minimum="0",
            maximum="1",
        ),
        "assignment_at": _timestamp(),
        "exposed_at": _timestamp(
            nullable=True,
        ),
        "experiment_start_at": _timestamp(),
        "experiment_end_at": _timestamp(),
        "eligibility_rule": _string(),
        "assignment_trigger": _string(),
        "exposure_trigger": _string(),
        "hypothesis": _string(),
        "primary_metric": _string(),
        "secondary_metric": _string(),
        "commercial_metric": _string(),
        "guardrail_metric": _string(),
        "analysis_window_days": _integer(
            minimum=1,
        ),
    },
    "marketing_spend": {
        "marketing_spend_id": _string(),
        "period_start": _date(),
        "period_end": _date(),
        "acquisition_channel": _string(
            allowed=ACQUISITION_CHANNELS,
        ),
        "spend_type": _string(
            allowed=MARKETING_SPEND_TYPES,
        ),
        "campaign_type": _string(
            allowed=MARKETING_CAMPAIGN_TYPES,
        ),
        "spend": _decimal(
            minimum="0",
        ),
        "currency": _string(
            allowed=("GBP",),
        ),
        "impressions": _integer(
            nullable=True,
            minimum=0,
        ),
        "clicks": _integer(
            nullable=True,
            minimum=0,
        ),
    },
    "app_releases": {
        "app_release_id": _string(),
        "release_key": _string(),
        "release_name": _string(),
        "release_sequence": _integer(
            minimum=1,
        ),
        "platform": _string(
            allowed=PLATFORMS,
        ),
        "version": _string(),
        "release_at": _timestamp(),
        "release_type": _string(
            allowed=RELEASE_TYPES,
        ),
        "feature_area": _string(
            allowed=RELEASE_FEATURE_AREAS,
        ),
        "rollout_strategy": _string(
            allowed=ROLLOUT_STRATEGIES,
        ),
        "rollout_days": _integer(
            minimum=0,
        ),
        "rollout_complete_at": _timestamp(),
        "release_channel": _string(
            allowed=("production",),
        ),
        "release_notes": _string(),
    },
}


def get_field_rules(
    dataset_name: str,
) -> dict[str, FieldRule]:
    """Return the ordered field rules for one approved dataset."""

    try:
        return DATASET_FIELD_RULES[
            dataset_name
        ]
    except KeyError as exc:
        raise KeyError(
            "No field schema is defined "
            f"for dataset: {dataset_name}"
        ) from exc