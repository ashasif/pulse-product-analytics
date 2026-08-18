-- Pulse
-- Phase 3, Step 3
-- Typed PostgreSQL raw-layer tables.
--
-- Source/business columns remain in the exact approved source order.
-- Ingestion lineage columns are appended to each table.
--
-- Business transformations and analytics logic do not belong here.

BEGIN;


CREATE TABLE IF NOT EXISTS raw.installations (
    installation_id TEXT NOT NULL,
    anonymous_id TEXT NOT NULL,
    installed_at TIMESTAMPTZ NOT NULL,
    platform TEXT NOT NULL,
    acquisition_channel TEXT NOT NULL,
    country_code TEXT NOT NULL,

    ingestion_batch_id BIGINT NOT NULL,
    source_file TEXT NOT NULL
        CHECK (length(trim(source_file)) > 0),
    source_row_number BIGINT NOT NULL
        CHECK (source_row_number > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_hash TEXT NOT NULL
        CHECK (row_hash ~ '^[0-9a-f]{64}$'),

    PRIMARY KEY (
        ingestion_batch_id,
        source_row_number
    ),

    FOREIGN KEY (
        ingestion_batch_id,
        source_file
    )
        REFERENCES raw.ingestion_files (
            ingestion_batch_id,
            source_file
        )
        ON DELETE RESTRICT
);


CREATE TABLE IF NOT EXISTS raw.users (
    user_id TEXT NOT NULL,
    installation_id TEXT NOT NULL,
    anonymous_id TEXT NOT NULL,
    signed_up_at TIMESTAMPTZ NOT NULL,
    onboarding_started_at TIMESTAMPTZ,
    onboarding_completed_at TIMESTAMPTZ,

    ingestion_batch_id BIGINT NOT NULL,
    source_file TEXT NOT NULL
        CHECK (length(trim(source_file)) > 0),
    source_row_number BIGINT NOT NULL
        CHECK (source_row_number > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_hash TEXT NOT NULL
        CHECK (row_hash ~ '^[0-9a-f]{64}$'),

    PRIMARY KEY (
        ingestion_batch_id,
        source_row_number
    ),

    FOREIGN KEY (
        ingestion_batch_id,
        source_file
    )
        REFERENCES raw.ingestion_files (
            ingestion_batch_id,
            source_file
        )
        ON DELETE RESTRICT
);


CREATE TABLE IF NOT EXISTS raw.product_events (
    event_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    installation_id TEXT NOT NULL,
    anonymous_id TEXT NOT NULL,
    user_id TEXT,
    session_id TEXT,
    feature_name TEXT,

    ingestion_batch_id BIGINT NOT NULL,
    source_file TEXT NOT NULL
        CHECK (length(trim(source_file)) > 0),
    source_row_number BIGINT NOT NULL
        CHECK (source_row_number > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_hash TEXT NOT NULL
        CHECK (row_hash ~ '^[0-9a-f]{64}$'),

    PRIMARY KEY (
        ingestion_batch_id,
        source_row_number
    ),

    FOREIGN KEY (
        ingestion_batch_id,
        source_file
    )
        REFERENCES raw.ingestion_files (
            ingestion_batch_id,
            source_file
        )
        ON DELETE RESTRICT
);


CREATE TABLE IF NOT EXISTS raw.subscriptions (
    subscription_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    installation_id TEXT NOT NULL,
    billing_period TEXT NOT NULL,
    price_gbp NUMERIC NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    trial_started_at TIMESTAMPTZ NOT NULL,
    trial_ends_at TIMESTAMPTZ NOT NULL,
    subscription_started_at TIMESTAMPTZ,
    current_period_start_at TIMESTAMPTZ,
    current_period_end_at TIMESTAMPTZ,
    cancellation_requested_at TIMESTAMPTZ,
    expired_at TIMESTAMPTZ,
    auto_renew BOOLEAN NOT NULL,
    end_reason TEXT,

    ingestion_batch_id BIGINT NOT NULL,
    source_file TEXT NOT NULL
        CHECK (length(trim(source_file)) > 0),
    source_row_number BIGINT NOT NULL
        CHECK (source_row_number > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_hash TEXT NOT NULL
        CHECK (row_hash ~ '^[0-9a-f]{64}$'),

    PRIMARY KEY (
        ingestion_batch_id,
        source_row_number
    ),

    FOREIGN KEY (
        ingestion_batch_id,
        source_file
    )
        REFERENCES raw.ingestion_files (
            ingestion_batch_id,
            source_file
        )
        ON DELETE RESTRICT
);


CREATE TABLE IF NOT EXISTS raw.subscription_transactions (
    transaction_id TEXT NOT NULL,
    subscription_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    installation_id TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL,
    billing_period TEXT NOT NULL,
    amount_gbp NUMERIC NOT NULL,
    currency TEXT NOT NULL,
    payment_status TEXT NOT NULL,
    billing_cycle_number INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,

    ingestion_batch_id BIGINT NOT NULL,
    source_file TEXT NOT NULL
        CHECK (length(trim(source_file)) > 0),
    source_row_number BIGINT NOT NULL
        CHECK (source_row_number > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_hash TEXT NOT NULL
        CHECK (row_hash ~ '^[0-9a-f]{64}$'),

    PRIMARY KEY (
        ingestion_batch_id,
        source_row_number
    ),

    FOREIGN KEY (
        ingestion_batch_id,
        source_file
    )
        REFERENCES raw.ingestion_files (
            ingestion_batch_id,
            source_file
        )
        ON DELETE RESTRICT
);


CREATE TABLE IF NOT EXISTS raw.experiment_assignments (
    assignment_id TEXT NOT NULL,
    experiment_id TEXT NOT NULL,
    experiment_name TEXT NOT NULL,
    user_id TEXT NOT NULL,
    installation_id TEXT NOT NULL,
    randomization_unit TEXT NOT NULL,
    variant TEXT NOT NULL,
    allocation_probability NUMERIC NOT NULL,
    assignment_at TIMESTAMPTZ NOT NULL,
    exposed_at TIMESTAMPTZ,
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

    ingestion_batch_id BIGINT NOT NULL,
    source_file TEXT NOT NULL
        CHECK (length(trim(source_file)) > 0),
    source_row_number BIGINT NOT NULL
        CHECK (source_row_number > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_hash TEXT NOT NULL
        CHECK (row_hash ~ '^[0-9a-f]{64}$'),

    PRIMARY KEY (
        ingestion_batch_id,
        source_row_number
    ),

    FOREIGN KEY (
        ingestion_batch_id,
        source_file
    )
        REFERENCES raw.ingestion_files (
            ingestion_batch_id,
            source_file
        )
        ON DELETE RESTRICT
);


CREATE TABLE IF NOT EXISTS raw.marketing_spend (
    marketing_spend_id TEXT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    acquisition_channel TEXT NOT NULL,
    spend_type TEXT NOT NULL,
    campaign_type TEXT NOT NULL,
    spend NUMERIC NOT NULL,
    currency TEXT NOT NULL,
    impressions INTEGER,
    clicks INTEGER,

    ingestion_batch_id BIGINT NOT NULL,
    source_file TEXT NOT NULL
        CHECK (length(trim(source_file)) > 0),
    source_row_number BIGINT NOT NULL
        CHECK (source_row_number > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_hash TEXT NOT NULL
        CHECK (row_hash ~ '^[0-9a-f]{64}$'),

    PRIMARY KEY (
        ingestion_batch_id,
        source_row_number
    ),

    FOREIGN KEY (
        ingestion_batch_id,
        source_file
    )
        REFERENCES raw.ingestion_files (
            ingestion_batch_id,
            source_file
        )
        ON DELETE RESTRICT
);


CREATE TABLE IF NOT EXISTS raw.app_releases (
    app_release_id TEXT NOT NULL,
    release_key TEXT NOT NULL,
    release_name TEXT NOT NULL,
    release_sequence INTEGER NOT NULL,
    platform TEXT NOT NULL,
    version TEXT NOT NULL,
    release_at TIMESTAMPTZ NOT NULL,
    release_type TEXT NOT NULL,
    feature_area TEXT NOT NULL,
    rollout_strategy TEXT NOT NULL,
    rollout_days INTEGER NOT NULL,
    rollout_complete_at TIMESTAMPTZ NOT NULL,
    release_channel TEXT NOT NULL,
    release_notes TEXT NOT NULL,

    ingestion_batch_id BIGINT NOT NULL,
    source_file TEXT NOT NULL
        CHECK (length(trim(source_file)) > 0),
    source_row_number BIGINT NOT NULL
        CHECK (source_row_number > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_hash TEXT NOT NULL
        CHECK (row_hash ~ '^[0-9a-f]{64}$'),

    PRIMARY KEY (
        ingestion_batch_id,
        source_row_number
    ),

    FOREIGN KEY (
        ingestion_batch_id,
        source_file
    )
        REFERENCES raw.ingestion_files (
            ingestion_batch_id,
            source_file
        )
        ON DELETE RESTRICT
);


COMMIT;