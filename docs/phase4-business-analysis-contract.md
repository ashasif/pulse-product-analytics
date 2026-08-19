# Pulse Phase 4 Business Analysis Contract

## Purpose

Phase 4 converts the validated Pulse reporting semantic layer into
decision-oriented business analysis.

The warehouse remains the source of truth for metric definitions,
cohort maturity, lineage and reporting semantics.

## Source contract

Phase 4 analysis code may read from:

- `reporting.metric_definitions`
- approved `reporting.vw_*` semantic views

Business-analysis code must not read directly from:

- `raw`
- `staging`
- `validation`
- `analytics`

The purpose of this boundary is to prevent downstream analysis from
silently recreating or bypassing validated warehouse logic.

## Metric support contract

Only metrics whose canonical `support_status` is `supported` may be
used in Phase 4 analytical outputs.

Metrics marked `deferred` or `unsupported` must remain excluded until
their underlying business definitions or source data are explicitly
approved in a later phase.

Phase 4 must therefore not invent:

- customer lifetime value
- recognised accounting revenue
- net revenue
- campaign-attributed CAC
- average session duration
- deferred experiment metrics

## Lineage

All generated Phase 4 analytical outputs must retain or record the
relevant:

- ingestion batch
- analytics build
- observation cutoff

The production analysis currently consumes analytics build `1`.

## Cohort maturity

Trial-conversion and paid-retention analysis must preserve the
warehouse maturity rules.

Immature observations must not be introduced into conversion or
retention denominators.

## Revenue terminology

`successful_payment_revenue_gbp` represents successful billed payment
collection.

It must not be presented as:

- accounting-recognised revenue
- net revenue
- profit

## Experiment interpretation

Existing experiment reporting is descriptive.

Phase 4 may compare supported variant-level outcomes but must not claim:

- statistical significance
- confidence intervals
- p-values
- causal lift
- causal treatment effects

without a separately approved methodology.

## Read-only execution

Phase 4 PostgreSQL queries must execute inside read-only transactions.

The Python analysis client also rejects SQL containing direct
references to Phase 3 internal schemas or database-modification
keywords.

## Business output standard

Each substantive analysis should answer:

1. What happened?
2. Where or for whom did it happen?
3. Why does it matter to the simulated Pulse business?
4. What should a product or commercial stakeholder investigate next?
5. What caveats constrain the interpretation?

All business statements must make clear that Pulse and its data are
synthetic portfolio data.
