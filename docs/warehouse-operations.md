# Pulse Warehouse Operations

PostgreSQL 18.4; database `pulse_warehouse`; object owner `pulse_app`; reporting group role `pulse_reporting_reader`.

Do not modify `data/raw/`.

## Step 7 deployment order
- `009_harden_observation_cutoff.sql`
- `010_add_reporting_performance_indexes.sql`
- `011_optimize_feature_engagement_view.sql`
- `012_admin_create_reporting_reader.sql`
- `013_grant_reporting_reader.sql`
- `014_comment_analytics_objects.sql`

`012_admin_create_reporting_reader.sql` requires an administrator with CREATEROLE. `pulse_app` intentionally does not have CREATEROLE. `013_grant_reporting_reader.sql` is run by `pulse_app`.

Performance indexes were adopted only after production-scale `EXPLAIN (ANALYZE, BUFFERS)` evidence. No planner-forcing configuration or permanent global `work_mem` change was introduced.

Before Phase 3 closure: run the full Python test suite; confirm analytics validation; confirm reporting validation; run Step 7 readiness validation; prove SQL idempotency; prove reader SELECT and write/internal-schema denial; verify hardened indexes/plans; verify clean Git state and remote parity.

Regression command: `python -m unittest discover -s tests -p "test_*.py"`

Passwords and connection secrets must not be committed.
