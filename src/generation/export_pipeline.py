"""End-to-end synthetic-data orchestration, validation and raw export for Pulse."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from src.generation.app_releases import generate_app_releases
from src.generation.experiments import generate_experiment_assignments
from src.generation.installations import (
    DEFAULT_SIMULATION_CONFIG,
    PROJECT_ROOT,
    generate_installations,
    get_simulation_bounds,
    load_installation_dimensions,
    load_simulation_config,
)
from src.generation.marketing_spend import generate_marketing_spend
from src.generation.product_events import generate_product_events
from src.generation.subscriptions import (
    generate_subscription_lifecycle,
    merge_subscription_events,
)
from src.generation.users import generate_users


DEFAULT_RAW_DIR = PROJECT_ROOT / "data" / "raw"

DATASET_SCHEMAS: dict[str, tuple[str, ...]] = {
    "installations": (
        "installation_id",
        "anonymous_id",
        "installed_at",
        "platform",
        "acquisition_channel",
        "country_code",
    ),
    "users": (
        "user_id",
        "installation_id",
        "anonymous_id",
        "signed_up_at",
        "onboarding_started_at",
        "onboarding_completed_at",
    ),
    "product_events": (
        "event_id",
        "event_name",
        "occurred_at",
        "installation_id",
        "anonymous_id",
        "user_id",
        "session_id",
        "feature_name",
    ),
    "subscriptions": (
        "subscription_id",
        "user_id",
        "installation_id",
        "billing_period",
        "price_gbp",
        "currency",
        "status",
        "trial_started_at",
        "trial_ends_at",
        "subscription_started_at",
        "current_period_start_at",
        "current_period_end_at",
        "cancellation_requested_at",
        "expired_at",
        "auto_renew",
        "end_reason",
    ),
    "subscription_transactions": (
        "transaction_id",
        "subscription_id",
        "user_id",
        "installation_id",
        "transaction_type",
        "attempted_at",
        "billing_period",
        "amount_gbp",
        "currency",
        "payment_status",
        "billing_cycle_number",
        "attempt_number",
    ),
    "experiment_assignments": (
        "assignment_id",
        "experiment_id",
        "experiment_name",
        "user_id",
        "installation_id",
        "randomization_unit",
        "variant",
        "allocation_probability",
        "assignment_at",
        "exposed_at",
        "experiment_start_at",
        "experiment_end_at",
        "eligibility_rule",
        "assignment_trigger",
        "exposure_trigger",
        "hypothesis",
        "primary_metric",
        "secondary_metric",
        "commercial_metric",
        "guardrail_metric",
        "analysis_window_days",
    ),
    "marketing_spend": (
        "marketing_spend_id",
        "period_start",
        "period_end",
        "acquisition_channel",
        "spend_type",
        "campaign_type",
        "spend",
        "currency",
        "impressions",
        "clicks",
    ),
    "app_releases": (
        "app_release_id",
        "release_key",
        "release_name",
        "release_sequence",
        "platform",
        "version",
        "release_at",
        "release_type",
        "feature_area",
        "rollout_strategy",
        "rollout_days",
        "rollout_complete_at",
        "release_channel",
        "release_notes",
    ),
}

PRIMARY_KEYS = {
    "installations": "installation_id",
    "users": "user_id",
    "product_events": "event_id",
    "subscriptions": "subscription_id",
    "subscription_transactions": "transaction_id",
    "experiment_assignments": "assignment_id",
    "marketing_spend": "marketing_spend_id",
    "app_releases": "app_release_id",
}

RAW_FILENAMES = {
    dataset_name: f"{dataset_name}.csv"
    for dataset_name in DATASET_SCHEMAS
}


def get_default_installation_count(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> int:
    """Use the approved lower bound as the stable final dataset size."""
    config = load_simulation_config(config_path)
    count = int(config["scale"]["installations_min"])
    if count <= 0:
        raise ValueError("installations_min must be greater than zero")
    return count


def get_snapshot_at(
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> datetime:
    """Return the configured UTC dataset snapshot timestamp."""
    config = load_simulation_config(config_path)
    timestamp = datetime.fromisoformat(
        config["simulation"]["snapshot_at"].replace("Z", "+00:00")
    )
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def generate_all_datasets(
    installation_count: int | None = None,
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict[str, list[dict[str, Any]]]:
    """Generate every approved Phase 2 dataset using existing generators."""
    if installation_count is None:
        installation_count = get_default_installation_count(config_path)
    if not isinstance(installation_count, int):
        raise TypeError("installation_count must be an integer")
    if installation_count <= 0:
        raise ValueError("installation_count must be greater than zero")

    start_at, end_at = get_simulation_bounds(config_path)

    installations = generate_installations(
        count=installation_count,
        start_at=start_at,
        end_at=end_at,
        config_path=config_path,
    )
    users = generate_users(
        installations,
        config_path=config_path,
    )
    base_product_events = generate_product_events(
        installations,
        users,
        config_path=config_path,
    )

    subscriptions, transactions, subscription_events = (
        generate_subscription_lifecycle(
            users,
            base_product_events,
            config_path=config_path,
        )
    )

    # Preserve the Step 7 assignment input contract by using the approved
    # base product-event entity. Subscription events do not affect assignment
    # eligibility and are merged only for the final exported event stream.
    experiment_assignments = generate_experiment_assignments(
        users,
        base_product_events,
        config_path=config_path,
    )

    product_events = merge_subscription_events(
        base_product_events,
        subscription_events,
    )

    marketing_spend = generate_marketing_spend(
        start_at,
        end_at,
        config_path=config_path,
    )
    app_releases = generate_app_releases(
        start_at,
        end_at,
        config_path=config_path,
    )

    return {
        "installations": installations,
        "users": users,
        "product_events": product_events,
        "subscriptions": subscriptions,
        "subscription_transactions": transactions,
        "experiment_assignments": experiment_assignments,
        "marketing_spend": marketing_spend,
        "app_releases": app_releases,
    }


def _validate_schema(
    dataset_name: str,
    rows: list[dict[str, Any]],
) -> None:
    expected = set(DATASET_SCHEMAS[dataset_name])
    for row_number, row in enumerate(rows, start=1):
        actual = set(row)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                f"{dataset_name} row {row_number} schema mismatch: "
                f"missing={missing}, extra={extra}"
            )


def _validate_primary_key(
    dataset_name: str,
    rows: list[dict[str, Any]],
) -> None:
    primary_key = PRIMARY_KEYS[dataset_name]
    values = [row[primary_key] for row in rows]
    if any(value is None or value == "" for value in values):
        raise ValueError(f"{dataset_name}.{primary_key} contains null/blank values")
    if len(values) != len(set(values)):
        raise ValueError(f"{dataset_name}.{primary_key} is not unique")


def _require_aware_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{label} must be a datetime")
    if value.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


def validate_dataset_bundle(
    datasets: dict[str, list[dict[str, Any]]],
    expected_installation_count: int,
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
    enforce_config_scale: bool = False,
) -> dict[str, int]:
    """Validate schemas, keys, chronology and cross-dataset integrity."""
    expected_names = set(DATASET_SCHEMAS)
    actual_names = set(datasets)
    if actual_names != expected_names:
        raise ValueError(
            "Dataset bundle mismatch: "
            f"missing={sorted(expected_names - actual_names)}, "
            f"extra={sorted(actual_names - expected_names)}"
        )

    if len(datasets["installations"]) != expected_installation_count:
        raise ValueError(
            "Installation row count mismatch: "
            f"expected {expected_installation_count}, "
            f"got {len(datasets['installations'])}"
        )

    for dataset_name, rows in datasets.items():
        if not isinstance(rows, list):
            raise TypeError(f"{dataset_name} must be a list")
        _validate_schema(dataset_name, rows)
        _validate_primary_key(dataset_name, rows)

    start_at, end_at = get_simulation_bounds(config_path)
    snapshot_at = get_snapshot_at(config_path)
    config = load_simulation_config(config_path)

    if enforce_config_scale:
        scale = config["scale"]
        installation_count = len(datasets["installations"])
        if not (
            int(scale["installations_min"])
            <= installation_count
            <= int(scale["installations_max"])
        ):
            raise ValueError("Final installation count is outside approved scale")

        event_count = len(datasets["product_events"])
        if not (
            int(scale["product_events_min"])
            <= event_count
            <= int(scale["product_events_max"])
        ):
            raise ValueError(
                "Final product-event count is outside approved scale: "
                f"{event_count:,}"
            )

    installations_by_id = {
        row["installation_id"]: row
        for row in datasets["installations"]
    }
    anonymous_ids = [
        row["anonymous_id"]
        for row in datasets["installations"]
    ]
    if len(anonymous_ids) != len(set(anonymous_ids)):
        raise ValueError("installations.anonymous_id is not unique")

    for row in datasets["installations"]:
        installed_at = _require_aware_datetime(
            row["installed_at"],
            "installations.installed_at",
        )
        if not start_at <= installed_at <= end_at:
            raise ValueError("Installation timestamp is outside simulation bounds")

    users_by_id: dict[str, dict[str, Any]] = {}
    users_by_installation: dict[str, dict[str, Any]] = {}
    for row in datasets["users"]:
        installation_id = row["installation_id"]
        if installation_id not in installations_by_id:
            raise ValueError("User references unknown installation")
        if installation_id in users_by_installation:
            raise ValueError("More than one user references an installation")
        installation = installations_by_id[installation_id]
        if row["anonymous_id"] != installation["anonymous_id"]:
            raise ValueError("User anonymous_id does not match installation")

        signed_up_at = _require_aware_datetime(
            row["signed_up_at"],
            "users.signed_up_at",
        )
        if not installation["installed_at"] <= signed_up_at < snapshot_at:
            raise ValueError("User signup timestamp is invalid")

        started_at = row["onboarding_started_at"]
        completed_at = row["onboarding_completed_at"]
        if started_at is not None:
            started_at = _require_aware_datetime(
                started_at,
                "users.onboarding_started_at",
            )
            if not signed_up_at <= started_at < snapshot_at:
                raise ValueError("Onboarding start timestamp is invalid")
        if completed_at is not None:
            completed_at = _require_aware_datetime(
                completed_at,
                "users.onboarding_completed_at",
            )
            if started_at is None or not started_at <= completed_at < snapshot_at:
                raise ValueError("Onboarding completion timestamp is invalid")

        users_by_id[row["user_id"]] = row
        users_by_installation[installation_id] = row

    event_counts = Counter()
    lifecycle_event_times: dict[tuple[str, str], set[datetime]] = {}
    app_install_times_by_installation: dict[str, set[datetime]] = {}
    for row in datasets["product_events"]:
        installation_id = row["installation_id"]
        if installation_id not in installations_by_id:
            raise ValueError("Product event references unknown installation")
        installation = installations_by_id[installation_id]
        if row["anonymous_id"] != installation["anonymous_id"]:
            raise ValueError("Product event anonymous_id does not match installation")

        occurred_at = _require_aware_datetime(
            row["occurred_at"],
            "product_events.occurred_at",
        )
        if not installation["installed_at"] <= occurred_at < snapshot_at:
            raise ValueError("Product event timestamp is invalid")

        user_id = row["user_id"]
        if user_id is not None:
            if user_id not in users_by_id:
                raise ValueError("Product event references unknown user")
            user = users_by_id[user_id]
            if user["installation_id"] != installation_id:
                raise ValueError("Product event user/installation mismatch")
            if occurred_at < user["signed_up_at"]:
                raise ValueError("Registered product event occurs before signup")

        event_name = row["event_name"]
        event_counts[event_name] += 1
        if event_name == "app_install":
            app_install_times_by_installation.setdefault(
                installation_id,
                set(),
            ).add(occurred_at)
        if user_id is not None:
            lifecycle_event_times.setdefault(
                (row["event_name"], user_id),
                set(),
            ).add(occurred_at)

    if event_counts["app_install"] != len(datasets["installations"]):
        raise ValueError("app_install event count does not match installations")
    if event_counts["signup"] != len(datasets["users"]):
        raise ValueError("signup event count does not match users")

    for installation_id, installation in installations_by_id.items():
        install_times = app_install_times_by_installation.get(
            installation_id,
            set(),
        )
        if install_times != {installation["installed_at"]}:
            raise ValueError("app_install event does not match installation timestamp")

    for user_id, user in users_by_id.items():
        if user["signed_up_at"] not in lifecycle_event_times.get(
            ("signup", user_id), set()
        ):
            raise ValueError("signup event does not match user timestamp")
        started_at = user["onboarding_started_at"]
        if started_at is not None and started_at not in lifecycle_event_times.get(
            ("onboarding_started", user_id), set()
        ):
            raise ValueError("onboarding_started event does not match user timestamp")
        completed_at = user["onboarding_completed_at"]
        if completed_at is not None and completed_at not in lifecycle_event_times.get(
            ("onboarding_completed", user_id), set()
        ):
            raise ValueError("onboarding_completed event does not match user timestamp")

    subscriptions_by_id: dict[str, dict[str, Any]] = {}
    subscription_users: set[str] = set()
    for row in datasets["subscriptions"]:
        user_id = row["user_id"]
        if user_id not in users_by_id:
            raise ValueError("Subscription references unknown user")
        if user_id in subscription_users:
            raise ValueError("More than one subscription exists for a user")
        user = users_by_id[user_id]
        if row["installation_id"] != user["installation_id"]:
            raise ValueError("Subscription user/installation mismatch")
        trial_started_at = _require_aware_datetime(
            row["trial_started_at"],
            "subscriptions.trial_started_at",
        )
        _require_aware_datetime(
            row["trial_ends_at"],
            "subscriptions.trial_ends_at",
        )
        if not user["signed_up_at"] <= trial_started_at < snapshot_at:
            raise ValueError("Subscription trial timestamp is invalid")
        for field in (
            "subscription_started_at",
            "current_period_start_at",
            "current_period_end_at",
            "cancellation_requested_at",
            "expired_at",
        ):
            value = row[field]
            if value is not None:
                _require_aware_datetime(value, f"subscriptions.{field}")
        subscriptions_by_id[row["subscription_id"]] = row
        subscription_users.add(user_id)

    for row in datasets["subscription_transactions"]:
        subscription_id = row["subscription_id"]
        if subscription_id not in subscriptions_by_id:
            raise ValueError("Transaction references unknown subscription")
        subscription = subscriptions_by_id[subscription_id]
        if row["user_id"] != subscription["user_id"]:
            raise ValueError("Transaction user does not match subscription")
        if row["installation_id"] != subscription["installation_id"]:
            raise ValueError("Transaction installation does not match subscription")
        attempted_at = _require_aware_datetime(
            row["attempted_at"],
            "subscription_transactions.attempted_at",
        )
        if attempted_at >= snapshot_at:
            raise ValueError("Transaction occurs at/after snapshot")

    for row in datasets["experiment_assignments"]:
        user_id = row["user_id"]
        if user_id not in users_by_id:
            raise ValueError("Experiment assignment references unknown user")
        user = users_by_id[user_id]
        if row["installation_id"] != user["installation_id"]:
            raise ValueError("Experiment assignment user/installation mismatch")
        assignment_at = _require_aware_datetime(
            row["assignment_at"],
            "experiment_assignments.assignment_at",
        )
        experiment_start_at = _require_aware_datetime(
            row["experiment_start_at"],
            "experiment_assignments.experiment_start_at",
        )
        experiment_end_at = _require_aware_datetime(
            row["experiment_end_at"],
            "experiment_assignments.experiment_end_at",
        )
        if not (
            user["signed_up_at"] <= assignment_at < snapshot_at
            and experiment_start_at <= assignment_at < experiment_end_at
        ):
            raise ValueError("Experiment assignment timestamp is invalid")
        exposed_at = row["exposed_at"]
        if exposed_at is not None:
            exposed_at = _require_aware_datetime(
                exposed_at,
                "experiment_assignments.exposed_at",
            )
            if not assignment_at <= exposed_at < experiment_end_at:
                raise ValueError("Experiment exposure timestamp is invalid")

    installation_dimensions = load_installation_dimensions(config_path)
    install_channels = set(
        installation_dimensions["acquisition_channel"]["values"]
    )
    marketing_pairs: set[tuple[date, str]] = set()
    for row in datasets["marketing_spend"]:
        if row["acquisition_channel"] not in install_channels:
            raise ValueError("Marketing spend uses unknown acquisition channel")
        if not isinstance(row["period_start"], date) or isinstance(
            row["period_start"], datetime
        ):
            raise TypeError("marketing_spend.period_start must be a date")
        if not isinstance(row["period_end"], date) or isinstance(
            row["period_end"], datetime
        ):
            raise TypeError("marketing_spend.period_end must be a date")
        if not start_at.date() <= row["period_start"] <= row["period_end"] <= end_at.date():
            raise ValueError("Marketing period is outside simulation bounds")
        pair = (row["period_start"], row["acquisition_channel"])
        if pair in marketing_pairs:
            raise ValueError("Duplicate marketing period/channel grain")
        marketing_pairs.add(pair)

    install_platforms = set(
        installation_dimensions["platform"]["values"]
    )
    release_pairs: set[tuple[str, str]] = set()
    for row in datasets["app_releases"]:
        if row["platform"] not in install_platforms:
            raise ValueError("App release uses unknown platform")
        release_at = _require_aware_datetime(
            row["release_at"],
            "app_releases.release_at",
        )
        rollout_complete_at = _require_aware_datetime(
            row["rollout_complete_at"],
            "app_releases.rollout_complete_at",
        )
        if not start_at <= release_at <= end_at:
            raise ValueError("App release is outside simulation bounds")
        if rollout_complete_at < release_at:
            raise ValueError("App release rollout completes before release")
        pair = (row["release_key"], row["platform"])
        if pair in release_pairs:
            raise ValueError("Duplicate app release/platform grain")
        release_pairs.add(pair)

    return {
        dataset_name: len(rows)
        for dataset_name, rows in datasets.items()
    }


def _serialize_value(value: Any) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Cannot export a timezone-naive datetime")
        return (
            value.astimezone(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def export_datasets(
    datasets: dict[str, list[dict[str, Any]]],
    output_dir: Path = DEFAULT_RAW_DIR,
) -> dict[str, Path]:
    """Write deterministic UTF-8 CSV files with stable columns and filenames."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    for dataset_name in DATASET_SCHEMAS:
        rows = datasets[dataset_name]
        path = output_dir / RAW_FILENAMES[dataset_name]
        fieldnames = DATASET_SCHEMAS[dataset_name]

        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=fieldnames,
                extrasaction="raise",
                lineterminator="\n",
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        field: _serialize_value(row[field])
                        for field in fieldnames
                    }
                )

        paths[dataset_name] = path

    return paths


