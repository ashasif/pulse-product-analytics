# Pulse Warehouse Data Dictionary

## Schemas

- raw: immutable landing layer and ingestion metadata; internal only.
- staging: typed and validated promotion layer; internal only.
- validation: persisted warehouse validation controls; internal only.
- analytics: dimensional warehouse; internal only.
- reporting: supported business-facing read-only semantic layer.

## Core analytics objects

- analytics.build_runs: one row per analytics build run.
- analytics.dim_date: one row per calendar date.
- analytics.dim_installation: one row per installation.
- analytics.dim_user: one row per registered user.
- analytics.dim_experiment: one row per experiment definition.
- analytics.dim_app_release: one row per application release.
- analytics.fact_product_event: one row per product event.
- analytics.fact_subscription: one row per subscription lifecycle.
- analytics.fact_subscription_transaction: one row per payment attempt.
- analytics.fact_experiment_assignment: one row per experiment assignment.
- analytics.fact_marketing_spend: one row per marketing-spend record.

## Reporting semantics

Canonical metrics are registered in reporting.metric_definitions: 30 supported, 5 deferred, 4 unsupported.

Successful payment revenue means successful billed payment collection, not accounting-recognised or net revenue.

Trial conversion and D30/D90/D180/D365 retention exclude immature cohorts from rate denominators.

Experiment reporting is descriptive only and does not provide causal lift or statistical-significance claims.

Canonical observation cutoff: 2026-07-01 00:59:36+01.

## Performance hardening

- analytics.ix_fact_product_event_daily_reporting supports daily product KPIs.
- analytics.ix_fact_product_event_feature_reporting supports daily feature engagement.
- analytics.ix_fact_product_event_time supports the indexed observation-cutoff lookup.

## Production validation

Reporting validation for analytics build 1: 31 expected, 31 passed, 0 failed, 0 violations.
