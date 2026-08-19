# Pulse Phase 4 — Business Synthesis

> Pulse and all analysed data are synthetic and exist solely for portfolio and learning purposes.

## Executive view

Pulse's synthetic dataset shows strong top-of-funnel growth and reasonable early paid retention, but much weaker long-horizon paid persistence.

The current reporting snapshot contains **100,000 installations**, with an install-to-signup rate of **62.18%**.
Mature trial-to-paid conversion is **37.31%**, while D30 paid retention is **73.26%**.
By D365, retention falls to **9.74%** among 1,510 eligible subscriptions.

## Business priorities

### 1. Long-term paid retention

D30 retention is **73.26%**, D90 is **51.51%**, D180 is **37.92%**, and D365 is **9.74%**.

The largest business issue visible in the current snapshot is therefore not initial paid activation alone, but maintaining subscriptions over longer horizons. The next product questions should focus on lifecycle drop-off, feature value and renewal behaviour rather than simply increasing acquisition volume.

### 2. Acquisition quality, not just acquisition volume

`referral` has the highest observed install-to-signup rate at **69.28%**.
`referral` also has the lowest positive channel-level CPI at **£0.77**.
The strongest observed D365 retention among acquisition channels is `referral` at **11.86%**.

These cross-stage patterns are useful for prioritising further investigation, but they do not prove that acquisition channel caused better downstream retention.

### 3. Payment reliability

The payment failure rate is **4.67%**, while renewal attempt success is **95.43%**.
Successful billed payment collection totals **£176,562.87**.

Payment failure remains measurable friction, but the current snapshot does not support recognised revenue, net revenue, profit or customer lifetime value conclusions.

### 4. Feature engagement concentration

`ai_assistant` is the highest-volume feature with **739,182 feature-use events**, representing **31.95%** of all feature-use events.

This establishes usage concentration, not which feature causes retention or commercial value.

### 5. Experiments as hypothesis-generating evidence

The reporting layer currently provides **3 descriptive variant comparison(s)** across the configured experiments.

Observed variant differences can identify areas worth deeper investigation, but Phase 4 deliberately does not convert those differences into causal lift or statistical-significance claims.

## Recommended next investigations

1. Examine which product behaviours precede the largest retention losses between D30, D90 and D180.
2. Compare referral-acquired users with other channels across engagement, paid conversion and longer-horizon retention.
3. Investigate payment-failure timing and whether failed attempts cluster around specific renewal stages.
4. Examine whether high AI Assistant usage is associated with stronger retention while keeping the analysis explicitly observational.
5. Treat experiment differences as hypotheses requiring a later approved statistical methodology before making causal claims.

## Governance and interpretation boundaries

- Source of truth: `reporting.*`
- Only supported metric contracts are used.
- Cohort maturity rules are preserved.
- Successful payment collection is not accounting revenue.
- Channel CPI is not campaign-attributed CAC.
- No LTV, MAU, recognised revenue or net revenue is invented.
- Experiment outputs remain descriptive only.
- All data are synthetic.

## Analysis lineage

- Ingestion batch: `1`
- Analytics build: `1`
- Observation cutoff: `2026-07-01T00:59:36+01:00`
