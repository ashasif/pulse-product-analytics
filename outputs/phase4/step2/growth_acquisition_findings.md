# Pulse Phase 4 — Growth, Funnel & Acquisition Findings

> Pulse and all analysed data are synthetic and exist solely for portfolio and learning purposes.

## Analysis context

- Ingestion batch: `1`
- Analytics build: `1`
- Observation cutoff: `2026-07-01T00:59:36+01:00`
- Business source of truth: `reporting.*`

## Growth: H1 2024 vs H1 2026

| Measure | H1 2024 | H1 2026 | Change |
|---|---:|---:|---:|
| Installations | 13,629 | 26,947 | +97.72% |
| Signups | 8,475 | 16,772 | +97.90% |
| Trial starts | 858 | 2,252 | +162.47% |
| Paid subscription starts | 294 | 866 | +194.56% |

The comparison uses the same January-to-June calendar window in each year so the incomplete 2026 calendar year is not compared with a full prior year.

## Core acquisition and onboarding funnel

- Installations: **100,000**
- Installations with signup: **62,176**
- Install → signup: **62.18%**
- Registered users: **62,176**
- Onboarding started: **55,220**
- Onboarding start rate: **88.81%**
- Onboarding completed: **43,056**
- Onboarding completion rate: **69.25%**

## Acquisition channel performance

| Channel | Spend | Installs | Install → signup | CPI | CTR |
|---|---:|---:|---:|---:|---:|
| content | £14,122.10 | 8,153 | 64.53% | £1.73 | n/a |
| organic | £0.00 | 38,317 | 62.47% | £0.00 | n/a |
| paid_search | £55,189.61 | 18,045 | 62.99% | £3.06 | 5.10% |
| paid_social | £46,691.75 | 23,605 | 56.69% | £1.98 | 1.25% |
| referral | £9,148.57 | 11,880 | 69.28% | £0.77 | n/a |

## Decision-oriented observations

1. **Acquisition scale:** `organic` generated the highest installation volume in the approved snapshot (38,317 installs).
2. **Signup efficiency:** `referral` had the highest aggregated install-to-signup rate (69.28%).
3. **Acquisition cost efficiency:** `referral` had the lowest aggregated cost per install among channels with a positive measured CPI (£0.77).
4. **Spend concentration:** `paid_search` received the highest total marketing spend (£55,189.61).

These are descriptive relationships in synthetic data. They do not establish that acquisition channel caused downstream behaviour.

## What should be investigated next?

- Compare acquisition efficiency with downstream trial and paid retention before recommending budget changes.
- Investigate whether platform differences explain part of the observed install-to-signup variation.
- Examine engagement and feature-use patterns after signup to determine where acquired users create product value.
- Preserve cohort maturity rules when moving into subscription conversion and retention analysis.

## Interpretation boundaries

- Cost per install is channel-level, not campaign-attributed CAC.
- Successful payment collection is not analysed in this step.
- No LTV, recognised revenue or net revenue is inferred.
- No statistical or causal claims are made.
