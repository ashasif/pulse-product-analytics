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