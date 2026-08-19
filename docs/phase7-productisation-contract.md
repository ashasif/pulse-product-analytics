# Pulse Phase 7 Productisation Contract

## Purpose

Phase 7 turns the completed Pulse analytical platform into a business-facing,
portfolio-ready application without redefining or weakening analytical
contracts established in Phases 1 through 6.

## Protected analytical state

Phase 7 must not modify or reinterpret:

- the immutable raw snapshot;
- canonical reporting semantics;
- experiment definitions;
- Phase 5 inferential outcomes;
- Phase 6 model selection;
- Phase 6 calibration policy;
- final-test partitions;
- final-test results;
- the frozen final-holdout evidence.

The locked Phase 6 model remains `behavioural_logistic` with
`uncalibrated` probability output.

## Business reporting source

Business-facing KPIs must consume PostgreSQL `reporting.*`.

Python and Streamlit may format, filter and visualise supported metrics but
must not independently recreate canonical KPI definitions.

Deferred and unsupported metric contracts remain unavailable.

## Live and frozen evidence boundary

### Live PostgreSQL evidence

Phase 4-style descriptive business analytics may be queried from validated
`reporting.*` relations.

This includes acquisition, funnel, engagement, successful billed payment
collection, mature trial conversion and maturity-controlled paid retention.

### Frozen Phase 5 evidence

Randomized experiment statistical inference is consumed from approved frozen
Phase 5 portfolio artifacts.

The Streamlit application must not rerun inference in normal dashboard use.

### Frozen Phase 6 evidence

The application may present approved Phase 6 model results but must not:

- retrain the model;
- reselect predictors;
- recalibrate probabilities;
- rescore the final holdout for development;
- use final-test or June 2026 results for tuning.

The Phase 6 final holdout status remains:

`OPEN AND FROZEN`

The Phase 6 final holdout status remains:

`OPEN AND FROZEN`

The SHA-256 of `docs/phase6-final-holdout-results.md` must remain:

`ec1eadb21395b8dfda95399766e1993781c95b9621d8c6d500c9a0a1f429737e`

## Predictive interpretation

Operational risk is:

`1 - P(paid conversion)`

The model provides modest prioritisation value.

Predictive ranking is not causal evidence, and targeting lift does not
establish intervention effectiveness.

## Revenue terminology

Successful payment revenue represents successful billed cash collection.

It must not be presented as:

- accounting-recognised revenue;
- net revenue;
- profit;
- customer lifetime value.

## Synthetic-data constraint

Pulse uses synthetic customer behaviour.

The application demonstrates data engineering, analytics, experimentation
and predictive-modelling methodology.

No dashboard result should imply that identical customer relationships would
necessarily hold in a real production population.

## Application configuration

Application database configuration uses the `PULSE_DB_*` environment-variable
contract implemented by `DatabaseConfig`.

A deployed application should use a dedicated PostgreSQL LOGIN role inheriting
the read-only `pulse_reporting_reader` group role.

Secrets must not be committed to the repository.