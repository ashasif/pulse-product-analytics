# Pulse Reporting Consumer Contract

This is a read-only consumer contract. The supported SQL boundary is `reporting.*`.

Canonical group role: `pulse_reporting_reader`.

Role properties: NOLOGIN, NOSUPERUSER, INHERIT, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS.

Allowed: USAGE on `reporting`; SELECT on current and future reporting tables/views created by `pulse_app`.

Prohibited direct access: raw, staging, validation, analytics. No INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER or CREATE on reporting.

Canonical metrics live in `reporting.metric_definitions`: 30 supported, 5 deferred, 4 unsupported.

Revenue means successful billed payment collection, not accounting-recognised or net revenue.

Trial conversion and D30/D90/D180/D365 retention use mature denominators only.

Experiment reporting is descriptive only and does not provide p-values, confidence intervals, significance declarations, causal lift or treatment-effect estimates.

Performance-supported paths use `analytics.ix_fact_product_event_daily_reporting`, `analytics.ix_fact_product_event_feature_reporting`, and `analytics.ix_fact_product_event_time`.
