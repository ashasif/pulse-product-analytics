BEGIN;

COMMENT ON TABLE analytics.build_runs IS 'Analytics build control table. One row per analytics build with upstream ingestion and promotion lineage.';
COMMENT ON TABLE analytics.dim_date IS 'Conformed calendar dimension. One row per calendar date.';
COMMENT ON TABLE analytics.dim_installation IS 'Conformed installation dimension with acquisition and platform attributes.';
COMMENT ON TABLE analytics.dim_user IS 'Conformed registered-user dimension with signup and onboarding lifecycle attributes.';
COMMENT ON TABLE analytics.dim_experiment IS 'Experiment metadata dimension with configured metrics and analysis-window definitions.';
COMMENT ON TABLE analytics.dim_app_release IS 'Application release dimension containing release metadata by platform.';
COMMENT ON TABLE analytics.fact_product_event IS 'Product-event fact. One row per product event and the primary behavioural reporting source.';
COMMENT ON TABLE analytics.fact_subscription IS 'Subscription lifecycle fact containing trial, paid-start, billing and expiry state.';
COMMENT ON TABLE analytics.fact_subscription_transaction IS 'Payment-attempt fact. Successful amounts represent billed payment collection, not accounting-recognised or net revenue.';
COMMENT ON TABLE analytics.fact_experiment_assignment IS 'Experiment-assignment fact. Downstream reporting is descriptive and does not imply causal inference.';
COMMENT ON TABLE analytics.fact_marketing_spend IS 'Marketing-spend fact used for weekly acquisition and paid-channel reporting.';

COMMIT;
