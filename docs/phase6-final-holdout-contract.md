# Phase 6 — Locked Final Holdout Evaluation Contract

## Purpose

Step 6 performs the final out-of-time evaluation of the Phase 6 trial
conversion model after model family, predictors, calibration policy, temporal
partitions and evaluation criteria have been frozen.

No model selection or tuning is permitted after the final test is opened.

## Locked model

Selected model:

`behavioural_logistic`

Selected calibration policy:

`uncalibrated`

The model uses the 16 point-in-time predictors approved in Phase 6 Step 2.

## Development population

The locked model is refitted using:

- training: January 2024 through June 2025
- validation: July 2025 through December 2025

Expected development population:

6,411 trials.

## Final test

The final holdout contains trials beginning:

January 2026 through May 2026.

Expected final-test population:

1,991 trials.

The final test is scored only after Step 6 implementation tests and the full
repository regression pass.

## June 2026 boundary sensitivity

The June 2026 population contains:

201 trials.

It remains separate from the primary final test.

It is evaluated only after the primary final-test result and is interpreted as
boundary sensitivity rather than model-selection evidence.

## Comparators

The final test evaluates:

1. development-population prevalence
2. static logistic regression
3. locked behavioural logistic regression

All three are fitted using the same complete development population.

## Primary final-test rule

Behavioural probability-quality improvement is confirmed only if both:

- behavioural Brier score is lower than static-logistic Brier score
- behavioural log loss is lower than static-logistic log loss

ROC-AUC and average precision remain supporting metrics.

If this rule fails, no new model search or tuning is permitted.

## Paired uncertainty

Behavioural-minus-static differences in Brier score and log loss are evaluated
using a deterministic paired bootstrap on final-test observations.

Negative differences favour the behavioural model.

Bootstrap uncertainty is descriptive evidence and cannot trigger model tuning.

## Decision utility

Non-conversion risk concentration is evaluated at:

- 10% targeting capacity
- 20% targeting capacity
- 30% targeting capacity

This measures prioritisation only.

It does not estimate causal intervention effectiveness.

## Robustness

Final-test diagnostics are reported by:

- month
- platform
- billing period
- acquisition channel

Subgroup results cannot trigger model retuning.

## Reproducibility and holdout protection

The one-time final evaluation writes:

`docs/phase6-final-holdout-results.md`

The runner refuses to execute if this file already exists.

The results file therefore acts as a final-holdout sentinel.

## Synthetic-data constraint

Pulse uses synthetic customer behaviour.

Phase 6 demonstrates leakage control, point-in-time feature construction,
temporal validation, model comparison and reproducible holdout evaluation.

It must not be represented as proof that the same customer relationships would
exist in a real production population.
