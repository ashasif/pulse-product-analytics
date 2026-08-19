# Pulse Phase 5 - Continuous Commercial Outcome Inference

> Pulse is synthetic. The monetary outcome represents successful billed payment collection, not accounting-recognised revenue, net revenue, profit or LTV.

## Production context

- Ingestion batch: `1`
- Analytics build: `1`
- Observation cutoff: `2026-07-01T00:59:36+01:00`
- Primary population: `assigned_mature`

## Distribution diagnostics

- Control users: 1,341
- Treatment users: 1,364
- Control zero-collection rate: 89.19%
- Treatment zero-collection rate: 89.30%
- Observed control support: `[0.0, 11.99, 99.99]`
- Observed treatment support: `[0.0, 11.99, 99.99]`

## Mean collection inference

- Control mean: £3.1995
- Treatment mean: £3.4769
- Treatment minus control: £0.2774
- Relative mean difference: 8.67%
- Bootstrap 95% CI: [£-0.8993, £1.4410]
- Randomization permutation p-value: 0.644536
- Statistically detectable at alpha 0.05: No

## Method

- Bootstrap replicates: 10,000
- Permutation replicates: 10,000
- Bootstrap seed: `5202026`
- Permutation seed: `5202027`
- Confidence interval: non-parametric percentile bootstrap of treatment-minus-control mean.
- Hypothesis test: randomized-label permutation test with fixed observed group sizes.

## Interpretation

- The commercial estimand is the arithmetic mean across all assigned-mature users, including users with £0 collection.
- Positive-only users are not used as the primary population.
- The zero-heavy discrete distribution is why the Phase 5 primary method uses resampling rather than assuming normally distributed user-level collection.
- Statistical detectability alone is not a rollout decision.
