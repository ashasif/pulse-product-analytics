# Phase 6 — Calibration, Decision Utility and Robustness Contract

## Purpose

Step 5 evaluates the provisional behavioural logistic model before final
holdout evaluation.

The January-May 2026 final test population remains sealed.

The June 2026 boundary population also remains unscored.

## Calibration

Three probability variants are compared:

1. uncalibrated behavioural logistic probabilities
2. sigmoid / Platt calibration
3. isotonic calibration

The calibration methods are fitted only from temporal out-of-fold predictions
generated within the January 2024-June 2025 training population.

Validation outcomes do not fit calibration models.

They are used only to compare calibration choices.

## Calibration complexity rule

The uncalibrated model remains preferred unless a calibration method improves
both:

- validation Brier score
- validation log loss

If more than one calibration method satisfies the rule, lower Brier score is
preferred, with log loss as the secondary criterion.

## Reliability analysis

The selected probability variant is evaluated in ten equal-frequency
validation bins.

For each bin the analysis reports:

- row count
- mean predicted conversion probability
- observed conversion rate
- calibration gap

## Decision utility

The operational use case prioritises trialists with high predicted
non-conversion risk.

Step 5 evaluates fixed lifecycle-intervention capacities:

- top 10% highest risk
- top 20% highest risk
- top 30% highest risk

For each capacity the analysis reports:

- number of trialists targeted
- number of actual non-conversions captured
- share of all non-conversions captured
- non-conversion rate inside the targeted group
- population non-conversion rate
- lift versus population targeting

These results measure risk concentration only.

They do not imply that contacting a high-risk user causes conversion.

Intervention effectiveness requires randomized experimentation.

## Robustness

Validation probability quality is inspected across:

- validation month
- platform
- billing period
- acquisition channel

For each group Step 5 reports:

- population
- observed conversion rate
- mean predicted conversion
- Brier score
- log loss
- ROC-AUC where both classes are present
- average precision where both classes are present

Subgroup results are diagnostic. They are not used for broad hyperparameter
search.

## Final-test firewall

No final-test or June-2026 boundary probabilities or metrics may be produced in
Step 5.

Final holdout evaluation belongs to Phase 6 Step 6.

## Step 5 validation result

Validation population: 2,238 trials from July through December 2025.

### Calibration comparison

Uncalibrated behavioural logistic:

- Brier score: 0.233099
- log loss: 0.658924
- ROC-AUC: 0.563282
- average precision: 0.445289
- mean predicted conversion: 0.364974
- observed conversion: 0.381144
- mean probability bias: -0.016170

Sigmoid calibration:

- Brier score: 0.234724
- log loss: 0.662181
- ROC-AUC: 0.563282
- average precision: 0.445289
- mean probability bias: -0.009493

Isotonic calibration:

- Brier score: 0.234329
- log loss: 0.661381
- ROC-AUC: 0.558323
- average precision: 0.425908
- mean probability bias: -0.013829

Neither calibration method improves both Brier score and log loss.

Selected calibration method:

`uncalibrated`

Although sigmoid and isotonic reduce mean probability bias slightly, both
worsen overall probability quality under the predeclared Step 5 criteria.

### Reliability

Validation reliability is imperfect but does not justify additional
calibration complexity.

The largest notable reliability-bin gaps include:

- bin 1: predicted 0.2814, observed 0.3304
- bin 4: predicted 0.3399, observed 0.4152
- bin 8: predicted 0.3907, observed 0.4330

The highest predicted-conversion decile is closely aligned:

- predicted: 0.4950
- observed: 0.4978

Local calibration error remains a documented model limitation.

### Capacity-constrained decision utility

At 10% targeting capacity:

- targeted trials: 224
- non-conversions captured: 150 / 1,385
- capture rate: 10.83%
- targeted non-conversion rate: 66.96%
- population non-conversion rate: 61.89%
- lift: 1.0821

At 20% targeting capacity:

- targeted trials: 448
- non-conversions captured: 309 / 1,385
- capture rate: 22.31%
- targeted non-conversion rate: 68.97%
- population non-conversion rate: 61.89%
- lift: 1.1145

At 30% targeting capacity:

- targeted trials: 672
- non-conversions captured: 457 / 1,385
- capture rate: 33.00%
- targeted non-conversion rate: 68.01%
- population non-conversion rate: 61.89%
- lift: 1.0989

The model therefore provides modest positive concentration of non-conversion
risk for capacity-limited prioritisation.

This does not establish intervention effectiveness.

### Temporal robustness

Validation month ROC-AUC ranges from approximately 0.534 to 0.618.

December 2025 has the weakest probability quality:

- Brier score: 0.246572
- log loss: 0.686982
- observed conversion: 0.4240
- mean predicted conversion: 0.3601

Temporal variability is retained as a model limitation.

### Platform robustness

Android:

- Brier score: 0.234344
- ROC-AUC: 0.555960

iOS:

- Brier score: 0.231879
- ROC-AUC: 0.572774

No major platform-specific failure is observed.

### Billing-period robustness

Annual:

- Brier score: 0.235471
- ROC-AUC: 0.587138

Monthly:

- Brier score: 0.232460
- ROC-AUC: 0.556794

No major billing-period-specific failure is observed.

### Acquisition-channel robustness

Validation ROC-AUC:

- content: 0.616915
- paid search: 0.601834
- referral: 0.565547
- organic: 0.553570
- paid social: 0.551898

Channel-level discrimination varies and is retained as a diagnostic
limitation.

### Step 5 decision

The uncalibrated behavioural logistic model remains the provisional Phase 6
champion.

It provides modest but consistent validation improvement over the static
baseline, modest positive risk concentration for operational prioritisation,
and acceptable subgroup stability.

Predictive discrimination remains moderate rather than strong.

The January-May 2026 final test population remains unscored.

The June 2026 boundary population remains unscored.
