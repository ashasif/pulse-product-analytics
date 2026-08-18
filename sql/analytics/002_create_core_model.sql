-- Pulse
-- Phase 3, Step 5
-- Core analytics dimensional model.
--
-- Staging remains immutable.
-- Analytics tables use warehouse surrogate keys while retaining
-- source business identifiers and sufficient lineage for auditability.

BEGIN;


-- ============================================================
-- DATE DIMENSION
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.dim_date (
    date_key INTEGER PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,

    calendar_year SMALLINT NOT NULL,
    calendar_quarter SMALLINT NOT NULL,
    month_number SMALLINT NOT NULL,
    month_name TEXT NOT NULL,
    iso_week SMALLINT NOT NULL,
    day_of_month SMALLINT NOT NULL,
    day_of_week SMALLINT NOT NULL,
    day_name TEXT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);


-- ============================================================
-- INSTALLATION DIMENSION
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.dim_installation (
    installation_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    installation_id TEXT NOT NULL,

    anonymous_id TEXT NOT NULL,
    installed_at TIMESTAMPTZ NOT NULL,
    installed_date_key INTEGER NOT NULL,

    platform TEXT NOT NULL,
    acquisition_channel TEXT NOT NULL,
    country_code TEXT NOT NULL,

    validation_run_id BIGINT NOT NULL,
    analytics_build_run_id BIGINT NOT NULL,

    source_row_number BIGINT NOT NULL,
    row_hash TEXT NOT NULL,

    CONSTRAINT dim_installation_business_key_uk
        UNIQUE (ingestion_batch_id, installation_id),

    CONSTRAINT dim_installation_source_row_uk
        UNIQUE (ingestion_batch_id, source_row_number),

    CONSTRAINT dim_installation_batch_fk
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batches (ingestion_batch_id)
        ON DELETE RESTRICT,

    CONSTRAINT dim_installation_date_fk
        FOREIGN KEY (installed_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT dim_installation_validation_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT dim_installation_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (analytics_build_run_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- USER DIMENSION
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.dim_user (
    user_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    user_id TEXT NOT NULL,

    installation_key BIGINT NOT NULL,

    signed_up_at TIMESTAMPTZ NOT NULL,
    signed_up_date_key INTEGER NOT NULL,

    onboarding_started_at TIMESTAMPTZ,
    onboarding_completed_at TIMESTAMPTZ,

    validation_run_id BIGINT NOT NULL,
    analytics_build_run_id BIGINT NOT NULL,

    source_row_number BIGINT NOT NULL,
    row_hash TEXT NOT NULL,

    CONSTRAINT dim_user_business_key_uk
        UNIQUE (ingestion_batch_id, user_id),

    CONSTRAINT dim_user_source_row_uk
        UNIQUE (ingestion_batch_id, source_row_number),

    CONSTRAINT dim_user_installation_fk
        FOREIGN KEY (installation_key)
        REFERENCES analytics.dim_installation (installation_key)
        ON DELETE RESTRICT,

    CONSTRAINT dim_user_date_fk
        FOREIGN KEY (signed_up_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT dim_user_validation_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT dim_user_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (analytics_build_run_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- EXPERIMENT DIMENSION
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.dim_experiment (
    experiment_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    experiment_id TEXT NOT NULL,

    experiment_name TEXT NOT NULL,
    randomization_unit TEXT NOT NULL,

    experiment_start_at TIMESTAMPTZ NOT NULL,
    experiment_end_at TIMESTAMPTZ NOT NULL,

    eligibility_rule TEXT NOT NULL,
    assignment_trigger TEXT NOT NULL,
    exposure_trigger TEXT NOT NULL,
    hypothesis TEXT NOT NULL,

    primary_metric TEXT NOT NULL,
    secondary_metric TEXT NOT NULL,
    commercial_metric TEXT NOT NULL,
    guardrail_metric TEXT NOT NULL,

    analysis_window_days INTEGER NOT NULL,

    analytics_build_run_id BIGINT NOT NULL,

    CONSTRAINT dim_experiment_business_key_uk
        UNIQUE (ingestion_batch_id, experiment_id),

    CONSTRAINT dim_experiment_batch_fk
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batches (ingestion_batch_id)
        ON DELETE RESTRICT,

    CONSTRAINT dim_experiment_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (analytics_build_run_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- APP RELEASE DIMENSION
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.dim_app_release (
    app_release_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    app_release_id TEXT NOT NULL,

    release_key TEXT NOT NULL,
    release_name TEXT NOT NULL,
    release_sequence INTEGER NOT NULL,

    platform TEXT NOT NULL,
    version TEXT NOT NULL,

    release_at TIMESTAMPTZ NOT NULL,
    release_date_key INTEGER NOT NULL,

    release_type TEXT NOT NULL,
    feature_area TEXT NOT NULL,

    rollout_strategy TEXT NOT NULL,
    rollout_days INTEGER NOT NULL,
    rollout_complete_at TIMESTAMPTZ NOT NULL,

    release_channel TEXT NOT NULL,
    release_notes TEXT NOT NULL,

    validation_run_id BIGINT NOT NULL,
    analytics_build_run_id BIGINT NOT NULL,

    source_row_number BIGINT NOT NULL,
    row_hash TEXT NOT NULL,

    CONSTRAINT dim_app_release_business_key_uk
        UNIQUE (ingestion_batch_id, app_release_id),

    CONSTRAINT dim_app_release_source_row_uk
        UNIQUE (ingestion_batch_id, source_row_number),

    CONSTRAINT dim_app_release_date_fk
        FOREIGN KEY (release_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT dim_app_release_validation_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT dim_app_release_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (analytics_build_run_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- PRODUCT EVENT FACT
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.fact_product_event (
    product_event_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    event_id TEXT NOT NULL,

    event_name TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    occurred_date_key INTEGER NOT NULL,

    installation_key BIGINT NOT NULL,
    user_key BIGINT,

    session_id TEXT,
    feature_name TEXT,

    validation_run_id BIGINT NOT NULL,
    analytics_build_run_id BIGINT NOT NULL,

    source_row_number BIGINT NOT NULL,
    row_hash TEXT NOT NULL,

    CONSTRAINT fact_product_event_business_key_uk
        UNIQUE (ingestion_batch_id, event_id),

    CONSTRAINT fact_product_event_source_row_uk
        UNIQUE (ingestion_batch_id, source_row_number),

    CONSTRAINT fact_product_event_date_fk
        FOREIGN KEY (occurred_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_product_event_installation_fk
        FOREIGN KEY (installation_key)
        REFERENCES analytics.dim_installation (installation_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_product_event_user_fk
        FOREIGN KEY (user_key)
        REFERENCES analytics.dim_user (user_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_product_event_validation_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fact_product_event_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (analytics_build_run_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- SUBSCRIPTION ACCUMULATING FACT
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.fact_subscription (
    subscription_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    subscription_id TEXT NOT NULL,

    user_key BIGINT NOT NULL,
    installation_key BIGINT NOT NULL,

    billing_period TEXT NOT NULL,
    price_gbp NUMERIC NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,

    trial_started_at TIMESTAMPTZ NOT NULL,
    trial_started_date_key INTEGER NOT NULL,

    trial_ends_at TIMESTAMPTZ NOT NULL,

    subscription_started_at TIMESTAMPTZ,
    subscription_started_date_key INTEGER,

    current_period_start_at TIMESTAMPTZ,
    current_period_end_at TIMESTAMPTZ,

    cancellation_requested_at TIMESTAMPTZ,

    expired_at TIMESTAMPTZ,
    expired_date_key INTEGER,

    auto_renew BOOLEAN NOT NULL,
    end_reason TEXT,

    validation_run_id BIGINT NOT NULL,
    analytics_build_run_id BIGINT NOT NULL,

    source_row_number BIGINT NOT NULL,
    row_hash TEXT NOT NULL,

    CONSTRAINT fact_subscription_business_key_uk
        UNIQUE (ingestion_batch_id, subscription_id),

    CONSTRAINT fact_subscription_source_row_uk
        UNIQUE (ingestion_batch_id, source_row_number),

    CONSTRAINT fact_subscription_user_fk
        FOREIGN KEY (user_key)
        REFERENCES analytics.dim_user (user_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_installation_fk
        FOREIGN KEY (installation_key)
        REFERENCES analytics.dim_installation (installation_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_trial_date_fk
        FOREIGN KEY (trial_started_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_started_date_fk
        FOREIGN KEY (subscription_started_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_expired_date_fk
        FOREIGN KEY (expired_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_validation_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (analytics_build_run_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- SUBSCRIPTION TRANSACTION FACT
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.fact_subscription_transaction (
    subscription_transaction_key
        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    transaction_id TEXT NOT NULL,

    subscription_key BIGINT NOT NULL,
    user_key BIGINT NOT NULL,
    installation_key BIGINT NOT NULL,

    transaction_type TEXT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL,
    attempted_date_key INTEGER NOT NULL,

    billing_period TEXT NOT NULL,
    amount_gbp NUMERIC NOT NULL,
    currency TEXT NOT NULL,
    payment_status TEXT NOT NULL,

    billing_cycle_number INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,

    validation_run_id BIGINT NOT NULL,
    analytics_build_run_id BIGINT NOT NULL,

    source_row_number BIGINT NOT NULL,
    row_hash TEXT NOT NULL,

    CONSTRAINT fact_subscription_transaction_business_key_uk
        UNIQUE (ingestion_batch_id, transaction_id),

    CONSTRAINT fact_subscription_transaction_source_row_uk
        UNIQUE (ingestion_batch_id, source_row_number),

    CONSTRAINT fact_subscription_transaction_subscription_fk
        FOREIGN KEY (subscription_key)
        REFERENCES analytics.fact_subscription (subscription_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_transaction_user_fk
        FOREIGN KEY (user_key)
        REFERENCES analytics.dim_user (user_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_transaction_installation_fk
        FOREIGN KEY (installation_key)
        REFERENCES analytics.dim_installation (installation_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_transaction_date_fk
        FOREIGN KEY (attempted_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_transaction_validation_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fact_subscription_transaction_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (analytics_build_run_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- EXPERIMENT ASSIGNMENT FACT
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.fact_experiment_assignment (
    experiment_assignment_key
        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    assignment_id TEXT NOT NULL,

    experiment_key BIGINT NOT NULL,
    user_key BIGINT NOT NULL,
    installation_key BIGINT NOT NULL,

    variant TEXT NOT NULL,
    allocation_probability NUMERIC NOT NULL,

    assignment_at TIMESTAMPTZ NOT NULL,
    assignment_date_key INTEGER NOT NULL,

    exposed_at TIMESTAMPTZ,
    exposed_date_key INTEGER,

    validation_run_id BIGINT NOT NULL,
    analytics_build_run_id BIGINT NOT NULL,

    source_row_number BIGINT NOT NULL,
    row_hash TEXT NOT NULL,

    CONSTRAINT fact_experiment_assignment_business_key_uk
        UNIQUE (ingestion_batch_id, assignment_id),

    CONSTRAINT fact_experiment_assignment_source_row_uk
        UNIQUE (ingestion_batch_id, source_row_number),

    CONSTRAINT fact_experiment_assignment_experiment_fk
        FOREIGN KEY (experiment_key)
        REFERENCES analytics.dim_experiment (experiment_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_experiment_assignment_user_fk
        FOREIGN KEY (user_key)
        REFERENCES analytics.dim_user (user_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_experiment_assignment_installation_fk
        FOREIGN KEY (installation_key)
        REFERENCES analytics.dim_installation (installation_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_experiment_assignment_date_fk
        FOREIGN KEY (assignment_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_experiment_assignment_exposed_date_fk
        FOREIGN KEY (exposed_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_experiment_assignment_validation_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fact_experiment_assignment_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (analytics_build_run_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- MARKETING SPEND FACT
-- ============================================================

CREATE TABLE IF NOT EXISTS analytics.fact_marketing_spend (
    marketing_spend_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ingestion_batch_id BIGINT NOT NULL,
    marketing_spend_id TEXT NOT NULL,

    period_start DATE NOT NULL,
    period_start_date_key INTEGER NOT NULL,

    period_end DATE NOT NULL,
    period_end_date_key INTEGER NOT NULL,

    acquisition_channel TEXT NOT NULL,
    spend_type TEXT NOT NULL,
    campaign_type TEXT NOT NULL,

    spend NUMERIC NOT NULL,
    currency TEXT NOT NULL,

    impressions INTEGER,
    clicks INTEGER,

    validation_run_id BIGINT NOT NULL,
    analytics_build_run_id BIGINT NOT NULL,

    source_row_number BIGINT NOT NULL,
    row_hash TEXT NOT NULL,

    CONSTRAINT fact_marketing_spend_business_key_uk
        UNIQUE (ingestion_batch_id, marketing_spend_id),

    CONSTRAINT fact_marketing_spend_source_row_uk
        UNIQUE (ingestion_batch_id, source_row_number),

    CONSTRAINT fact_marketing_spend_start_date_fk
        FOREIGN KEY (period_start_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_marketing_spend_end_date_fk
        FOREIGN KEY (period_end_date_key)
        REFERENCES analytics.dim_date (date_key)
        ON DELETE RESTRICT,

    CONSTRAINT fact_marketing_spend_validation_fk
        FOREIGN KEY (validation_run_id)
        REFERENCES validation.validation_runs (validation_run_id)
        ON DELETE RESTRICT,

    CONSTRAINT fact_marketing_spend_build_fk
        FOREIGN KEY (analytics_build_run_id)
        REFERENCES analytics.build_runs (analytics_build_run_id)
        ON DELETE RESTRICT
);


-- ============================================================
-- ANALYTICAL ACCESS INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS
    ix_dim_installation_batch_channel
ON analytics.dim_installation (
    ingestion_batch_id,
    acquisition_channel
);

CREATE INDEX IF NOT EXISTS
    ix_dim_installation_batch_platform
ON analytics.dim_installation (
    ingestion_batch_id,
    platform
);

CREATE INDEX IF NOT EXISTS
    ix_dim_user_installation
ON analytics.dim_user (installation_key);

CREATE INDEX IF NOT EXISTS
    ix_fact_product_event_time
ON analytics.fact_product_event (
    ingestion_batch_id,
    occurred_at
);

CREATE INDEX IF NOT EXISTS
    ix_fact_product_event_installation_time
ON analytics.fact_product_event (
    installation_key,
    occurred_at
);

CREATE INDEX IF NOT EXISTS
    ix_fact_product_event_user_time
ON analytics.fact_product_event (
    user_key,
    occurred_at
);

CREATE INDEX IF NOT EXISTS
    ix_fact_product_event_name_time
ON analytics.fact_product_event (
    event_name,
    occurred_at
);

CREATE INDEX IF NOT EXISTS
    ix_fact_subscription_user
ON analytics.fact_subscription (user_key);

CREATE INDEX IF NOT EXISTS
    ix_fact_subscription_status
ON analytics.fact_subscription (
    ingestion_batch_id,
    status
);

CREATE INDEX IF NOT EXISTS
    ix_fact_subscription_transaction_subscription
ON analytics.fact_subscription_transaction (subscription_key);

CREATE INDEX IF NOT EXISTS
    ix_fact_subscription_transaction_time
ON analytics.fact_subscription_transaction (
    ingestion_batch_id,
    attempted_at
);

CREATE INDEX IF NOT EXISTS
    ix_fact_experiment_assignment_experiment
ON analytics.fact_experiment_assignment (experiment_key);

CREATE INDEX IF NOT EXISTS
    ix_fact_experiment_assignment_user
ON analytics.fact_experiment_assignment (user_key);

CREATE INDEX IF NOT EXISTS
    ix_fact_marketing_spend_period
ON analytics.fact_marketing_spend (
    ingestion_batch_id,
    period_start
);

COMMIT;
