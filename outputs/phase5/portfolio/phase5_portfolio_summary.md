# Pulse Phase 5 - Experimentation & Statistical Inference

> Pulse is a synthetic product analytics and subscription intelligence platform. All experiment data and results are synthetic.

## Executive result

No completed canonical Pulse experiment outcome produced a statistically detectable treatment-minus-control difference at the current production snapshot. Several configured metrics remain deferred or non-canonical, so absence of detectability must not be interpreted as proof of zero effect.

## Production lineage

- Ingestion batch: `1`
- Analytics build: `1`
- Observation cutoff: `2026-07-01T00:59:36+01:00`
- Primary population: `assigned_mature`

## Experiment decisions

### AI Assistant Discovery Experiment

- Decision status: `not_decision_ready_primary_metric_unavailable`
- Completed inferential metrics: 1 / 4
- Primary metric: `ai_assistant_use_7d`

Do not make a treatment rollout decision from Phase 5. The configured primary metric is not currently available as a supported canonical inferential outcome.

| Role | Metric | Effect | 95% CI | Raw p | Holm p | MDE |
|---|---|---:|---:|---:|---:|---:|
| guardrail | `overall_feature_use_7d` | 0.00 pp | [-0.06, 0.09] pp | 1 | 1 | n/a |

Unavailable configured metrics:
- `ai_assistant_use_7d` (primary): `excluded_deferred`
- `return_session_7d` (secondary): `excluded_deferred`
- `trial_start_conversion_14d` (commercial): `excluded_unknown_metric_contract`

### Onboarding Guidance Experiment

- Decision status: `primary_not_detectable_supporting_metrics_incomplete`
- Completed inferential metrics: 1 / 4
- Primary metric: `onboarding_completion_48h`

The canonical primary outcome does not show a statistically detectable treatment-minus-control difference, while one or more configured supporting metrics remain unavailable. Do not interpret this as proof of no treatment effect.

| Role | Metric | Effect | 95% CI | Raw p | Holm p | MDE |
|---|---|---:|---:|---:|---:|---:|
| primary | `onboarding_completion_48h` | -0.01 pp | [-2.37, 2.35] pp | 0.994 | n/a | 3.37 pp |

Unavailable configured metrics:
- `activation_48h` (secondary): `excluded_deferred`
- `trial_start_conversion_14d` (commercial): `excluded_unknown_metric_contract`
- `d7_return_rate` (guardrail): `excluded_deferred`

### Paywall Redesign Experiment

- Decision status: `no_detectable_effect_in_completed_metric_family`
- Completed inferential metrics: 4 / 4
- Primary metric: `trial_start_conversion_7d`

The completed canonical primary and supportive outcome family provides no statistically detectable evidence supporting treatment rollout. This does not prove exact equivalence between treatment and control.

| Role | Metric | Effect | 95% CI | Raw p | Holm p | MDE |
|---|---|---:|---:|---:|---:|---:|
| primary | `trial_start_conversion_7d` | -1.37 pp | [-4.36, 1.62] pp | 0.369735 | n/a | 4.33 pp |
| secondary | `paid_conversion_14d` | -0.06 pp | [-2.11, 1.99] pp | 0.953059 | 1 | 2.92 pp |
| commercial | `revenue_per_assigned_user_30d` | GBP 0.2774 | [GBP -0.8993, GBP 1.4410] | 0.644536 | 1 | GBP 1.6471 |
| guardrail | `cancellation_or_expiry_30d` | -0.92 pp | [-3.61, 1.77] pp | 0.502196 | 1 | 3.88 pp |

## Statistical architecture

- Randomized assignment integrity checked before inference.
- Sample-ratio mismatch diagnostics respect configured allocations.
- Immature analysis windows are excluded from primary denominators.
- Binary effects use treatment minus control proportions.
- Binary uncertainty uses Newcombe/Wilson score intervals.
- Continuous commercial uncertainty uses deterministic bootstrap.
- Continuous commercial testing uses randomized-label permutation.
- Supportive outcomes use Holm multiplicity adjustment.
- MDE diagnostics are reported instead of retrospective observed power.
- Deferred and non-canonical KPIs are not invented in Python.

## Commercial metric interpretation

`revenue_per_assigned_user_30d` represents successful billed payment collection per assigned user. It is not accounting-recognised revenue, net revenue, profit or customer LTV.

## What Phase 5 does not claim

- A non-significant result does not prove exact equality.
- Statistical significance is not automatically business significance.
- Exposure-conditioned subsets are not substituted for the randomized primary estimand.
- Deferred metrics are not reconstructed from similar-looking event fields.
- Phase 5 does not perform observational causal inference.
- Phase 5 does not introduce predictive ML, forecasting or Streamlit.
