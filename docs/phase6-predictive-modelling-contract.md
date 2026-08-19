# Phase 6 — Predictive Analytics & Machine Learning Contract

## Selected modelling problem

Predict whether an active seven-day trial will convert to a paid subscription,
scored 48 hours before the scheduled trial end.

The operational quantity is paid-conversion probability. Non-conversion risk is
one minus that probability.

## Business decision

The prediction supports lifecycle / subscription-growth prioritisation while
there is still time to intervene during the trial.

A predictive score does not establish that an intervention causes conversion.
Any intervention based on the score requires randomized evaluation.

## Prediction unit

One subscription trial.

Pulse currently has one subscription trial per user and per installation in the
production lineage.

## Prediction timestamp

`prediction_at = trial_ends_at - 48 hours`

Because the configured trial length is seven days, this corresponds to Day 5.

## Canonical target

The canonical business label remains the existing reporting definition:

A trial is converted when `subscription_started_at` is observed on or before
the canonical reporting observation cutoff.

The Phase 6 row-level reporting contract mirrors this definition; it does not
add or modify a KPI in `reporting.metric_definitions`.

## Supervised-learning maturity rule

The reporting KPI considers a trial mature when the contractual trial end is
observable.

For supervised modelling, Phase 6 adds a right-censoring safety buffer only:

`trial_ends_at + 72 hours <= observation_cutoff_at`

This is not a new business metric. It ensures that the configured initial
payment retry window can be observed before assigning the final training label.

## Current production population

For ingestion batch 1 / analytics build run 1:

- strict label-ready trials: 8,603
- converted to paid: 3,213
- not converted: 5,390
- conversion rate: 37.35%
- monthly cohorts: January 2024 through June 2026

## Predictor contract

### Static context

- `platform`
- `acquisition_channel`
- `country_code`
- `billing_period`

`price_gbp` is retained for audit context but excluded as a predictor because
the current synthetic pricing contract maps price directly to billing period.

### Lifecycle context

- `install_to_signup_hours`
- `signup_to_trial_hours`
- `onboarding_started_before_prediction`
- `onboarding_completed_before_prediction`

### Pre-trial behaviour

- `pretrial_session_count`
- `pretrial_feature_event_count`
- `pretrial_paywall_view_count`

### Trial behaviour observable by Day 5

- `trial_session_count`
- `trial_feature_event_count`
- `trial_active_day_count`
- `trial_distinct_feature_count`
- `hours_since_last_trial_activity`

No per-feature model columns are created in Step 2. The synthetic paid
conversion mechanism uses aggregate trial engagement, so adding many feature-
specific columns would increase dimensionality without a justified decision
need.

## Hard point-in-time boundary

No product event after `prediction_at` may contribute to a predictor.

The dataset stores `max_observed_trial_activity_at` as audit evidence and
validates that it never exceeds `prediction_at`.

## Forbidden outcome information

The following are never predictors:

- subscription status
- paid-subscription start timestamp
- current paid-period timestamps
- cancellation timestamps
- expiry timestamps
- auto-renew state
- end reason
- payment outcomes
- payment-failure events
- subscription-start events
- renewal events
- cancellation events
- subscription-expiry events
- post-prediction product events
- row hashes
- source row numbers
- warehouse validation/build identifiers as model inputs
- user, installation or subscription identifiers as model inputs

Keys and lineage values are retained only for reconciliation and auditing.

## Architecture

Business target semantics:
`reporting.vw_trial_conversion_prediction_base`

Canonical aggregate KPI:
`reporting.vw_trial_conversion_cohorts`

Point-in-time feature construction:
`src.analysis.trial_conversion_dataset`

Validated source activity:
`analytics.fact_product_event`

Model fitting, preprocessing, baselines and evaluation are deferred to later
Phase 6 steps.

## Synthetic-data limitation

Pulse demonstrates a point-in-time-correct predictive workflow over synthetic
customer behaviour. Predictive performance must not be presented as evidence
that the same behavioural relationships exist in real customers.