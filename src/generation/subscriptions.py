"""Synthetic subscription and monetisation lifecycle generation for Pulse."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import datetime, timedelta, timezone
from math import isclose
from pathlib import Path
import random
from typing import Any

from src.generation.installations import (
    DEFAULT_SIMULATION_CONFIG,
    load_simulation_config,
)
from src.generation.randomness import get_substream_seed


SUBSCRIPTION_EVENT_NAMES = (
    "trial_started",
    "subscription_started",
    "subscription_renewed",
    "cancellation_requested",
    "subscription_expired",
    "payment_failed",
)

EVENT_SORT_PRIORITY = {
    "app_install": 0,
    "signup": 1,
    "onboarding_started": 2,
    "onboarding_completed": 3,
    "session_started": 4,
    "feature_used": 5,
    "paywall_viewed": 6,
    "trial_started": 7,
    "subscription_started": 8,
    "subscription_renewed": 9,
    "payment_failed": 10,
    "cancellation_requested": 11,
    "subscription_expired": 12,
}


def _parse_utc_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 timestamp as a UTC-aware datetime."""
    timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def get_snapshot_at(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> datetime:
    """Return the configured dataset snapshot timestamp."""
    config = load_simulation_config(config_path)
    return _parse_utc_timestamp(config["simulation"]["snapshot_at"])


def _validate_probability(value: float, name: str) -> float:
    """Validate and return a probability in [0, 1]."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return value


def _validate_positive_number(value: float, name: str) -> float:
    """Validate and return a strictly positive number."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    value = float(value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _validate_non_negative_number(value: float, name: str) -> float:
    """Validate and return a non-negative number."""
    if not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    value = float(value)
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


def _validate_weight_map(weights: dict[str, Any], name: str) -> dict[str, float]:
    """Validate a named probability distribution."""
    if not weights:
        raise ValueError(f"{name} must not be empty")

    validated = {
        key: _validate_non_negative_number(value, f"{name}.{key}")
        for key, value in weights.items()
    }

    if not isclose(
        sum(validated.values()),
        1.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        raise ValueError(f"{name} weights must sum to 1")

    return validated


def load_subscription_config(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict[str, Any]:
    """Load and validate subscription-lifecycle assumptions."""
    config = load_simulation_config(config_path)
    lifecycle = config["subscription_lifecycle"]

    trial_length_days = lifecycle["trial_length_days"]
    if not isinstance(trial_length_days, int) or trial_length_days <= 0:
        raise ValueError("trial_length_days must be a positive integer")

    delay_min = lifecycle["trial_start_delay_seconds_min"]
    delay_max = lifecycle["trial_start_delay_seconds_max"]
    if not isinstance(delay_min, int) or delay_min < 0:
        raise ValueError(
            "trial_start_delay_seconds_min must be a non-negative integer"
        )
    if not isinstance(delay_max, int) or delay_max < delay_min:
        raise ValueError(
            "trial_start_delay_seconds_max must be >= minimum"
        )

    for name in (
        "trial_start_probability_per_paywall",
        "trial_onboarding_completed_adjustment",
        "trial_session_adjustment_per_session",
        "trial_session_adjustment_cap",
        "trial_feature_adjustment_per_feature",
        "trial_feature_adjustment_cap",
        "trial_probability_cap",
    ):
        _validate_non_negative_number(lifecycle[name], name)

    if lifecycle["trial_probability_cap"] > 1:
        raise ValueError("trial_probability_cap must be <= 1")

    plan_mix = _validate_weight_map(lifecycle["plan_mix"], "plan_mix")
    expected_plans = {"monthly", "annual"}
    if set(plan_mix) != expected_plans:
        raise ValueError("plan_mix must contain monthly and annual")

    pricing = lifecycle["pricing_gbp"]
    period_days = lifecycle["billing_period_days"]
    if set(pricing) != expected_plans:
        raise ValueError("pricing_gbp must contain monthly and annual")
    if set(period_days) != expected_plans:
        raise ValueError(
            "billing_period_days must contain monthly and annual"
        )

    for plan in expected_plans:
        _validate_positive_number(pricing[plan], f"pricing_gbp.{plan}")
        if not isinstance(period_days[plan], int) or period_days[plan] <= 0:
            raise ValueError(
                f"billing_period_days.{plan} must be a positive integer"
            )

    paid_conversion = lifecycle["paid_conversion"]
    for name in (
        "base_probability",
        "onboarding_completed_adjustment",
        "session_adjustment_per_session",
        "session_adjustment_cap",
        "feature_adjustment_per_feature",
        "feature_adjustment_cap",
        "probability_cap",
    ):
        _validate_non_negative_number(
            paid_conversion[name],
            f"paid_conversion.{name}",
        )

    if paid_conversion["probability_cap"] > 1:
        raise ValueError("paid_conversion.probability_cap must be <= 1")

    cancellation = lifecycle["cancellation_probability"]
    renewal_probability_keys = (
        "first_renewal",
        "second_renewal",
        "third_renewal",
        "later_renewal",
    )
    for plan in expected_plans:
        plan_probabilities = cancellation[plan]
        if set(plan_probabilities) != set(renewal_probability_keys):
            raise ValueError(
                "cancellation_probability."
                f"{plan} must contain "
                "first_renewal, second_renewal, third_renewal and "
                "later_renewal"
            )
        for key in renewal_probability_keys:
            _validate_probability(
                plan_probabilities[key],
                f"cancellation_probability.{plan}.{key}",
            )

    for name in (
        "inactive_penalty",
        "session_discount_per_session",
        "session_discount_cap",
        "minimum_probability",
        "maximum_probability",
    ):
        _validate_non_negative_number(
            cancellation[name],
            f"cancellation_probability.{name}",
        )

    if cancellation["maximum_probability"] > 1:
        raise ValueError(
            "cancellation_probability.maximum_probability must be <= 1"
        )
    if (
        cancellation["minimum_probability"]
        > cancellation["maximum_probability"]
    ):
        raise ValueError(
            "cancellation minimum_probability must be <= maximum_probability"
        )

    for name in (
        "monthly_lookback_days",
        "annual_lookback_days",
        "lead_days_min",
        "lead_days_max",
    ):
        value = cancellation[name]
        if not isinstance(value, int) or value < 0:
            raise ValueError(
                f"cancellation_probability.{name} must be a non-negative integer"
            )

    if cancellation["lead_days_max"] < cancellation["lead_days_min"]:
        raise ValueError(
            "cancellation lead_days_max must be >= lead_days_min"
        )

    payment = lifecycle["payment"]
    _validate_probability(
        payment["failure_probability"],
        "payment.failure_probability",
    )
    _validate_probability(
        payment["retry_recovery_probability"],
        "payment.retry_recovery_probability",
    )
    if (
        not isinstance(payment["retry_delay_days"], int)
        or payment["retry_delay_days"] <= 0
    ):
        raise ValueError("payment.retry_delay_days must be a positive integer")
    if not isinstance(payment["currency"], str) or not payment["currency"].strip():
        raise ValueError("payment.currency must be a non-empty string")

    return lifecycle


def _validate_users(
    users: list[dict[str, Any]],
    snapshot_at: datetime,
) -> dict[str, dict[str, Any]]:
    """Validate registered-user inputs and return a user-id map."""
    if not isinstance(users, list):
        raise TypeError("users must be a list")

    users_by_id: dict[str, dict[str, Any]] = {}
    installation_ids: set[str] = set()

    required_fields = {
        "user_id",
        "installation_id",
        "anonymous_id",
        "signed_up_at",
        "onboarding_started_at",
        "onboarding_completed_at",
    }

    for user in users:
        missing = sorted(required_fields - set(user))
        if missing:
            raise ValueError(f"User is missing required fields: {missing}")

        user_id = user["user_id"]
        installation_id = user["installation_id"]

        if user_id in users_by_id:
            raise ValueError(f"Duplicate user_id: {user_id}")
        if installation_id in installation_ids:
            raise ValueError(
                "Only one registered user may be linked to an installation"
            )

        signed_up_at = user["signed_up_at"]
        if not isinstance(signed_up_at, datetime):
            raise TypeError("signed_up_at must be a datetime")
        if signed_up_at.tzinfo is None:
            raise ValueError("signed_up_at must be timezone-aware")
        if signed_up_at >= snapshot_at:
            raise ValueError("signed_up_at must be before the snapshot")

        for field in (
            "onboarding_started_at",
            "onboarding_completed_at",
        ):
            value = user[field]
            if value is not None:
                if not isinstance(value, datetime):
                    raise TypeError(f"{field} must be a datetime or None")
                if value.tzinfo is None:
                    raise ValueError(f"{field} must be timezone-aware")
                if value >= snapshot_at:
                    raise ValueError(f"{field} must be before the snapshot")

        users_by_id[user_id] = user
        installation_ids.add(installation_id)

    return users_by_id


def _build_activity_profiles(
    product_events: list[dict[str, Any]],
    users_by_id: dict[str, dict[str, Any]],
    snapshot_at: datetime,
) -> dict[str, dict[str, Any]]:
    """Index registered product behaviour without changing source events."""
    if not isinstance(product_events, list):
        raise TypeError("product_events must be a list")

    profiles = {
        user_id: {
            "session_times": [],
            "feature_times": [],
            "paywall_contexts": [],
        }
        for user_id in users_by_id
    }

    grouped: dict[str, list[dict[str, Any]]] = {
        user_id: [] for user_id in users_by_id
    }

    for event in product_events:
        user_id = event.get("user_id")
        if user_id is None:
            continue
        if user_id not in users_by_id:
            raise ValueError(
                f"Product event references unknown registered user: {user_id}"
            )

        occurred_at = event.get("occurred_at")
        if not isinstance(occurred_at, datetime):
            raise TypeError("product event occurred_at must be a datetime")
        if occurred_at.tzinfo is None:
            raise ValueError("product event occurred_at must be timezone-aware")
        if occurred_at >= snapshot_at:
            raise ValueError("product event occurs at/after the snapshot")

        grouped[user_id].append(event)

    for user_id, events in grouped.items():
        events.sort(
            key=lambda row: (
                row["occurred_at"],
                row.get("event_id") or "",
            )
        )

        sessions = 0
        features = 0
        profile = profiles[user_id]

        for event in events:
            event_name = event.get("event_name")
            occurred_at = event["occurred_at"]

            if event_name == "session_started":
                sessions += 1
                profile["session_times"].append(occurred_at)
            elif event_name == "feature_used":
                features += 1
                profile["feature_times"].append(occurred_at)
            elif event_name == "paywall_viewed":
                profile["paywall_contexts"].append(
                    {
                        "occurred_at": occurred_at,
                        "sessions_before": sessions,
                        "features_before": features,
                    }
                )

    return profiles


def _count_between(
    timestamps: list[datetime],
    start_at: datetime,
    end_at: datetime,
) -> int:
    """Count timestamps in the half-open interval [start_at, end_at)."""
    return max(
        0,
        bisect_left(timestamps, end_at)
        - bisect_left(timestamps, start_at),
    )


def _count_through(
    timestamps: list[datetime],
    end_at: datetime,
) -> int:
    """Count timestamps at or before end_at."""
    return bisect_right(timestamps, end_at)


def _trial_start_probability(
    *,
    user: dict[str, Any],
    paywall_at: datetime,
    sessions_before: int,
    features_before: int,
    lifecycle: dict[str, Any],
) -> float:
    """Calculate trial-start probability at a specific paywall exposure."""
    probability = float(lifecycle["trial_start_probability_per_paywall"])

    completed_at = user["onboarding_completed_at"]
    if completed_at is not None and completed_at <= paywall_at:
        probability += float(
            lifecycle["trial_onboarding_completed_adjustment"]
        )

    probability += min(
        sessions_before
        * float(lifecycle["trial_session_adjustment_per_session"]),
        float(lifecycle["trial_session_adjustment_cap"]),
    )
    probability += min(
        features_before
        * float(lifecycle["trial_feature_adjustment_per_feature"]),
        float(lifecycle["trial_feature_adjustment_cap"]),
    )

    return min(
        float(lifecycle["trial_probability_cap"]),
        max(0.0, probability),
    )


def _paid_conversion_probability(
    *,
    user: dict[str, Any],
    trial_started_at: datetime,
    trial_ends_at: datetime,
    profile: dict[str, Any],
    lifecycle: dict[str, Any],
) -> float:
    """Calculate trial-to-paid probability using behaviour during the trial."""
    conversion = lifecycle["paid_conversion"]
    probability = float(conversion["base_probability"])

    completed_at = user["onboarding_completed_at"]
    if completed_at is not None and completed_at <= trial_ends_at:
        probability += float(
            conversion["onboarding_completed_adjustment"]
        )

    trial_sessions = _count_between(
        profile["session_times"],
        trial_started_at,
        trial_ends_at,
    )
    trial_features = _count_between(
        profile["feature_times"],
        trial_started_at,
        trial_ends_at,
    )

    probability += min(
        trial_sessions
        * float(conversion["session_adjustment_per_session"]),
        float(conversion["session_adjustment_cap"]),
    )
    probability += min(
        trial_features
        * float(conversion["feature_adjustment_per_feature"]),
        float(conversion["feature_adjustment_cap"]),
    )

    return min(
        float(conversion["probability_cap"]),
        max(0.0, probability),
    )


def _cancellation_probability(
    *,
    billing_period: str,
    renewal_number: int,
    decision_at: datetime,
    profile: dict[str, Any],
    lifecycle: dict[str, Any],
) -> float:
    """Calculate voluntary cancellation for a specific renewal decision."""
    cancellation = lifecycle["cancellation_probability"]
    lookback_days = int(
        cancellation[
            "monthly_lookback_days"
            if billing_period == "monthly"
            else "annual_lookback_days"
        ]
    )
    lookback_start = decision_at - timedelta(days=lookback_days)
    recent_sessions = _count_between(
        profile["session_times"],
        lookback_start,
        decision_at,
    )

    if renewal_number == 1:
        renewal_key = "first_renewal"
    elif renewal_number == 2:
        renewal_key = "second_renewal"
    elif renewal_number == 3:
        renewal_key = "third_renewal"
    else:
        renewal_key = "later_renewal"

    probability = float(
        cancellation[billing_period][renewal_key]
    )

    if recent_sessions == 0:
        probability += float(cancellation["inactive_penalty"])
    else:
        probability -= min(
            recent_sessions
            * float(cancellation["session_discount_per_session"]),
            float(cancellation["session_discount_cap"]),
        )

    return min(
        float(cancellation["maximum_probability"]),
        max(
            float(cancellation["minimum_probability"]),
            probability,
        ),
    )


def _subscription_event_row(
    *,
    event_name: str,
    occurred_at: datetime,
    user: dict[str, Any],
) -> dict[str, Any]:
    """Build a subscription lifecycle event using the product-event schema."""
    return {
        "event_id": None,
        "event_name": event_name,
        "occurred_at": occurred_at,
        "installation_id": user["installation_id"],
        "anonymous_id": user["anonymous_id"],
        "user_id": user["user_id"],
        "session_id": None,
        "feature_name": None,
    }


def _append_transaction(
    *,
    transactions: list[dict[str, Any]],
    subscription_id: str,
    user: dict[str, Any],
    transaction_type: str,
    attempted_at: datetime,
    billing_period: str,
    amount_gbp: float,
    currency: str,
    payment_status: str,
    billing_cycle_number: int,
    attempt_number: int,
) -> None:
    """Append one billing-attempt row."""
    transactions.append(
        {
            "transaction_id": None,
            "subscription_id": subscription_id,
            "user_id": user["user_id"],
            "installation_id": user["installation_id"],
            "transaction_type": transaction_type,
            "attempted_at": attempted_at,
            "billing_period": billing_period,
            "amount_gbp": round(float(amount_gbp), 2),
            "currency": currency,
            "payment_status": payment_status,
            "billing_cycle_number": billing_cycle_number,
            "attempt_number": attempt_number,
        }
    )


def _attempt_payment(
    *,
    transactions: list[dict[str, Any]],
    subscription_events: list[dict[str, Any]],
    subscription_id: str,
    user: dict[str, Any],
    transaction_type: str,
    attempted_at: datetime,
    billing_period: str,
    amount_gbp: float,
    currency: str,
    billing_cycle_number: int,
    snapshot_at: datetime,
    lifecycle: dict[str, Any],
    failure_rng: random.Random,
    recovery_rng: random.Random,
) -> tuple[str, datetime | None]:
    """
    Attempt a charge and, when required, one deterministic retry.

    Returns:
        ("succeeded", success_timestamp)
        ("failed", final_failure_timestamp)
        ("past_due", None) when retry is right-censored by the snapshot.
    """
    payment = lifecycle["payment"]

    first_failed = (
        failure_rng.random()
        < float(payment["failure_probability"])
    )

    if not first_failed:
        _append_transaction(
            transactions=transactions,
            subscription_id=subscription_id,
            user=user,
            transaction_type=transaction_type,
            attempted_at=attempted_at,
            billing_period=billing_period,
            amount_gbp=amount_gbp,
            currency=currency,
            payment_status="succeeded",
            billing_cycle_number=billing_cycle_number,
            attempt_number=1,
        )
        return "succeeded", attempted_at

    _append_transaction(
        transactions=transactions,
        subscription_id=subscription_id,
        user=user,
        transaction_type=transaction_type,
        attempted_at=attempted_at,
        billing_period=billing_period,
        amount_gbp=amount_gbp,
        currency=currency,
        payment_status="failed",
        billing_cycle_number=billing_cycle_number,
        attempt_number=1,
    )
    subscription_events.append(
        _subscription_event_row(
            event_name="payment_failed",
            occurred_at=attempted_at,
            user=user,
        )
    )

    retry_at = attempted_at + timedelta(
        days=int(payment["retry_delay_days"])
    )
    if retry_at >= snapshot_at:
        return "past_due", None

    recovered = (
        recovery_rng.random()
        < float(payment["retry_recovery_probability"])
    )

    if recovered:
        _append_transaction(
            transactions=transactions,
            subscription_id=subscription_id,
            user=user,
            transaction_type=transaction_type,
            attempted_at=retry_at,
            billing_period=billing_period,
            amount_gbp=amount_gbp,
            currency=currency,
            payment_status="succeeded",
            billing_cycle_number=billing_cycle_number,
            attempt_number=2,
        )
        return "succeeded", retry_at

    _append_transaction(
        transactions=transactions,
        subscription_id=subscription_id,
        user=user,
        transaction_type=transaction_type,
        attempted_at=retry_at,
        billing_period=billing_period,
        amount_gbp=amount_gbp,
        currency=currency,
        payment_status="failed",
        billing_cycle_number=billing_cycle_number,
        attempt_number=2,
    )
    subscription_events.append(
        _subscription_event_row(
            event_name="payment_failed",
            occurred_at=retry_at,
            user=user,
        )
    )
    return "failed", retry_at


def _subscription_id_for_user(user_id: str) -> str:
    """Return the stable v1 subscription identifier for a registered user."""
    suffix = user_id.removeprefix("user_")
    return f"sub_{suffix}"


def generate_subscription_lifecycle(
    users: list[dict[str, Any]],
    product_events: list[dict[str, Any]],
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    Generate subscriptions, billing attempts and subscription events.

    v1 deliberately allows at most one subscription episode per user.
    Only registered users with a registered paywall exposure can start a trial.
    Existing product-event timestamps are read as behavioural inputs and are
    never changed here.
    """
    lifecycle = load_subscription_config(config_path)
    snapshot_at = get_snapshot_at(config_path)
    users_by_id = _validate_users(users, snapshot_at)
    profiles = _build_activity_profiles(
        product_events,
        users_by_id,
        snapshot_at,
    )

    trial_decision_rng = random.Random(
        get_substream_seed("subscriptions", "trial_decision")
    )
    trial_delay_rng = random.Random(
        get_substream_seed("subscriptions", "trial_start_delay")
    )
    plan_rng = random.Random(
        get_substream_seed("subscriptions", "plan_choice")
    )
    paid_conversion_rng = random.Random(
        get_substream_seed("subscriptions", "paid_conversion")
    )
    cancellation_decision_rng = random.Random(
        get_substream_seed("subscriptions", "cancellation_decision")
    )
    cancellation_lead_rng = random.Random(
        get_substream_seed("subscriptions", "cancellation_lead")
    )
    payment_failure_rng = random.Random(
        get_substream_seed("subscriptions", "payment_failure")
    )
    payment_recovery_rng = random.Random(
        get_substream_seed("subscriptions", "payment_recovery")
    )

    plan_names = list(lifecycle["plan_mix"])
    plan_weights = [
        lifecycle["plan_mix"][name]
        for name in plan_names
    ]

    subscriptions: list[dict[str, Any]] = []
    transactions: list[dict[str, Any]] = []
    subscription_events: list[dict[str, Any]] = []

    for user in users:
        user_id = user["user_id"]
        profile = profiles[user_id]

        trial_started_at: datetime | None = None

        for paywall in profile["paywall_contexts"]:
            paywall_at = paywall["occurred_at"]
            if paywall_at < user["signed_up_at"]:
                continue

            probability = _trial_start_probability(
                user=user,
                paywall_at=paywall_at,
                sessions_before=paywall["sessions_before"],
                features_before=paywall["features_before"],
                lifecycle=lifecycle,
            )

            if trial_decision_rng.random() >= probability:
                continue

            delay_seconds = trial_delay_rng.randint(
                int(lifecycle["trial_start_delay_seconds_min"]),
                int(lifecycle["trial_start_delay_seconds_max"]),
            )
            candidate = paywall_at + timedelta(seconds=delay_seconds)
            if candidate >= snapshot_at:
                continue

            trial_started_at = candidate
            break

        if trial_started_at is None:
            continue

        subscription_id = _subscription_id_for_user(user_id)
        billing_period = plan_rng.choices(
            plan_names,
            weights=plan_weights,
            k=1,
        )[0]
        price_gbp = float(lifecycle["pricing_gbp"][billing_period])
        currency = str(lifecycle["payment"]["currency"])
        period_days = int(
            lifecycle["billing_period_days"][billing_period]
        )

        trial_ends_at = trial_started_at + timedelta(
            days=int(lifecycle["trial_length_days"])
        )

        subscription = {
            "subscription_id": subscription_id,
            "user_id": user_id,
            "installation_id": user["installation_id"],
            "billing_period": billing_period,
            "price_gbp": round(price_gbp, 2),
            "currency": currency,
            "status": "trialing",
            "trial_started_at": trial_started_at,
            "trial_ends_at": trial_ends_at,
            "subscription_started_at": None,
            "current_period_start_at": None,
            "current_period_end_at": None,
            "cancellation_requested_at": None,
            "expired_at": None,
            "auto_renew": True,
            "end_reason": None,
        }

        subscription_events.append(
            _subscription_event_row(
                event_name="trial_started",
                occurred_at=trial_started_at,
                user=user,
            )
        )

        if trial_ends_at >= snapshot_at:
            subscriptions.append(subscription)
            continue

        conversion_probability = _paid_conversion_probability(
            user=user,
            trial_started_at=trial_started_at,
            trial_ends_at=trial_ends_at,
            profile=profile,
            lifecycle=lifecycle,
        )

        if paid_conversion_rng.random() >= conversion_probability:
            subscription["status"] = "expired"
            subscription["auto_renew"] = False
            subscription["expired_at"] = trial_ends_at
            subscription["end_reason"] = "trial_no_conversion"
            subscription_events.append(
                _subscription_event_row(
                    event_name="subscription_expired",
                    occurred_at=trial_ends_at,
                    user=user,
                )
            )
            subscriptions.append(subscription)
            continue

        payment_result, payment_at = _attempt_payment(
            transactions=transactions,
            subscription_events=subscription_events,
            subscription_id=subscription_id,
            user=user,
            transaction_type="initial_charge",
            attempted_at=trial_ends_at,
            billing_period=billing_period,
            amount_gbp=price_gbp,
            currency=currency,
            billing_cycle_number=1,
            snapshot_at=snapshot_at,
            lifecycle=lifecycle,
            failure_rng=payment_failure_rng,
            recovery_rng=payment_recovery_rng,
        )

        if payment_result == "past_due":
            subscription["status"] = "past_due"
            subscriptions.append(subscription)
            continue

        if payment_result == "failed":
            subscription["status"] = "expired"
            subscription["auto_renew"] = False
            subscription["expired_at"] = payment_at
            subscription["end_reason"] = "payment_failure"
            subscription_events.append(
                _subscription_event_row(
                    event_name="subscription_expired",
                    occurred_at=payment_at,
                    user=user,
                )
            )
            subscriptions.append(subscription)
            continue

        if payment_at is None:
            raise RuntimeError("Successful initial payment has no timestamp")

        subscription["status"] = "active"
        subscription["subscription_started_at"] = payment_at
        subscription["current_period_start_at"] = payment_at
        subscription["current_period_end_at"] = (
            payment_at + timedelta(days=period_days)
        )
        subscription_events.append(
            _subscription_event_row(
                event_name="subscription_started",
                occurred_at=payment_at,
                user=user,
            )
        )

        next_billing_cycle_number = 2

        while True:
            period_start = subscription["current_period_start_at"]
            period_end = subscription["current_period_end_at"]
            if period_start is None or period_end is None:
                raise RuntimeError("Active subscription period is incomplete")

            cancellation = lifecycle["cancellation_probability"]
            earliest_observable_request = period_end - timedelta(
                days=int(cancellation["lead_days_max"])
            )

            if earliest_observable_request < snapshot_at:
                lead_days = cancellation_lead_rng.randint(
                    int(cancellation["lead_days_min"]),
                    int(cancellation["lead_days_max"]),
                )
                request_at = period_end - timedelta(days=lead_days)

                if request_at < period_start:
                    request_at = period_start

                if request_at < snapshot_at:
                    cancel_probability = _cancellation_probability(
                        billing_period=billing_period,
                        renewal_number=(
                            next_billing_cycle_number - 1
                        ),
                        decision_at=request_at,
                        profile=profile,
                        lifecycle=lifecycle,
                    )

                    if (
                        cancellation_decision_rng.random()
                        < cancel_probability
                    ):
                        subscription["status"] = (
                            "expired"
                            if period_end < snapshot_at
                            else "cancel_at_period_end"
                        )
                        subscription["auto_renew"] = False
                        subscription["cancellation_requested_at"] = request_at
                        subscription["end_reason"] = "voluntary_cancellation"
                        subscription_events.append(
                            _subscription_event_row(
                                event_name="cancellation_requested",
                                occurred_at=request_at,
                                user=user,
                            )
                        )

                        if period_end < snapshot_at:
                            subscription["expired_at"] = period_end
                            subscription_events.append(
                                _subscription_event_row(
                                    event_name="subscription_expired",
                                    occurred_at=period_end,
                                    user=user,
                                )
                            )
                        break

            if period_end >= snapshot_at:
                subscription["status"] = "active"
                break

            payment_result, payment_at = _attempt_payment(
                transactions=transactions,
                subscription_events=subscription_events,
                subscription_id=subscription_id,
                user=user,
                transaction_type="renewal",
                attempted_at=period_end,
                billing_period=billing_period,
                amount_gbp=price_gbp,
                currency=currency,
                billing_cycle_number=next_billing_cycle_number,
                snapshot_at=snapshot_at,
                lifecycle=lifecycle,
                failure_rng=payment_failure_rng,
                recovery_rng=payment_recovery_rng,
            )

            if payment_result == "past_due":
                subscription["status"] = "past_due"
                break

            if payment_result == "failed":
                subscription["status"] = "expired"
                subscription["auto_renew"] = False
                subscription["expired_at"] = payment_at
                subscription["end_reason"] = "payment_failure"
                subscription_events.append(
                    _subscription_event_row(
                        event_name="subscription_expired",
                        occurred_at=payment_at,
                        user=user,
                    )
                )
                break

            if payment_at is None:
                raise RuntimeError("Successful renewal has no timestamp")

            subscription["status"] = "active"
            subscription["current_period_start_at"] = payment_at
            subscription["current_period_end_at"] = (
                payment_at + timedelta(days=period_days)
            )
            subscription_events.append(
                _subscription_event_row(
                    event_name="subscription_renewed",
                    occurred_at=payment_at,
                    user=user,
                )
            )
            next_billing_cycle_number += 1

        subscriptions.append(subscription)

    subscriptions.sort(
        key=lambda row: (
            row["trial_started_at"],
            row["subscription_id"],
        )
    )

    transactions.sort(
        key=lambda row: (
            row["attempted_at"],
            row["subscription_id"],
            row["billing_cycle_number"],
            row["transaction_type"],
            row["attempt_number"],
        )
    )
    for number, transaction in enumerate(transactions, start=1):
        transaction["transaction_id"] = f"txn_{number:010d}"

    subscription_events.sort(
        key=lambda row: (
            row["occurred_at"],
            row["installation_id"],
            EVENT_SORT_PRIORITY[row["event_name"]],
        )
    )
    for number, event in enumerate(subscription_events, start=1):
        event["event_id"] = f"sevt_{number:010d}"

    return subscriptions, transactions, subscription_events


def merge_subscription_events(
    product_events: list[dict[str, Any]],
    subscription_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Return one chronologically sorted product-events entity.

    Source rows are copied. Existing event timestamps and payload values are
    preserved; event_id is re-numbered only in the merged output so the final
    entity has one deterministic primary-key sequence.
    """
    merged = [dict(row) for row in product_events]
    merged.extend(dict(row) for row in subscription_events)

    unknown_names = {
        row["event_name"]
        for row in merged
        if row["event_name"] not in EVENT_SORT_PRIORITY
    }
    if unknown_names:
        raise ValueError(
            f"Unknown event names for merge: {sorted(unknown_names)}"
        )

    merged.sort(
        key=lambda row: (
            row["occurred_at"],
            row["installation_id"],
            EVENT_SORT_PRIORITY[row["event_name"]],
            row.get("session_id") or "",
            row.get("feature_name") or "",
        )
    )

    for number, event in enumerate(merged, start=1):
        event["event_id"] = f"evt_{number:010d}"

    return merged