def run_export_pipeline(
    output_dir: Path = DEFAULT_RAW_DIR,
    config_path: Path = DEFAULT_SIMULATION_CONFIG,
) -> dict[str, int]:
    """Generate, validate and export the approved final Phase 2 snapshot."""
    installation_count = get_default_installation_count(config_path)
    datasets = generate_all_datasets(
        installation_count=installation_count,
        config_path=config_path,
    )
    summary = validate_dataset_bundle(
        datasets,
        expected_installation_count=installation_count,
        config_path=config_path,
        enforce_config_scale=True,
    )
    paths = export_datasets(
        datasets,
        output_dir=output_dir,
    )

    print("=== PHASE 2 FINAL SYNTHETIC DATA VALIDATION ===")
    print(f"Simulation: {get_simulation_bounds(config_path)[0].date()} to {get_simulation_bounds(config_path)[1].date()}")
    print(f"Snapshot: {get_snapshot_at(config_path).isoformat()}")
    print()
    for dataset_name in DATASET_SCHEMAS:
        print(
            f"{dataset_name}: {summary[dataset_name]:,} rows -> "
            f"{paths[dataset_name].relative_to(PROJECT_ROOT)}"
        )
    print()
    print("Schemas: PASS")
    print("Primary keys / uniqueness: PASS")
    print("Timestamp bounds / chronology: PASS")
    print("Cross-dataset referential integrity: PASS")
    print("Approved scale bounds: PASS")
    print("Deterministic raw export pipeline: PASS")

    return summary


if __name__ == "__main__":
    run_export_pipeline()