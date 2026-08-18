"""PostgreSQL warehouse validation for succeeded Pulse raw batches."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Any

from psycopg.types.json import Jsonb

from src.ingestion.database import connect_database
from src.validation.field_schema import DATASET_FIELD_RULES


class PostgresValidationError(RuntimeError):
    """Raised when PostgreSQL validation cannot be completed safely."""


@dataclass(frozen=True)
class ValidationCheck:
    """One deterministic warehouse validation check."""

    name: str
    category: str
    dataset_name: str | None
    description: str
    query: str
    params: tuple[Any, ...] = ()
    severity: str = "error"


@dataclass(frozen=True)
class ValidationRunResult:
    """Summary of one PostgreSQL validation run."""

    validation_run_id: int
    ingestion_batch_id: int
    snapshot_id: str
    status: str
    expected_check_count: int
    completed_check_count: int
    passed_check_count: int
    failed_check_count: int
    already_validated: bool
    failures: tuple[tuple[str, int], ...] = ()


DATASETS = tuple(DATASET_FIELD_RULES)

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

_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


def _identifier(value: str) -> str:
    """Validate an internal SQL identifier before interpolation."""

    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(
            f"Unsafe internal SQL identifier: {value!r}"
        )
    return value


def _reconciliation_checks() -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []

    for dataset_name in DATASETS:
        checks.append(
            ValidationCheck(
                name=f"{dataset_name}_raw_reconciliation",
                category="reconciliation",
                dataset_name=dataset_name,
                description=(
                    "Raw table row count must reconcile exactly "
                    "with ingestion-file metadata."
                ),
                query="""
                    SELECT
                        CASE
                            WHEN COUNT(*) = 1
                             AND COALESCE(
                                    MAX(
                                        ABS(
                                            accepted_vs_actual_delta
                                        )
                                    ),
                                    1
                                 ) = 0
                             AND COALESCE(
                                    MAX(
                                        ABS(
                                            expected_vs_processed_delta
                                        )
                                    ),
                                    1
                                 ) = 0
                             AND COALESCE(
                                    BOOL_AND(reconciled),
                                    FALSE
                                 )
                            THEN 0
                            ELSE 1
                        END::BIGINT
                    FROM validation.raw_reconciliation
                    WHERE ingestion_batch_id = %s
                      AND dataset_name = %s
                """,
                params=(dataset_name,),
            )
        )

    checks.extend(
        [
            ValidationCheck(
                name="app_install_event_count_matches_installations",
                category="reconciliation",
                dataset_name="product_events",
                description=(
                    "There must be exactly one app_install event "
                    "per installation in aggregate."
                ),
                query="""
                    SELECT ABS(
                        (
                            SELECT COUNT(*)
                            FROM raw.product_events
                            WHERE ingestion_batch_id = %s
                              AND event_name = 'app_install'
                        )
                        -
                        (
                            SELECT COUNT(*)
                            FROM raw.installations
                            WHERE ingestion_batch_id = %s
                        )
                    )::BIGINT
                """,
                params=(),
            ),
            ValidationCheck(
                name="signup_event_count_matches_users",
                category="reconciliation",
                dataset_name="product_events",
                description=(
                    "Signup event count must equal registered-user count."
                ),
                query="""
                    SELECT ABS(
                        (
                            SELECT COUNT(*)
                            FROM raw.product_events
                            WHERE ingestion_batch_id = %s
                              AND event_name = 'signup'
                        )
                        -
                        (
                            SELECT COUNT(*)
                            FROM raw.users
                            WHERE ingestion_batch_id = %s
                        )
                    )::BIGINT
                """,
            ),
            ValidationCheck(
                name="trial_started_event_count_matches_subscriptions",
                category="reconciliation",
                dataset_name="product_events",
                description=(
                    "Trial-start event count must equal subscription count."
                ),
                query="""
                    SELECT ABS(
                        (
                            SELECT COUNT(*)
                            FROM raw.product_events
                            WHERE ingestion_batch_id = %s
                              AND event_name = 'trial_started'
                        )
                        -
                        (
                            SELECT COUNT(*)
                            FROM raw.subscriptions
                            WHERE ingestion_batch_id = %s
                        )
                    )::BIGINT
                """,
            ),
            ValidationCheck(
                name="subscription_started_event_count_matches_charges",
                category="reconciliation",
                dataset_name="product_events",
                description=(
                    "Subscription-started events must reconcile with "
                    "successful initial charges."
                ),
                query="""
                    SELECT ABS(
                        (
                            SELECT COUNT(*)
                            FROM raw.product_events
                            WHERE ingestion_batch_id = %s
                              AND event_name = 'subscription_started'
                        )
                        -
                        (
                            SELECT COUNT(*)
                            FROM raw.subscription_transactions
                            WHERE ingestion_batch_id = %s
                              AND transaction_type = 'initial_charge'
                              AND payment_status = 'succeeded'
                        )
                    )::BIGINT
                """,
            ),
            ValidationCheck(
                name="subscription_renewed_event_count_matches_charges",
                category="reconciliation",
                dataset_name="product_events",
                description=(
                    "Subscription-renewed events must reconcile with "
                    "successful renewal charges."
                ),
                query="""
                    SELECT ABS(
                        (
                            SELECT COUNT(*)
                            FROM raw.product_events
                            WHERE ingestion_batch_id = %s
                              AND event_name = 'subscription_renewed'
                        )
                        -
                        (
                            SELECT COUNT(*)
                            FROM raw.subscription_transactions
                            WHERE ingestion_batch_id = %s
                              AND transaction_type = 'renewal'
                              AND payment_status = 'succeeded'
                        )
                    )::BIGINT
                """,
            ),
            ValidationCheck(
                name="payment_failed_event_count_matches_transactions",
                category="reconciliation",
                dataset_name="product_events",
                description=(
                    "Payment-failed events must reconcile with "
                    "failed payment attempts."
                ),
                query="""
                    SELECT ABS(
                        (
                            SELECT COUNT(*)
                            FROM raw.product_events
                            WHERE ingestion_batch_id = %s
                              AND event_name = 'payment_failed'
                        )
                        -
                        (
                            SELECT COUNT(*)
                            FROM raw.subscription_transactions
                            WHERE ingestion_batch_id = %s
                              AND payment_status = 'failed'
                        )
                    )::BIGINT
                """,
            ),
            ValidationCheck(
                name="installation_app_install_timestamp_match",
                category="reconciliation",
                dataset_name="installations",
                description=(
                    "Every installation must have an app_install event "
                    "at the installation timestamp."
                ),
                query="""
                    SELECT COUNT(*)::BIGINT
                    FROM raw.installations AS i
                    WHERE i.ingestion_batch_id = %s
                      AND NOT EXISTS (
                          SELECT 1
                          FROM raw.product_events AS e
                          WHERE e.ingestion_batch_id
                                = i.ingestion_batch_id
                            AND e.installation_id
                                = i.installation_id
                            AND e.event_name = 'app_install'
                            AND e.occurred_at
                                = i.installed_at
                      )
                """,
            ),
            ValidationCheck(
                name="user_signup_event_timestamp_match",
                category="reconciliation",
                dataset_name="users",
                description=(
                    "Every user must have a signup event "
                    "at signed_up_at."
                ),
                query="""
                    SELECT COUNT(*)::BIGINT
                    FROM raw.users AS u
                    WHERE u.ingestion_batch_id = %s
                      AND NOT EXISTS (
                          SELECT 1
                          FROM raw.product_events AS e
                          WHERE e.ingestion_batch_id
                                = u.ingestion_batch_id
                            AND e.user_id = u.user_id
                            AND e.event_name = 'signup'
                            AND e.occurred_at
                                = u.signed_up_at
                      )
                """,
            ),
            ValidationCheck(
                name="user_onboarding_started_event_timestamp_match",
                category="reconciliation",
                dataset_name="users",
                description=(
                    "Persisted onboarding-start timestamps must have "
                    "matching lifecycle events."
                ),
                query="""
                    SELECT COUNT(*)::BIGINT
                    FROM raw.users AS u
                    WHERE u.ingestion_batch_id = %s
                      AND u.onboarding_started_at IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1
                          FROM raw.product_events AS e
                          WHERE e.ingestion_batch_id
                                = u.ingestion_batch_id
                            AND e.user_id = u.user_id
                            AND e.event_name = 'onboarding_started'
                            AND e.occurred_at
                                = u.onboarding_started_at
                      )
                """,
            ),
            ValidationCheck(
                name="user_onboarding_completed_event_timestamp_match",
                category="reconciliation",
                dataset_name="users",
                description=(
                    "Persisted onboarding-completion timestamps must have "
                    "matching lifecycle events."
                ),
                query="""
                    SELECT COUNT(*)::BIGINT
                    FROM raw.users AS u
                    WHERE u.ingestion_batch_id = %s
                      AND u.onboarding_completed_at IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1
                          FROM raw.product_events AS e
                          WHERE e.ingestion_batch_id
                                = u.ingestion_batch_id
                            AND e.user_id = u.user_id
                            AND e.event_name = 'onboarding_completed'
                            AND e.occurred_at
                                = u.onboarding_completed_at
                      )
                """,
            ),
        ]
    )

    return checks


def _uniqueness_checks() -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []

    for dataset_name, primary_key in PRIMARY_KEYS.items():
        table = _identifier(dataset_name)
        key = _identifier(primary_key)

        checks.append(
            ValidationCheck(
                name=f"{dataset_name}_{primary_key}_unique",
                category="uniqueness",
                dataset_name=dataset_name,
                description=(
                    f"{dataset_name}.{primary_key} must be unique "
                    "inside one ingestion batch."
                ),
                query=f"""
                    SELECT (
                        COUNT(*)
                        - COUNT(DISTINCT {key})
                    )::BIGINT
                    FROM raw.{table}
                    WHERE ingestion_batch_id = %s
                """,
            )
        )

    checks.extend(
        [
            ValidationCheck(
                name="installations_anonymous_id_unique",
                category="uniqueness",
                dataset_name="installations",
                description=(
                    "Installation anonymous identifiers must be unique."
                ),
                query="""
                    SELECT (
                        COUNT(*)
                        - COUNT(DISTINCT anonymous_id)
                    )::BIGINT
                    FROM raw.installations
                    WHERE ingestion_batch_id = %s
                """,
            ),
            ValidationCheck(
                name="users_installation_id_unique",
                category="uniqueness",
                dataset_name="users",
                description=(
                    "At most one registered user may belong "
                    "to an installation."
                ),
                query="""
                    SELECT (
                        COUNT(*)
                        - COUNT(DISTINCT installation_id)
                    )::BIGINT
                    FROM raw.users
                    WHERE ingestion_batch_id = %s
                """,
            ),
            ValidationCheck(
                name="subscriptions_user_id_unique",
                category="uniqueness",
                dataset_name="subscriptions",
                description=(
                    "At most one subscription lifecycle may belong "
                    "to a user."
                ),
                query="""
                    SELECT (
                        COUNT(*)
                        - COUNT(DISTINCT user_id)
                    )::BIGINT
                    FROM raw.subscriptions
                    WHERE ingestion_batch_id = %s
                """,
            ),
            ValidationCheck(
                name="marketing_spend_period_channel_unique",
                category="uniqueness",
                dataset_name="marketing_spend",
                description=(
                    "Marketing spend grain is period_start "
                    "plus acquisition_channel."
                ),
                query="""
                    SELECT (
                        COUNT(*)
                        - COUNT(
                            DISTINCT (
                                period_start,
                                acquisition_channel
                            )
                        )
                    )::BIGINT
                    FROM raw.marketing_spend
                    WHERE ingestion_batch_id = %s
                """,
            ),
            ValidationCheck(
                name="app_releases_release_key_platform_unique",
                category="uniqueness",
                dataset_name="app_releases",
                description=(
                    "App-release grain is release_key plus platform."
                ),
                query="""
                    SELECT (
                        COUNT(*)
                        - COUNT(
                            DISTINCT (
                                release_key,
                                platform
                            )
                        )
                    )::BIGINT
                    FROM raw.app_releases
                    WHERE ingestion_batch_id = %s
                """,
            ),
        ]
    )

    return checks


def _referential_checks() -> list[ValidationCheck]:
    return [
        ValidationCheck(
            name="users_reference_installations",
            category="referential_integrity",
            dataset_name="users",
            description="Every user must reference an installation.",
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.users AS u
                WHERE u.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.installations AS i
                      WHERE i.ingestion_batch_id
                            = u.ingestion_batch_id
                        AND i.installation_id
                            = u.installation_id
                  )
            """,
        ),
        ValidationCheck(
            name="users_anonymous_id_matches_installation",
            category="referential_integrity",
            dataset_name="users",
            description=(
                "User anonymous_id must match its installation."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.users AS u
                WHERE u.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.installations AS i
                      WHERE i.ingestion_batch_id
                            = u.ingestion_batch_id
                        AND i.installation_id
                            = u.installation_id
                        AND i.anonymous_id
                            = u.anonymous_id
                  )
            """,
        ),
        ValidationCheck(
            name="product_events_reference_installations",
            category="referential_integrity",
            dataset_name="product_events",
            description=(
                "Every product event must reference an installation."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.product_events AS e
                WHERE e.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.installations AS i
                      WHERE i.ingestion_batch_id
                            = e.ingestion_batch_id
                        AND i.installation_id
                            = e.installation_id
                  )
            """,
        ),
        ValidationCheck(
            name="product_events_anonymous_id_matches_installation",
            category="referential_integrity",
            dataset_name="product_events",
            description=(
                "Product-event anonymous_id must match its installation."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.product_events AS e
                WHERE e.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.installations AS i
                      WHERE i.ingestion_batch_id
                            = e.ingestion_batch_id
                        AND i.installation_id
                            = e.installation_id
                        AND i.anonymous_id
                            = e.anonymous_id
                  )
            """,
        ),
        ValidationCheck(
            name="product_events_reference_users_when_present",
            category="referential_integrity",
            dataset_name="product_events",
            description=(
                "Non-null product-event user_id values "
                "must reference users."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.product_events AS e
                WHERE e.ingestion_batch_id = %s
                  AND e.user_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.users AS u
                      WHERE u.ingestion_batch_id
                            = e.ingestion_batch_id
                        AND u.user_id = e.user_id
                  )
            """,
        ),
        ValidationCheck(
            name="product_events_user_installation_match",
            category="referential_integrity",
            dataset_name="product_events",
            description=(
                "Registered product events must use the user's "
                "installation."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.product_events AS e
                WHERE e.ingestion_batch_id = %s
                  AND e.user_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.users AS u
                      WHERE u.ingestion_batch_id
                            = e.ingestion_batch_id
                        AND u.user_id = e.user_id
                        AND u.installation_id
                            = e.installation_id
                  )
            """,
        ),
        ValidationCheck(
            name="subscriptions_reference_users",
            category="referential_integrity",
            dataset_name="subscriptions",
            description="Every subscription must reference a user.",
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.subscriptions AS s
                WHERE s.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.users AS u
                      WHERE u.ingestion_batch_id
                            = s.ingestion_batch_id
                        AND u.user_id = s.user_id
                  )
            """,
        ),
        ValidationCheck(
            name="subscriptions_user_installation_match",
            category="referential_integrity",
            dataset_name="subscriptions",
            description=(
                "Subscription installation_id must match its user."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.subscriptions AS s
                WHERE s.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.users AS u
                      WHERE u.ingestion_batch_id
                            = s.ingestion_batch_id
                        AND u.user_id = s.user_id
                        AND u.installation_id
                            = s.installation_id
                  )
            """,
        ),
        ValidationCheck(
            name="transactions_reference_subscriptions",
            category="referential_integrity",
            dataset_name="subscription_transactions",
            description=(
                "Every transaction must reference a subscription."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.subscription_transactions AS t
                WHERE t.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.subscriptions AS s
                      WHERE s.ingestion_batch_id
                            = t.ingestion_batch_id
                        AND s.subscription_id
                            = t.subscription_id
                  )
            """,
        ),
        ValidationCheck(
            name="transactions_user_matches_subscription",
            category="referential_integrity",
            dataset_name="subscription_transactions",
            description=(
                "Transaction user_id must match its subscription."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.subscription_transactions AS t
                WHERE t.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.subscriptions AS s
                      WHERE s.ingestion_batch_id
                            = t.ingestion_batch_id
                        AND s.subscription_id
                            = t.subscription_id
                        AND s.user_id = t.user_id
                  )
            """,
        ),
        ValidationCheck(
            name="transactions_installation_matches_subscription",
            category="referential_integrity",
            dataset_name="subscription_transactions",
            description=(
                "Transaction installation_id must match "
                "its subscription."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.subscription_transactions AS t
                WHERE t.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.subscriptions AS s
                      WHERE s.ingestion_batch_id
                            = t.ingestion_batch_id
                        AND s.subscription_id
                            = t.subscription_id
                        AND s.installation_id
                            = t.installation_id
                  )
            """,
        ),
        ValidationCheck(
            name="experiment_assignments_reference_users",
            category="referential_integrity",
            dataset_name="experiment_assignments",
            description=(
                "Every experiment assignment must reference a user."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.experiment_assignments AS a
                WHERE a.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.users AS u
                      WHERE u.ingestion_batch_id
                            = a.ingestion_batch_id
                        AND u.user_id = a.user_id
                  )
            """,
        ),
        ValidationCheck(
            name="experiment_assignments_user_installation_match",
            category="referential_integrity",
            dataset_name="experiment_assignments",
            description=(
                "Experiment assignment installation_id "
                "must match its user."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.experiment_assignments AS a
                WHERE a.ingestion_batch_id = %s
                  AND NOT EXISTS (
                      SELECT 1
                      FROM raw.users AS u
                      WHERE u.ingestion_batch_id
                            = a.ingestion_batch_id
                        AND u.user_id = a.user_id
                        AND u.installation_id
                            = a.installation_id
                  )
            """,
        ),
    ]


