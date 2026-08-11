# Pulse Product Analytics & Subscription Intelligence Platform

## Project Specification v1.0

**Status:** Approved  
**Phase:** Phase 1 — Project Design  
**Specification version:** 1.0

---

## 1. Business Scenario

Pulse is a fictional consumer AI productivity application.

Business model:

**Freemium → Free Trial → Monthly/Annual Premium subscription**

Core features:

- AI Assistant
- Smart Tasks
- Document Summariser
- Focus Sessions
- AI Notes

Typical lifecycle:

**Install → Signup → Onboarding → First Value → Product Usage → Paywall → Trial → Paid Subscription → Renewal / Cancellation / Churn**

All generated data is synthetic and created for portfolio purposes.

---

## 2. Dataset Timeframe

Simulation period:

**1 January 2024 – 30 June 2026**

Dataset snapshot:

**1 July 2026 00:00 UTC**

History:

**30 months**

Target scale:

- approximately 100,000–120,000 installations
- approximately 3–5 million product events
- 30 months of activity

The scale should not be increased merely to make the project look larger.

---

## 3. Identity Model

An installation does not automatically represent a registered user.

Before signup:

- `anonymous_id`
- `user_id = NULL`

After signup:

- `anonymous_id`
- `user_id`

This enables realistic Install → Signup conversion analysis and anonymous-to-registered identity resolution.

---

## 4. Core Database Entities

1. `installations`
2. `users`
3. `product_events`
4. `subscriptions`
5. `subscription_transactions`
6. `experiment_assignments`
7. `marketing_spend`
8. `app_releases`

`subscription_transactions` will be treated as the financial source of truth.

---

## 5. Event Taxonomy

### Lifecycle

- `app_install`
- `signup`
- `onboarding_started`
- `onboarding_completed`

### Usage

- `session_started`
- `feature_used`
- `paywall_viewed`

### Subscription

- `trial_started`
- `subscription_started`
- `subscription_renewed`
- `cancellation_requested`
- `subscription_expired`
- `payment_failed`

### Core feature values

For `feature_used`, controlled `feature_name` values are:

- `ai_assistant`
- `smart_tasks`
- `document_summarizer`
- `focus_session`
- `ai_notes`

---

## 6. Architecture

Synthetic configuration  
→ Python synthetic-data engine  
→ Raw files  
→ Python ingestion / validation  
→ PostgreSQL `raw` layer  
→ PostgreSQL `staging` layer  
→ SQL transformations  
→ PostgreSQL `analytics` layer  
→ Statistical / ML analysis  
→ Experimentation / churn / LTV / forecasting / scenarios  
→ Streamlit internal analytics application  
→ Testing and reconciliation

PostgreSQL schemas:

- `raw`
- `staging`
- `analytics`
- `validation`

Streamlit calculations should not operate directly on messy raw data.

---

## 7. Key Definitions

### Meaningful Product Action

A valid `feature_used` event involving one of the five core Pulse features.

### Activation

A signed-up user who:

1. completes onboarding, and
2. performs at least one meaningful product action within 48 hours of signup.

### Time to First Value

Time between `signup_timestamp` and the first meaningful `feature_used` event.

### Primary Funnel

**Install → Signup → Onboarding Completed → Paywall Viewed → Trial Started → Paid Subscription**

Both overall-stage and stage-to-stage conversion will be calculated with documented denominators.

### Active User

A user with meaningful product activity during the relevant period.

Background/system activity must not classify a user as active.

### Retention

Analysis will distinguish:

- D1
- D7
- D30
- weekly retention
- monthly cohort retention
- rolling retention where appropriate

### Churn

The project distinguishes:

- cancellation request
- effective subscription churn
- expiry
- inactivity

Primary ML target:

**Probability that a currently active subscriber experiences effective subscription churn within the following 30 days.**

Target construction must avoid leakage.

### Revenue

The project distinguishes:

- billed/cash revenue
- MRR
- ARPU
- ARPPU

Annual subscription cash receipts must not be treated as equivalent to monthly recurring revenue.

---

## 8. Experiment

Initial experiment:

**Paywall Redesign Experiment**

Variants:

- A — Control
- B — Treatment

Experimental unit:

**user**

Primary metrics:

- trial-start conversion
- paid conversion

Commercial metric:

- revenue per assigned user

Guardrails include:

- engagement
- retention
- cancellation/churn

Analysis should cover:

- hypothesis
- randomisation
- balance checks
- sample-size/power reasoning
- confidence intervals
- statistical significance
- effect size
- practical significance
- guardrails
- business recommendation

---

## 9. Synthetic Behaviour Principles

Synthetic data must contain probabilistic relationships rather than independent random values.

Examples include:

- acquisition channels differ in user quality and CAC
- onboarding completion is associated with activation and retention
- engagement influences conversion and retention
- features have different relationships with retention
- trial behaviour helps predict paid conversion
- engagement decline may precede churn
- monthly and annual subscribers behave differently
- seasonality affects acquisition and usage
- releases may influence behaviour
- experiment treatment has a modest effect

These relationships must not be deterministic.

A separate synthetic ground-truth document will record intentionally simulated relationships.

That document should not be used during normal analysis.

---

## 10. Data Quality

Controlled corruption mechanisms will include examples such as:

- duplicate events
- duplicate transactions
- missing identifiers
- malformed timestamps
- future timestamps
- events before signup
- impossible subscription dates
- negative payments
- orphan records
- unknown events
- invalid country/platform labels
- broken sessions

Corruption mechanisms must be configurable and measurable.

Records may be:

- accepted
- standardised
- flagged
- quarantined
- rejected

Data-quality issues must not simply be cleaned silently.

---

## 11. Technology Stack

Primary technologies:

- Python
- Pandas
- NumPy
- PostgreSQL
- SQL
- scikit-learn
- SciPy / statsmodels where appropriate
- Matplotlib / Plotly
- Streamlit
- Git
- GitHub

Likely supporting packages:

- `psycopg`
- `pytest`

Additional infrastructure should only be introduced where there is a genuine technical requirement.

---

## 12. Implementation Principle

Implementation should proceed incrementally.

Major stages require:

1. explanation
2. technical design
3. implementation
4. validation
5. reconciliation where appropriate
6. documentation

No functionality should be presented as completed until it has actually been implemented and validated.
