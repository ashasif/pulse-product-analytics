# Phase 6 ? Predictive Modelling Summary

## Decision use case

Phase 6 evaluates whether a Day-5 trial conversion risk model can support
capacity-limited lifecycle prioritisation before a seven-day trial ends.

The prediction is made 48 hours before trial completion.

The operational score is non-conversion risk:

`1 - P(paid conversion)`

## Point-in-time modelling population

The modelling dataset uses the canonical reporting-layer paid-conversion
definition and a 72-hour maturity buffer after trial end.

Strict eligible population:

- 8,603 trials
- 3,213 paid conversions
- 5,390 non-conversions
- conversion rate: 37.35%

Sixteen approved point-in-time predictors are used.

Post-prediction subscription state, payment outcomes and other leakage-prone
fields are prohibited.

## Temporal evaluation design

Frozen partitions:

- training: January 2024 through June 2025 ? 4,173 rows
- validation: July through December 2025 ? 2,238 rows
- final test: January through May 2026 ? 1,991 rows
- June 2026 boundary sensitivity ? 201 rows

The final model is refitted on the combined 6,411-row training and validation
development population before the one-time final holdout evaluation.

## Baselines and model development

Validation static logistic baseline:

- Brier score: 0.235402
- log loss: 0.663727
- ROC-AUC: 0.536347
- average precision: 0.408229

Validation behavioural logistic:

- Brier score: 0.233099
- log loss: 0.658924
- ROC-AUC: 0.563282
- average precision: 0.445289

Histogram gradient boosting was rejected because it worsened both Brier score
and log loss relative to the static baseline.

The behavioural logistic model therefore became the locked candidate.

## Calibration

Sigmoid and isotonic calibration were fitted only from temporal
out-of-fold training predictions.

Neither improved both validation Brier score and log loss.

Final calibration policy:

`uncalibrated`

## Locked final holdout result

Final test population:

1,991 trials from January through May 2026.

### Model comparison

| Model | Brier | Log loss | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|
| Prevalence | 0.234303 | 0.661416 | 0.500000 | 0.374686 |
| Static logistic | 0.235131 | 0.663654 | 0.522154 | 0.396435 |
| Behavioural logistic | 0.232913 | 0.658714 | 0.548994 | 0.424815 |

The behavioural logistic model improved both frozen primary
probability-quality metrics relative to the static logistic comparator.

Behavioural minus static:

- Brier delta: -0.002218
- log-loss delta: -0.004940

Paired deterministic 95% bootstrap intervals:

- Brier delta: [-0.004362, -0.000143]
- log-loss delta: [-0.009389, -0.000540]
- bootstrap replicates: 2,000
- seed: 20260819

Both intervals remain below zero.

Final out-of-time probability-quality improvement is therefore confirmed under
the predeclared Phase 6 rule.

## Probability calibration

Final-test observed conversion rate:

37.47%

Behavioural model mean predicted conversion:

37.14%

Global mean calibration is therefore close, although reliability-bin
miscalibration remains locally visible.

The largest notable final reliability gaps are approximately four to five
percentage points.

## Decision utility

The model provides modest concentration of actual non-conversions.

At 10% targeting capacity:

- 200 trialists targeted
- 137 non-conversions captured
- 11.00% of all non-conversions captured
- target-group non-conversion rate: 68.50%
- population non-conversion rate: 62.53%
- lift: 1.0954

At 20% targeting capacity:

- 399 trialists targeted
- 273 non-conversions captured
- 21.93% of all non-conversions captured
- target-group non-conversion rate: 68.42%
- lift: 1.0942

The model therefore supports prioritisation, but the concentration is modest.

These results do not estimate the causal effect of contacting a high-risk
trialist.

## Robustness

Final monthly ROC-AUC ranges from approximately 0.533 to 0.591.

Platform ROC-AUC:

- Android: 0.559962
- iOS: 0.538092

Billing-period ROC-AUC:

- annual: 0.536551
- monthly: 0.552598

Acquisition-channel ROC-AUC ranges from:

- 0.509113 for paid social
- to 0.578605 for organic

There is no catastrophic overall subgroup failure, but predictive
discrimination is moderate and segment-dependent.

Paid social is especially close to random discrimination and should be treated
as a limitation rather than hidden through further tuning.

## June 2026 boundary sensitivity

On the separate 201-row June 2026 boundary population:

Static logistic:

- Brier score: 0.241041
- log loss: 0.675225
- ROC-AUC: 0.530761

Behavioural logistic:

- Brier score: 0.235261
- log loss: 0.663520
- ROC-AUC: 0.557716

The boundary result is directionally consistent with the primary final test.

It is sensitivity evidence only and was not used for model selection.

## Final interpretation

The Phase 6 evidence supports a simple behavioural logistic model over both
the static comparator and the tested nonlinear challenger.

The improvement is reproducible out of time but modest in magnitude.

The appropriate conclusion is not that Pulse produced a highly accurate
customer-conversion classifier.

The defensible conclusion is that Day-5 behavioural information adds a small
but measurable amount of probability and ranking value beyond static customer
context in this synthetic environment.

The model is suitable as a portfolio demonstration of:

- point-in-time feature engineering
- leakage prevention
- temporal validation
- baseline-first model development
- calibration assessment
- deterministic uncertainty analysis
- capacity-constrained decision utility
- subgroup robustness checks
- locked final holdout evaluation

## Constraints

Pulse uses synthetic customer behaviour.

Predictive ranking is not causal evidence.

Targeting lift does not establish intervention effectiveness.

The final holdout is frozen and must not be used for additional tuning,
feature selection or model-family selection.

## Formal closure

Phase 6 ? Predictive Modelling & Decision Support is **COMPLETE & FORMALLY CLOSED**.

Final closure evidence:

- locked behavioural logistic model retained
- calibration policy: uncalibrated
- development population: 6,411 trials
- locked final test: 1,991 trials from January through May 2026
- June 2026 boundary sensitivity population: 201 trials
- behavioural final-test Brier score: 0.232913
- behavioural final-test log loss: 0.658714
- behavioural final-test ROC-AUC: 0.548994
- behavioural final-test average precision: 0.424815
- behavioural-minus-static Brier delta: -0.002218
- behavioural-minus-static log-loss delta: -0.004940
- paired Brier 95% bootstrap interval: [-0.004362, -0.000143]
- paired log-loss 95% bootstrap interval: [-0.009389, -0.000540]
- final-test probability-quality improvement confirmed under the predeclared rule
- frozen final-results SHA-256:
  `ec1eadb21395b8dfda95399766e1993781c95b9621d8c6d500c9a0a1f429737e`
- final regression baseline: 544 tests passed
- raw source snapshot unchanged

The final holdout is open and frozen.

No further model-family selection, predictor selection, calibration selection or
hyperparameter tuning may use the final-test or June-2026 boundary results.

Phase 6 must not be reopened unless a genuine implementation or analytical
defect is identified.
