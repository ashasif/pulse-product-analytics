\set ON_ERROR_STOP on

SELECT
    'CREATE ROLE pulse_reporting_reader
        NOLOGIN
        NOSUPERUSER
        INHERIT
        NOCREATEDB
        NOCREATEROLE
        NOREPLICATION
        NOBYPASSRLS'
WHERE NOT EXISTS (
    SELECT 1
    FROM pg_roles
    WHERE rolname = 'pulse_reporting_reader'
)
\gexec


ALTER ROLE pulse_reporting_reader
    NOLOGIN
    NOSUPERUSER
    INHERIT
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION
    NOBYPASSRLS;


COMMENT ON ROLE pulse_reporting_reader IS
    'Pulse reporting-consumer group role. Provides read-only access to the reporting semantic layer and no direct warehouse-layer access.';