# Pulse Phase 5 - Multiplicity and Design Sensitivity

> Pulse and all experiment data are synthetic.

## Production context

- Ingestion batch: `1`
- Analytics build: `1`
- Observation cutoff: `2026-07-01T00:59:36+01:00`

## Multiplicity

Primary metrics remain prespecified and are not mixed into supportive Holm families.

| Experiment | Role | Metric | Raw p | Holm p | Family size | Detectable after Holm |
|---|---|---|---:|---:|---:|---|
| exp_ai_discovery_2025q4 | guardrail | `overall_feature_use_7d` | 1 | 1 | 1 | No |
| exp_paywall_redesign_2024q3 | secondary | `paid_conversion_14d` | 0.953059 | 1 | 3 | No |
| exp_paywall_redesign_2024q3 | guardrail | `cancellation_or_expiry_30d` | 0.502196 | 1 | 3 | No |
| exp_paywall_redesign_2024q3 | commercial | `revenue_per_assigned_user_30d` | 0.644536 | 1 | 3 | No |

## Binary design sensitivity

| Experiment | Role | Metric | Observed effect | Approx. MDE | Effect / MDE | Status |
|---|---|---|---:|---:|---:|---|
| exp_ai_discovery_2025q4 | guardrail | `overall_feature_use_7d` | 0.00 pp | not estimable | n/a | not_estimable_saturated_baseline |
| exp_onboarding_guidance_2025q1 | primary | `onboarding_completion_48h` | -0.01 pp | 3.37 pp | 0.00 | estimated |
| exp_paywall_redesign_2024q3 | primary | `trial_start_conversion_7d` | -1.37 pp | 4.33 pp | 0.32 | estimated |
| exp_paywall_redesign_2024q3 | secondary | `paid_conversion_14d` | -0.06 pp | 2.92 pp | 0.02 | estimated |
| exp_paywall_redesign_2024q3 | guardrail | `cancellation_or_expiry_30d` | -0.92 pp | 3.88 pp | 0.24 | estimated |

## Continuous commercial design sensitivity

- Experiment: `exp_paywall_redesign_2024q3`
- Metric: `revenue_per_assigned_user_30d`
- Observed treatment-minus-control mean: GBP 0.2774
- Approximate 80%-power MDE: GBP 1.6471
- Absolute observed effect / MDE: 0.17
- Control sample SD: GBP 14.7843
- Treatment sample SD: GBP 15.7834

## Interpretation

- MDE is a design-sensitivity diagnostic, not retrospective observed power.
- An observed effect smaller than the approximate MDE indicates that the current experiment was not designed to reliably detect effects that small.
- Failure to reject a null hypothesis does not prove that treatment and control are exactly equal.
- Statistical detectability and practical relevance remain separate questions.
