"""Approved reporting-layer queries used by the Phase 7 application.

Business-facing database access must remain inside reporting.*.
Canonical KPI definitions are owned by the PostgreSQL reporting
semantic layer rather than recreated in Python.
"""

from __future__ import annotations


REPORTING_CONTEXT_SQL = """
SELECT
    ingestion_batch_id,
    analytics_build_run_id,
    observation_cutoff_at
FROM reporting.vw_observation_cutoff
ORDER BY analytics_build_run_id DESC
LIMIT 1
"""


SUPPORTED_METRICS_SQL = """
SELECT
    metric_key,
    metric_name,
    metric_domain,
    metric_grain,
    metric_unit,
    support_status,
    definition,
    denominator_definition,
    caveat
FROM reporting.metric_definitions
WHERE support_status = 'supported'
ORDER BY metric_domain, metric_name
"""


APP_QUERY_REGISTRY: dict[str, str] = {
    "reporting_context": REPORTING_CONTEXT_SQL,
    "supported_metrics": SUPPORTED_METRICS_SQL,
}