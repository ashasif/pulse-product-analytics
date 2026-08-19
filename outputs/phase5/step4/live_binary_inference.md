# Pulse Phase 5 — Live Binary Experiment Inference

> Pulse is a synthetic product analytics project. All experiment data and results are synthetic.

## Production context

- Ingestion batch: `1`
- Analytics build: `1`
- Observation cutoff: `2026-07-01T00:59:36+01:00`
- Primary population: `assigned_mature`

## Metric eligibility

| Experiment | Role | Metric | Contract | Phase 5 status |
|---|---|---|---|---|
| AI Assistant Discovery Experiment | primary | `ai_assistant_use_7d` | deferred | excluded_deferred |
| AI Assistant Discovery Experiment | secondary | `return_session_7d` | deferred | excluded_deferred |
| AI Assistant Discovery Experiment | commercial | `trial_start_conversion_14d` | unknown | excluded_unknown_metric_contract |
| AI Assistant Discovery Experiment | guardrail | `overall_feature_use_7d` | supported | ready_binary |
| Onboarding Guidance Experiment | primary | `onboarding_completion_48h` | supported | ready_binary |
| Onboarding Guidance Experiment | secondary | `activation_48h` | deferred | excluded_deferred |
| Onboarding Guidance Experiment | commercial | `trial_start_conversion_14d` | unknown | excluded_unknown_metric_contract |
| Onboarding Guidance Experiment | guardrail | `d7_return_rate` | deferred | excluded_deferred |
| Paywall Redesign Experiment | primary | `trial_start_conversion_7d` | supported | ready_binary |
| Paywall Redesign Experiment | secondary | `paid_conversion_14d` | supported | ready_binary |
| Paywall Redesign Experiment | commercial | `revenue_per_assigned_user_30d` | supported | pending_continuous_inference |
| Paywall Redesign Experiment | guardrail | `cancellation_or_expiry_30d` | supported | ready_binary |

## Supported binary inference

| Experiment | Role | Metric | Control | Treatment | Effect | 95% CI | p-value | Detectable at 0.05 |
|---|---|---|---:|---:|---:|---:|---:|---|
| AI Assistant Discovery Experiment | guardrail | `overall_feature_use_7d` | 100.00% | 100.00% | 0.00 pp | [-0.06, 0.09] pp | 1 | No |
| Onboarding Guidance Experiment | primary | `onboarding_completion_48h` | 68.54% | 68.53% | -0.01 pp | [-2.37, 2.35] pp | 0.994 | No |
| Paywall Redesign Experiment | primary | `trial_start_conversion_7d` | 20.21% | 18.84% | -1.37 pp | [-4.36, 1.62] pp | 0.369735 | No |
| Paywall Redesign Experiment | secondary | `paid_conversion_14d` | 7.98% | 7.92% | -0.06 pp | [-2.11, 1.99] pp | 0.953059 | No |
| Paywall Redesign Experiment | guardrail | `cancellation_or_expiry_30d` | 15.36% | 14.44% | -0.92 pp | [-3.61, 1.77] pp | 0.502196 | No |

## Interpretation controls

- Effect direction is always treatment minus control.
- Deferred metrics are not reconstructed or substituted.
- Metrics absent from `reporting.metric_definitions` are not inferred.
- The supported continuous revenue metric is not forced through a binary test.
- Raw p-values are shown at this stage. Holm adjustment is deferred until the complete supported inferential family has been analysed.
- Statistical detectability alone is not a business decision.
- Phase 5 does not assume that the synthetic generator contains treatment effects.
