# Phase 6 — Model Development and Comparative Validation Contract

## Purpose

Step 4 determines whether Day-5 trial behaviour adds predictive value beyond
the frozen static logistic baseline established in Step 3.

## Candidate set

The candidate set is intentionally restricted to three models.

### 1. Static logistic baseline

This is the Step 3 benchmark and uses no explicit Day-5 behavioural features.

It is re-fit on the approved training population and evaluated on validation
only.

### 2. Behavioural logistic regression

This uses all 16 approved Phase 6 predictors.

Its purpose is to test whether Day-5 behavioural information adds predictive
signal while preserving a simple, regularized and interpretable model form.

### 3. Histogram gradient boosting

One nonlinear challenger is allowed.

The challenger uses the same 16 approved predictors and training-only
preprocessing.

Its hyperparameters are fixed and deliberately modest in Step 4. Step 4 is not
a broad hyperparameter-search exercise.

## Prohibited behaviour

Step 4 does not:

- use random train/test splitting
- score the final test population
- score the June 2026 boundary population
- alter the point-in-time feature contract
- create additional target definitions
- add arbitrary engineered predictors
- run a model zoo
- tune against final-test results

## Model fitting

All estimator parameters and preprocessing parameters are fitted on the
January 2024 through June 2025 training population only.

Model comparison uses the July through December 2025 validation population.

## Evaluation hierarchy

Primary:

- Brier score

Guardrail:

- log loss

Supporting discrimination metrics:

- ROC-AUC
- average precision

Lower Brier and log loss are better.

## Behavioural increment rule

A behavioural model is considered to have demonstrated improved probability
quality over the static baseline only if both:

- validation Brier score is lower than the static logistic baseline
- validation log loss is lower than the static logistic baseline

ROC-AUC alone is not sufficient.

## Complexity rule

If the full behavioural logistic model performs as well as or better than the
nonlinear challenger on probability quality, the simpler logistic model is
preferred.

If the nonlinear challenger provides materially better validation probability
quality, it may remain the provisional model for Step 5 robustness and
calibration work.

No final model is approved until later Phase 6 validation steps.

## Final-test firewall

The January through May 2026 test set is defined but not scored in Step 4.

The June 2026 boundary population also remains unscored.

## Step 4 validation result

Validation population: 2,238 trials from July through December 2025.

### Static logistic baseline

- Brier score: 0.235402
- log loss: 0.663727
- ROC-AUC: 0.536347
- average precision: 0.408229

### Behavioural logistic regression

- Brier score: 0.233099
- log loss: 0.658924
- ROC-AUC: 0.563282
- average precision: 0.445289

Relative to the static baseline:

- Brier delta: -0.002303
- log-loss delta: -0.004803
- ROC-AUC delta: +0.026935
- average-precision delta: +0.037060

The behavioural logistic model satisfies the predeclared behavioural-increment
rule because it improves both Brier score and log loss.

### Histogram gradient boosting

- Brier score: 0.238036
- log loss: 0.671337
- ROC-AUC: 0.543833
- average precision: 0.433623

Relative to the static baseline:

- Brier delta: +0.002635
- log-loss delta: +0.007610
- ROC-AUC delta: +0.007486
- average-precision delta: +0.025394

The nonlinear challenger fails the probability-quality improvement rule and is
rejected.

### Provisional champion

`behavioural_logistic`

This remains provisional until calibration, robustness and final holdout
evaluation are completed in later Phase 6 steps.

The January-May 2026 final test population and June 2026 boundary population
remain unscored.