def _chronology_checks() -> list[ValidationCheck]:
    return [
        ValidationCheck(
            name="users_signup_not_before_installation",
            category="chronology",
            dataset_name="users",
            description="User signup cannot precede installation.",
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.users AS u
                JOIN raw.installations AS i
                  ON i.ingestion_batch_id = u.ingestion_batch_id
                 AND i.installation_id = u.installation_id
                WHERE u.ingestion_batch_id = %s
                  AND u.signed_up_at < i.installed_at
            """,
        ),
        ValidationCheck(
            name="users_onboarding_start_not_before_signup",
            category="chronology",
            dataset_name="users",
            description=(
                "Onboarding start cannot precede user signup."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.users
                WHERE ingestion_batch_id = %s
                  AND onboarding_started_at IS NOT NULL
                  AND onboarding_started_at < signed_up_at
            """,
        ),
        ValidationCheck(
            name="users_onboarding_completion_valid",
            category="chronology",
            dataset_name="users",
            description=(
                "Onboarding completion requires a start timestamp "
                "and cannot precede it."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.users
                WHERE ingestion_batch_id = %s
                  AND onboarding_completed_at IS NOT NULL
                  AND (
                      onboarding_started_at IS NULL
                      OR onboarding_completed_at
                         < onboarding_started_at
                  )
            """,
        ),
        ValidationCheck(
            name="product_events_not_before_installation",
            category="chronology",
            dataset_name="product_events",
            description=(
                "Product events cannot precede installation."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.product_events AS e
                JOIN raw.installations AS i
                  ON i.ingestion_batch_id = e.ingestion_batch_id
                 AND i.installation_id = e.installation_id
                WHERE e.ingestion_batch_id = %s
                  AND e.occurred_at < i.installed_at
            """,
        ),
        ValidationCheck(
            name="registered_product_events_not_before_signup",
            category="chronology",
            dataset_name="product_events",
            description=(
                "Events attached to registered users "
                "cannot precede signup."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.product_events AS e
                JOIN raw.users AS u
                  ON u.ingestion_batch_id = e.ingestion_batch_id
                 AND u.user_id = e.user_id
                WHERE e.ingestion_batch_id = %s
                  AND e.user_id IS NOT NULL
                  AND e.occurred_at < u.signed_up_at
            """,
        ),
        ValidationCheck(
            name="subscription_trial_not_before_signup",
            category="chronology",
            dataset_name="subscriptions",
            description=(
                "Subscription trial start cannot precede signup."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.subscriptions AS s
                JOIN raw.users AS u
                  ON u.ingestion_batch_id = s.ingestion_batch_id
                 AND u.user_id = s.user_id
                WHERE s.ingestion_batch_id = %s
                  AND s.trial_started_at < u.signed_up_at
            """,
        ),
        ValidationCheck(
            name="experiment_assignment_not_before_signup",
            category="chronology",
            dataset_name="experiment_assignments",
            description=(
                "Experiment assignment cannot precede signup."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.experiment_assignments AS a
                JOIN raw.users AS u
                  ON u.ingestion_batch_id = a.ingestion_batch_id
                 AND u.user_id = a.user_id
                WHERE a.ingestion_batch_id = %s
                  AND a.assignment_at < u.signed_up_at
            """,
        ),
        ValidationCheck(
            name="experiment_assignment_inside_window",
            category="chronology",
            dataset_name="experiment_assignments",
            description=(
                "Assignment must occur at or after experiment start "
                "and before experiment end."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.experiment_assignments
                WHERE ingestion_batch_id = %s
                  AND NOT (
                      experiment_start_at <= assignment_at
                      AND assignment_at < experiment_end_at
                  )
            """,
        ),
        ValidationCheck(
            name="experiment_exposure_inside_window",
            category="chronology",
            dataset_name="experiment_assignments",
            description=(
                "Exposure must occur at or after assignment "
                "and before experiment end."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.experiment_assignments
                WHERE ingestion_batch_id = %s
                  AND exposed_at IS NOT NULL
                  AND NOT (
                      assignment_at <= exposed_at
                      AND exposed_at < experiment_end_at
                  )
            """,
        ),
        ValidationCheck(
            name="marketing_spend_period_order",
            category="chronology",
            dataset_name="marketing_spend",
            description=(
                "Marketing period_end cannot precede period_start."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.marketing_spend
                WHERE ingestion_batch_id = %s
                  AND period_end < period_start
            """,
        ),
        ValidationCheck(
            name="app_release_rollout_not_before_release",
            category="chronology",
            dataset_name="app_releases",
            description=(
                "App rollout completion cannot precede release."
            ),
            query="""
                SELECT COUNT(*)::BIGINT
                FROM raw.app_releases
                WHERE ingestion_batch_id = %s
                  AND rollout_complete_at < release_at
            """,
        ),
    ]


def _nullability_checks() -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []

    for dataset_name, field_rules in DATASET_FIELD_RULES.items():
        table = _identifier(dataset_name)
        clauses: list[str] = []

        for field_name, rule in field_rules.items():
            field = _identifier(field_name)

            if not rule.nullable:
                clauses.append(
                    f"{field} IS NULL"
                )

            if rule.kind == "string":
                clauses.append(
                    f"({field} IS NOT NULL "
                    f"AND btrim({field}) = '')"
                )

        predicate = " OR ".join(clauses)

        checks.append(
            ValidationCheck(
                name=f"{dataset_name}_nullability",
                category="nullability",
                dataset_name=dataset_name,
                description=(
                    "Required fields must be populated and "
                    "text values must not be blank."
                ),
                query=f"""
                    SELECT COUNT(*)::BIGINT
                    FROM raw.{table}
                    WHERE ingestion_batch_id = %s
                      AND ({predicate})
                """,
            )
        )

    return checks


def _domain_checks() -> list[ValidationCheck]:
    checks: list[ValidationCheck] = []

    for dataset_name, field_rules in DATASET_FIELD_RULES.items():
        table = _identifier(dataset_name)

        clauses: list[str] = []
        params: list[Any] = []

        for field_name, rule in field_rules.items():
            field = _identifier(field_name)

            if rule.kind == "string":
                clauses.append(
                    f"({field} IS NOT NULL "
                    f"AND {field} <> btrim({field}))"
                )

            if rule.allowed_values is not None:
                clauses.append(
                    f"({field} IS NOT NULL "
                    f"AND NOT ({field} = ANY(%s)))"
                )
                params.append(
                    list(rule.allowed_values)
                )

            if rule.minimum is not None:
                clauses.append(
                    f"({field} IS NOT NULL "
                    f"AND {field} < %s)"
                )
                params.append(rule.minimum)

            if rule.maximum is not None:
                clauses.append(
                    f"({field} IS NOT NULL "
                    f"AND {field} > %s)"
                )
                params.append(rule.maximum)

        predicate = " OR ".join(clauses)

        checks.append(
            ValidationCheck(
                name=f"{dataset_name}_domain",
                category="domain",
                dataset_name=dataset_name,
                description=(
                    "Values must satisfy the approved Step 2 "
                    "domain, range, and whitespace rules."
                ),
                query=f"""
                    SELECT COUNT(*)::BIGINT
                    FROM raw.{table}
                    WHERE ingestion_batch_id = %s
                      AND ({predicate})
                """,
                params=tuple(params),
            )
        )

    return checks


def build_validation_checks() -> tuple[ValidationCheck, ...]:
    """Build the complete deterministic raw-batch validation catalogue."""

    checks = (
        _reconciliation_checks()
        + _uniqueness_checks()
        + _referential_checks()
        + _chronology_checks()
        + _nullability_checks()
        + _domain_checks()
    )

    names = [check.name for check in checks]

    if len(names) != len(set(names)):
        raise PostgresValidationError(
            "Validation check names must be unique."
        )

    return tuple(checks)


def _get_source_batch(
    cursor,
    ingestion_batch_id: int,
) -> str:
    cursor.execute(
        """
        SELECT
            snapshot_id,
            status
        FROM raw.ingestion_batches
        WHERE ingestion_batch_id = %s
        """,
        (ingestion_batch_id,),
    )

    row = cursor.fetchone()

    if row is None:
        raise PostgresValidationError(
            "Unknown ingestion batch: "
            f"{ingestion_batch_id}"
        )

    snapshot_id, status = row

    if status != "succeeded":
        raise PostgresValidationError(
            "Only succeeded raw ingestion batches "
            "may be validated. "
            f"Batch {ingestion_batch_id} "
            f"has status={status!r}."
        )

    return str(snapshot_id)


def _find_successful_run(
    cursor,
    ingestion_batch_id: int,
    snapshot_id: str,
    expected_check_count: int,
) -> ValidationRunResult | None:
    cursor.execute(
        """
        SELECT
            validation_run_id,
            expected_check_count,
            completed_check_count,
            passed_check_count,
            failed_check_count
        FROM validation.validation_runs
        WHERE ingestion_batch_id = %s
          AND status = 'succeeded'
        ORDER BY validation_run_id
        LIMIT 1
        """,
        (ingestion_batch_id,),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    (
        validation_run_id,
        stored_expected,
        completed,
        passed,
        failed,
    ) = row

    if int(stored_expected) != expected_check_count:
        raise PostgresValidationError(
            "An existing successful validation run uses "
            "a different validation catalogue size. "
            "Explicit migration/revalidation is required."
        )

    return ValidationRunResult(
        validation_run_id=int(validation_run_id),
        ingestion_batch_id=ingestion_batch_id,
        snapshot_id=snapshot_id,
        status="succeeded",
        expected_check_count=int(stored_expected),
        completed_check_count=int(completed),
        passed_check_count=int(passed),
        failed_check_count=int(failed),
        already_validated=True,
    )


def _create_validation_run(
    cursor,
    ingestion_batch_id: int,
    expected_check_count: int,
) -> int:
    cursor.execute(
        """
        INSERT INTO validation.validation_runs (
            ingestion_batch_id,
            status,
            expected_check_count
        )
        VALUES (
            %s,
            'running',
            %s
        )
        RETURNING validation_run_id
        """,
        (
            ingestion_batch_id,
            expected_check_count,
        ),
    )

    row = cursor.fetchone()

    if row is None:
        raise PostgresValidationError(
            "PostgreSQL did not return validation_run_id."
        )

    return int(row[0])


def _execute_check(
    cursor,
    *,
    validation_run_id: int,
    ingestion_batch_id: int,
    check: ValidationCheck,
) -> int:
    params = (
        ingestion_batch_id,
        *check.params,
    )

    # Some reconciliation checks compare two batch-scoped subqueries.
    # They therefore contain two ingestion-batch placeholders.
    batch_placeholder_count = (
        check.query.count(
            "ingestion_batch_id = %s"
        )
    )

    if (
        check.category == "reconciliation"
        and batch_placeholder_count == 2
        and not check.params
    ):
        params = (
            ingestion_batch_id,
            ingestion_batch_id,
        )

    cursor.execute(
        check.query,
        params,
    )

    row = cursor.fetchone()

    if row is None:
        raise PostgresValidationError(
            f"Check returned no result: {check.name}"
        )

    violation_count = int(row[0])

    if violation_count < 0:
        raise PostgresValidationError(
            "Validation violation_count cannot be negative: "
            f"{check.name}"
        )

    status = (
        "passed"
        if violation_count == 0
        else "failed"
    )

    cursor.execute(
        """
        INSERT INTO validation.check_results (
            validation_run_id,
            check_name,
            check_category,
            dataset_name,
            severity,
            status,
            violation_count,
            details
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
        """,
        (
            validation_run_id,
            check.name,
            check.category,
            check.dataset_name,
            check.severity,
            status,
            violation_count,
            Jsonb(
                {
                    "description":
                        check.description,
                }
            ),
        ),
    )

    return violation_count


def _complete_validation_run(
    cursor,
    *,
    validation_run_id: int,
    expected_check_count: int,
    passed_check_count: int,
    failed_check_count: int,
) -> str:
    completed_check_count = (
        passed_check_count
        + failed_check_count
    )

    status = (
        "succeeded"
        if failed_check_count == 0
        else "failed"
    )

    error_message = (
        None
        if status == "succeeded"
        else (
            f"{failed_check_count} blocking "
            "validation check(s) failed."
        )
    )

    cursor.execute(
        """
        UPDATE validation.validation_runs
        SET
            status = %s,
            completed_check_count = %s,
            passed_check_count = %s,
            failed_check_count = %s,
            completed_at = clock_timestamp(),
            error_message = %s
        WHERE validation_run_id = %s
        """,
        (
            status,
            completed_check_count,
            passed_check_count,
            failed_check_count,
            error_message,
            validation_run_id,
        ),
    )

    if completed_check_count != expected_check_count:
        raise PostgresValidationError(
            "Validation run completed with an "
            "unexpected check count."
        )

    return status


def _record_operational_failure(
    connection,
    *,
    ingestion_batch_id: int,
    expected_check_count: int,
    error_message: str,
) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO validation.validation_runs (
                    ingestion_batch_id,
                    status,
                    expected_check_count,
                    completed_check_count,
                    passed_check_count,
                    failed_check_count,
                    completed_at,
                    error_message
                )
                VALUES (
                    %s,
                    'failed',
                    %s,
                    0,
                    0,
                    0,
                    clock_timestamp(),
                    %s
                )
                """,
                (
                    ingestion_batch_id,
                    expected_check_count,
                    error_message[:4000],
                ),
            )

        connection.commit()

    except Exception:
        connection.rollback()


def validate_raw_batch(
    ingestion_batch_id: int,
    *,
    connection=None,
) -> ValidationRunResult:
    """Validate one succeeded raw ingestion batch transactionally."""

    if ingestion_batch_id <= 0:
        raise ValueError(
            "ingestion_batch_id must be greater than zero."
        )

    checks = build_validation_checks()
    expected_check_count = len(checks)

    owns_connection = connection is None
    resolved_connection = (
        connect_database()
        if owns_connection
        else connection
    )

    run_created = False

    try:
        with resolved_connection.cursor() as cursor:
            snapshot_id = _get_source_batch(
                cursor,
                ingestion_batch_id,
            )

            existing = _find_successful_run(
                cursor,
                ingestion_batch_id,
                snapshot_id,
                expected_check_count,
            )

            if existing is not None:
                resolved_connection.rollback()
                return existing

            validation_run_id = _create_validation_run(
                cursor,
                ingestion_batch_id,
                expected_check_count,
            )
            run_created = True

            passed = 0
            failed = 0
            failures: list[tuple[str, int]] = []

            for check in checks:
                violation_count = _execute_check(
                    cursor,
                    validation_run_id=
                        validation_run_id,
                    ingestion_batch_id=
                        ingestion_batch_id,
                    check=check,
                )

                if violation_count == 0:
                    passed += 1
                else:
                    failed += 1
                    failures.append(
                        (
                            check.name,
                            violation_count,
                        )
                    )

            status = _complete_validation_run(
                cursor,
                validation_run_id=
                    validation_run_id,
                expected_check_count=
                    expected_check_count,
                passed_check_count=passed,
                failed_check_count=failed,
            )

        resolved_connection.commit()

        return ValidationRunResult(
            validation_run_id=validation_run_id,
            ingestion_batch_id=ingestion_batch_id,
            snapshot_id=snapshot_id,
            status=status,
            expected_check_count=
                expected_check_count,
            completed_check_count=
                passed + failed,
            passed_check_count=passed,
            failed_check_count=failed,
            already_validated=False,
            failures=tuple(failures),
        )

    except Exception as exc:
        resolved_connection.rollback()

        if run_created:
            _record_operational_failure(
                resolved_connection,
                ingestion_batch_id=
                    ingestion_batch_id,
                expected_check_count=
                    expected_check_count,
                error_message=(
                    f"{type(exc).__name__}: {exc}"
                ),
            )

        if isinstance(
            exc,
            PostgresValidationError,
        ):
            raise

        raise PostgresValidationError(
            "PostgreSQL raw validation failed "
            "operationally."
        ) from exc

    finally:
        if owns_connection:
            resolved_connection.close()


def print_validation_result(
    result: ValidationRunResult,
) -> None:
    """Print a concise validation summary."""

    print(
        "=== POSTGRESQL RAW VALIDATION ==="
    )
    print(
        "Ingestion batch ID:",
        result.ingestion_batch_id,
    )
    print(
        "Snapshot ID:",
        result.snapshot_id,
    )
    print(
        "Validation run ID:",
        result.validation_run_id,
    )
    print(
        "Status:",
        result.status,
    )
    print(
        "Expected checks:",
        result.expected_check_count,
    )
    print(
        "Completed checks:",
        result.completed_check_count,
    )
    print(
        "Passed checks:",
        result.passed_check_count,
    )
    print(
        "Failed checks:",
        result.failed_check_count,
    )
    print(
        "Already validated:",
        result.already_validated,
    )

    if result.failures:
        print()
        print("Failed validation checks:")

        for name, count in result.failures:
            print(
                f"  {name}: "
                f"{count:,} violation(s)"
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a succeeded Pulse PostgreSQL "
            "raw ingestion batch."
        )
    )

    parser.add_argument(
        "--batch-id",
        type=int,
        required=True,
        help="Succeeded raw ingestion batch ID.",
    )

    args = parser.parse_args()

    result = validate_raw_batch(
        args.batch_id,
    )

    print_validation_result(result)

    if result.status != "succeeded":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
