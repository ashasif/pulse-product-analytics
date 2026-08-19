# Phase 6 — Final Holdout Evaluation

## Locked evaluation

- development rows: 6,411
- final test rows: 1,991
- June 2026 boundary rows: 201
- selected model: `behavioural_logistic`
- calibration: `uncalibrated`

## Final test model comparison

| Model | Brier | Log loss | ROC-AUC | Average precision | Mean prediction | Observed conversion |
|---|---:|---:|---:|---:|---:|---:|
| prevalence | 0.234303 | 0.661416 | 0.500000 | 0.374686 | 0.372173 | 0.374686 |
| static_logistic | 0.235131 | 0.663654 | 0.522154 | 0.396435 | 0.369756 | 0.374686 |
| behavioural_logistic | 0.232913 | 0.658714 | 0.548994 | 0.424815 | 0.371363 | 0.374686 |

## Final generalisation decision

**Behavioural probability-quality improvement confirmed: True.**

Behavioural minus static:

- Brier delta: -0.002218
- log-loss delta: -0.004940

Paired 95% bootstrap intervals:

- Brier delta: [-0.004362, -0.000143]
- log-loss delta: [-0.009389, -0.000540]
- bootstrap replicates: 2,000
- bootstrap seed: 20260819

Negative deltas favour the behavioural model.

## Reliability deciles

| Bin | n | Mean predicted conversion | Observed conversion | Gap |
|---:|---:|---:|---:|---:|
| 1 | 200 | 0.2825 | 0.3150 | -0.0325 |
| 2 | 199 | 0.3159 | 0.3166 | -0.0006 |
| 3 | 199 | 0.3318 | 0.3769 | -0.0450 |
| 4 | 199 | 0.3431 | 0.3618 | -0.0187 |
| 5 | 199 | 0.3534 | 0.3618 | -0.0084 |
| 6 | 199 | 0.3654 | 0.3568 | +0.0086 |
| 7 | 199 | 0.3831 | 0.3869 | -0.0038 |
| 8 | 199 | 0.4031 | 0.3618 | +0.0413 |
| 9 | 199 | 0.4310 | 0.4121 | +0.0189 |
| 10 | 199 | 0.5045 | 0.4975 | +0.0070 |

## Non-conversion targeting utility

| Capacity | Targeted | Non-conversions captured | Capture rate | Target-group non-conversion rate | Population non-conversion rate | Lift |
|---:|---:|---:|---:|---:|---:|---:|
| 10% | 200 | 137 | 0.1100 | 0.6850 | 0.6253 | 1.0954 |
| 20% | 399 | 273 | 0.2193 | 0.6842 | 0.6253 | 1.0942 |
| 30% | 598 | 397 | 0.3189 | 0.6639 | 0.6253 | 1.0617 |

## Final-test robustness

### month

| Group | n | Conversion | Mean prediction | Brier | Log loss | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2026-01 | 414 | 0.3575 | 0.3689 | 0.231281 | 0.655290 | 0.533885 | 0.386551 |
| 2026-02 | 385 | 0.3740 | 0.3725 | 0.233624 | 0.660016 | 0.533109 | 0.419740 |
| 2026-03 | 396 | 0.4066 | 0.3743 | 0.237346 | 0.667659 | 0.591384 | 0.494625 |
| 2026-04 | 390 | 0.3436 | 0.3703 | 0.226139 | 0.644636 | 0.541016 | 0.388923 |
| 2026-05 | 406 | 0.3916 | 0.3710 | 0.236088 | 0.665771 | 0.545235 | 0.479280 |

### platform

| Group | n | Conversion | Mean prediction | Brier | Log loss | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| android | 1032 | 0.3915 | 0.3679 | 0.236334 | 0.665844 | 0.559962 | 0.452884 |
| ios | 959 | 0.3566 | 0.3751 | 0.229233 | 0.651042 | 0.538092 | 0.399236 |

### billing_period

| Group | n | Conversion | Mean prediction | Brier | Log loss | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| annual | 433 | 0.3580 | 0.3810 | 0.229872 | 0.652093 | 0.536551 | 0.397113 |
| monthly | 1558 | 0.3793 | 0.3687 | 0.233759 | 0.660554 | 0.552598 | 0.435593 |

### acquisition_channel

| Group | n | Conversion | Mean prediction | Brier | Log loss | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| content | 158 | 0.3734 | 0.3743 | 0.236240 | 0.665893 | 0.540147 | 0.397498 |
| organic | 790 | 0.3797 | 0.3705 | 0.231053 | 0.654731 | 0.578605 | 0.466191 |
| paid_search | 400 | 0.3875 | 0.3721 | 0.234605 | 0.662257 | 0.545385 | 0.461410 |
| paid_social | 402 | 0.3557 | 0.3656 | 0.232847 | 0.658839 | 0.509113 | 0.368703 |
| referral | 241 | 0.3693 | 0.3809 | 0.234132 | 0.660978 | 0.529494 | 0.404470 |

## June 2026 boundary sensitivity

| Model | Brier | Log loss | ROC-AUC | Average precision | Mean prediction | Observed conversion |
|---|---:|---:|---:|---:|---:|---:|
| prevalence | 0.241537 | 0.676214 | 0.500000 | 0.402985 | 0.372173 | 0.402985 |
| static_logistic | 0.241041 | 0.675225 | 0.530761 | 0.431976 | 0.371573 | 0.402985 |
| behavioural_logistic | 0.235261 | 0.663520 | 0.557716 | 0.528333 | 0.362349 | 0.402985 |

## Interpretation constraints

- Pulse uses synthetic customer behaviour.
- Predictive ranking is not causal evidence.
- Targeting utility does not estimate intervention effectiveness.
- Final-test results cannot be used for further model tuning.
- June 2026 is sensitivity evidence, not a second test set for selection.
