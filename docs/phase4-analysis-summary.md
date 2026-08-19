# Pulse Phase 4 — Business Analytics & Decision Intelligence

## Objective

Phase 4 converts the production-ready Pulse reporting semantic layer into
reproducible, decision-oriented product and subscription analysis.

The phase deliberately separates business analysis from Phase 3 warehouse
infrastructure.

## Source of truth

All Phase 4 database analysis reads from the validated `reporting` schema.

Phase 4 does not recreate KPI definitions in Python and does not query the
`raw`, `staging`, `validation` or `analytics` schemas directly from
business-analysis code.

## Step 1 — Analysis foundation

A read-only reporting client was introduced with controls that:

- reject direct access to Phase 3 internal schemas;
- reject write statements;
- require canonical metric contracts;
- reject deferred and unsupported metrics;
- preserve ingestion batch, analytics-build and observation-cutoff lineage.

## Step 2 — Growth, funnel and acquisition

The analysis evaluates:

- installation and signup growth;
- install-to-signup performance;
- onboarding conversion;
- acquisition-channel efficiency;
- marketing spend;
- CTR;
- cost per click;
- channel-level cost per install;
- platform and country funnel variation.

The analysis uses aligned H1 2024 and H1 2026 periods rather than comparing
a full prior year with the incomplete 2026 calendar year.

## Step 3 — Engagement, monetisation and retention

The analysis evaluates:

- registered daily active users;
- sessions;
- feature-use events;
- feature distribution;
- payment attempts and failures;
- successful billed payment collection;
- renewal performance;
- mature trial-to-paid conversion;
- maturity-controlled D30, D90, D180 and D365 paid retention;
- retention by billing period and acquisition channel.

Successful payment collection is not presented as accounting-recognised or
net revenue.

## Step 4 — Descriptive experiments and business synthesis

Three synthetic experiments are analysed using supported canonical outcomes.

Experiment reporting remains descriptive only.

No p-values, confidence intervals, statistical-significance claims, causal
lift or treatment effects are introduced.

Configured experiment metric labels that are deferred in the semantic
registry remain documented rather than being silently invented.

## Key portfolio findings

The approved production snapshot contains 100,000 installations and has an
install-to-signup rate of 62.18%.

Referral has the strongest observed install-to-signup performance and the
lowest positive channel-level CPI. It also has the strongest observed D365
paid retention among acquisition channels, although this relationship is
descriptive and does not establish causation.

Mature trial-to-paid conversion is 37.31%.

Paid retention is 73.26% at D30, 51.51% at D90, 37.92% at D180 and 9.74%
at D365. Long-horizon paid persistence is therefore the strongest business
issue surfaced by the current synthetic snapshot.

Successful billed payment collection is £176,562.87. Payment failure is
4.67%, while renewal-attempt success is 95.43%.

AI Assistant is the highest-volume feature with 739,182 feature-use events,
representing 31.95% of feature-use activity.

## Interpretation boundaries

Phase 4 does not infer or invent:

- customer lifetime value;
- monthly active users;
- recognised revenue;
- net revenue;
- profit;
- campaign-attributed CAC;
- average session duration;
- causal experiment lift.

## Lineage

Production Phase 4 analysis uses:

- ingestion batch `1`;
- analytics build `1`;
- observation cutoff `2026-07-01T00:59:36+01:00`.

All data are synthetic.

## Closure status

Phase 4 ? Business Analytics & Decision Intelligence is **COMPLETE & FORMALLY CLOSED**.

Final automated regression baseline: **425 tests passed**.

Closure validation confirmed:

- all Phase 4 analytical outputs use the validated `reporting` semantic layer;
- ingestion batch `1` and analytics build `1` lineage are preserved;
- the observation cutoff remains `2026-07-01T00:59:36+01:00`;
- Phase 3 protected warehouse areas remain unchanged;
- cohort maturity rules remain preserved;
- successful payment collection is not represented as accounting or net revenue;
- experiment reporting remains descriptive only;
- all analysed data remain explicitly identified as synthetic.
