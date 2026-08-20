# Pulse Public Deployment Readiness

## Target architecture

GitHub repository -> Streamlit Community Cloud -> Neon PostgreSQL.

## Public database

The public application uses a reduced cloud snapshot of the canonical Pulse
`reporting.*` semantic layer rather than exposing the internal warehouse.

Cloud snapshot:

- database: `pulse_warehouse`
- reporting rows: 88,105
- approximate reporting snapshot size: 9.74 MB
- ingestion batch: 1
- analytics build: 1

The snapshot reconciles exactly to the local canonical reporting layer for all
relations and all dashboard queries used by the application.

## Application database role

The deployed application uses:

`pulse_streamlit`

The role:

- can connect to `pulse_warehouse`;
- has `USAGE` on `reporting`;
- has `SELECT` on reporting relations;
- defaults to read-only transactions;
- cannot create or modify reporting objects.

The Neon pooled endpoint is used for application traffic.

## Secret handling

Database credentials must be stored in Streamlit Community Cloud secrets.

`.streamlit/secrets.toml` is local-only and must never be committed.

Required root-level deployment secrets:

- `PULSE_DB_HOST`
- `PULSE_DB_PORT`
- `PULSE_DB_NAME`
- `PULSE_DB_USER`
- `PULSE_DB_PASSWORD`
- `PULSE_DB_CONNECT_TIMEOUT`
- `PGSSLMODE`
- `PGCHANNELBINDING`

## Frozen analytical evidence

Phase 5 inference is not recomputed during dashboard use.

The Phase 6 final holdout remains OPEN AND FROZEN.

Required final-results SHA-256:

`ec1eadb21395b8dfda95399766e1993781c95b9621d8c6d500c9a0a1f429737e`

## Public interpretation boundary

Pulse uses synthetic customer behaviour.

Predictive ranking is not causal evidence.

Targeting lift does not estimate intervention effectiveness.

## Public deployment verification

Public deployment status:

**SUCCESSFUL**

Public application:

`https://pulse-appuct-analytics-zbqpxugy9bvxpxkcstwm4t.streamlit.app/`

Deployment architecture:

`GitHub -> Streamlit Community Cloud -> Neon PostgreSQL`

Seven-page public QA:

**7/7 PASS**

Validated public views:

1. Executive Overview
2. Growth & Acquisition
3. Engagement & Monetisation
4. Retention & Lifecycle
5. Experiments
6. Predictive Decision Support
7. Methodology & Contracts

Public QA confirmed:

- synthetic-data disclosure remains visible;
- ingestion lineage remains batch 1;
- analytics lineage remains build 1;
- the canonical observation cutoff renders correctly;
- live business KPIs remain sourced from `reporting.*`;
- Phase 5 inference remains frozen and is not rerun by the dashboard;
- Phase 6 final-test evidence remains frozen and is not used for further tuning;
- predictive ranking is not presented as causal evidence;
- successful billed collection is not presented as accounting-recognised or net revenue;
- the canonical metric registry and analytical boundaries render publicly.

## Phase 7 Step 5 closure

Phase 7 Step 5 ? UX, Portfolio Documentation & Public Deployment is:

**COMPLETE & CLOSED**

Closure evidence:

- public Streamlit deployment: successful;
- anonymous browser access: verified without authentication;
- seven-page public QA: 7/7 PASS;
- targeted Step 5 tests: 27/27 PASS;
- full regression: 581/581 PASS;
- repository UTF-8/mojibake diagnostic: PASS;
- protected `data/raw/` snapshot: unchanged;
- frozen Phase 6 final-holdout SHA-256: verified unchanged;
- `.streamlit/secrets.toml`: ignored and untracked.

Phase 7 remains open only for the separate formal Phase 7 project-level
closure step.
