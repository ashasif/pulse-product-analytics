# Pulse Phase 4 — Descriptive Experiment Findings

> Pulse and all analysed data are synthetic and exist solely for portfolio and learning purposes.

## Analysis context

- Ingestion batch: `1`
- Analytics build: `1`
- Observation cutoff: `2026-07-01T00:59:36+01:00`
- Experiments represented: **3**
- Assignments: **20,006**
- Exposed assignments: **19,321**
- Mature analysis windows: **20,006**

Only supported canonical outcome metrics are analysed. Configured experiment labels that remain deferred are not silently converted into new definitions.

## AI Assistant Discovery Experiment

- Experiment ID: `exp_ai_discovery_2025q4`
- Configured primary metric: `ai_assistant_use_7d`
- Configured secondary metric: `return_session_7d`
- Configured commercial metric: `trial_start_conversion_14d`
- Configured guardrail metric: `overall_feature_use_7d`
- Analysis window: **14 days**

| Variant | Assigned | Exposure | Onboarding 48h | Feature use 7d | Trial 7d | Paid 14d | Revenue/user 30d | Cancel/expiry 30d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 4,482 | 100.00% | 0.00% | 100.00% | 2.32% | 0.98% | £0.83 | 4.08% |
| treatment | 6,856 | 100.00% | 0.00% | 100.00% | 2.51% | 1.06% | £0.81 | 3.82% |

### Observed variant differences

**treatment vs control**

- Onboarding completion within 48h: +0.00 pp
- Any feature use within 7d: +0.00 pp
- Trial start within 7d: +0.19 pp
- Paid conversion within 14d: +0.08 pp
- Successful payment collection per assigned user within 30d: -0.01 GBP
- Cancellation or expiry within 30d: -0.26 pp

## Onboarding Guidance Experiment

- Experiment ID: `exp_onboarding_guidance_2025q1`
- Configured primary metric: `onboarding_completion_48h`
- Configured secondary metric: `activation_48h`
- Configured commercial metric: `trial_start_conversion_14d`
- Configured guardrail metric: `d7_return_rate`
- Analysis window: **14 days**

| Variant | Assigned | Exposure | Onboarding 48h | Feature use 7d | Trial 7d | Paid 14d | Revenue/user 30d | Cancel/expiry 30d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 3,001 | 88.24% | 68.54% | 85.10% | 1.83% | 0.90% | £0.56 | 3.07% |
| treatment | 2,962 | 88.79% | 68.53% | 84.67% | 1.72% | 0.47% | £0.59 | 3.00% |

### Observed variant differences

**treatment vs control**

- Onboarding completion within 48h: -0.01 pp
- Any feature use within 7d: -0.43 pp
- Trial start within 7d: -0.11 pp
- Paid conversion within 14d: -0.43 pp
- Successful payment collection per assigned user within 30d: +0.03 GBP
- Cancellation or expiry within 30d: -0.06 pp

## Paywall Redesign Experiment

- Experiment ID: `exp_paywall_redesign_2024q3`
- Configured primary metric: `trial_start_conversion_7d`
- Configured secondary metric: `paid_conversion_14d`
- Configured commercial metric: `revenue_per_assigned_user_30d`
- Configured guardrail metric: `cancellation_or_expiry_30d`
- Analysis window: **30 days**

| Variant | Assigned | Exposure | Onboarding 48h | Feature use 7d | Trial 7d | Paid 14d | Revenue/user 30d | Cancel/expiry 30d |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| control | 1,341 | 100.00% | 3.06% | 62.12% | 20.21% | 7.98% | £3.20 | 15.36% |
| treatment | 1,364 | 100.00% | 3.01% | 63.56% | 18.84% | 7.92% | £3.48 | 14.44% |

### Observed variant differences

**treatment vs control**

- Onboarding completion within 48h: -0.05 pp
- Any feature use within 7d: +1.45 pp
- Trial start within 7d: -1.37 pp
- Paid conversion within 14d: -0.06 pp
- Successful payment collection per assigned user within 30d: +0.28 GBP
- Cancellation or expiry within 30d: -0.92 pp

## Interpretation boundary

Every difference above is an **observed descriptive difference** in the synthetic dataset.

The analysis does **not** provide:

- p-values
- confidence intervals
- statistical-significance decisions
- causal lift
- treatment effects
- causal-inference claims

The experiment results should therefore be used as hypothesis-generating evidence rather than proof that a variant caused an outcome.
