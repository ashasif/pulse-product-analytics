-- Pulse
-- Phase 3, Step 3
-- PostgreSQL warehouse schema foundation.

BEGIN;

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS validation;

COMMIT;