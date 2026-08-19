# Pulse Phase 4 — Engagement, Monetisation & Retention Findings

> Pulse and all analysed data are synthetic and exist solely for portfolio and learning purposes.

## Analysis context

- Ingestion batch: `1`
- Analytics build: `1`
- Observation cutoff: `2026-07-01T00:59:36+01:00`
- Business source of truth: `reporting.*`

## Product engagement

- Sessions started: **837,333**
- Feature-use events: **2,313,519**
- Average of monthly average registered DAU: **685**
- Highest-volume feature: **ai_assistant** (739,182 feature-use events)
- Share of all feature-use events: **31.95%**

The DAU figure above is an average of canonical daily active user measurements. It is not monthly active users and does not deduplicate users across calendar days.

## Billing and successful payment collection

- Payment attempts: **9,350**
- Successful payments: **8,913**
- Failed payments: **437**
- Payment failure rate: **4.67%**
- Successful billed payment collection: **£176,562.87**
- Renewal attempts: **5,970**
- Renewal success rate: **95.43%**

`successful_payment_revenue_gbp` is successful billed payment collection. It is not accounting-recognised revenue, net revenue or profit.

## Trial conversion

- Trials: **8,663**
- Mature trials: **8,619**
- Immature trials excluded from denominator: **44**
- Mature paid conversions: **3,216**
- Mature trial → paid: **37.31%**

## Paid retention

| Horizon | Eligible | Retained | Rate |
|---|---:|---:|---:|
| D30 | 3,108 | 2,277 | 73.26% |
| D90 | 2,807 | 1,446 | 51.51% |
| D180 | 2,355 | 893 | 37.92% |
| D365 | 1,510 | 147 | 9.74% |

Each retention denominator contains only subscriptions mature enough to have reached the relevant observation horizon.

## Decision-oriented interpretation

1. Acquisition growth should be evaluated together with downstream product engagement rather than install volume alone.
2. Payment failure and renewal performance identify commercial friction after customers have already entered the paid lifecycle.
3. The decline from D30 through D365 retention should be treated as a lifecycle problem requiring cohort and segment comparison, not as evidence of one specific cause.
4. Acquisition-channel efficiency from Step 2 should be compared with channel-level paid retention before any synthetic budget reallocation recommendation.

## Interpretation boundaries

- No monthly active user metric is invented.
- No customer LTV is inferred.
- No recognised or net revenue is inferred.
- Retention rates use mature denominators.
- Rates are rolled up from canonical numerator and denominator components rather than averaged across cohorts.
- No causal claim is made from descriptive segment differences.
