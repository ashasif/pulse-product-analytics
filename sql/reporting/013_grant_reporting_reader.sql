BEGIN;

GRANT USAGE
ON SCHEMA reporting
TO pulse_reporting_reader;


GRANT SELECT
ON ALL TABLES IN SCHEMA reporting
TO pulse_reporting_reader;


REVOKE
    INSERT,
    UPDATE,
    DELETE,
    TRUNCATE,
    REFERENCES,
    TRIGGER
ON ALL TABLES IN SCHEMA reporting
FROM pulse_reporting_reader;


REVOKE ALL
ON SCHEMA raw
FROM pulse_reporting_reader;

REVOKE ALL
ON SCHEMA staging
FROM pulse_reporting_reader;

REVOKE ALL
ON SCHEMA validation
FROM pulse_reporting_reader;

REVOKE ALL
ON SCHEMA analytics
FROM pulse_reporting_reader;


ALTER DEFAULT PRIVILEGES
FOR ROLE pulse_app
IN SCHEMA reporting
GRANT SELECT
ON TABLES
TO pulse_reporting_reader;

COMMIT;