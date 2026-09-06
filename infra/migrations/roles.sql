-- Database roles and grants.
--
-- Append-only is enforced here, not by convention in application code.
-- The application role has INSERT and SELECT on the append-only tables and no
-- UPDATE or DELETE grant at all, so a bug or a compromised process cannot
-- rewrite history. Only the migrator role can alter structure.
--
-- ADR 0006. Two schemas: `clinical` holds the record with no patient reference
-- of any kind, `restricted` holds the linkage. A dump of `clinical` is then
-- genuinely unlinkable rather than merely pseudonymous.

CREATE SCHEMA IF NOT EXISTS clinical;
CREATE SCHEMA IF NOT EXISTS restricted;

CREATE EXTENSION IF NOT EXISTS postgis;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nidana_app') THEN
        CREATE ROLE nidana_app LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nidana_reader') THEN
        CREATE ROLE nidana_reader LOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA clinical TO nidana_app, nidana_reader;

-- The application may add rows and read them. It may not change or remove them.
ALTER DEFAULT PRIVILEGES IN SCHEMA clinical
    GRANT SELECT, INSERT ON TABLES TO nidana_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA clinical
    GRANT SELECT ON TABLES TO nidana_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA clinical
    GRANT USAGE, SELECT ON SEQUENCES TO nidana_app;

-- Patient linkage is separate and the reader role cannot reach it at all.
GRANT USAGE ON SCHEMA restricted TO nidana_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA restricted
    GRANT SELECT, INSERT ON TABLES TO nidana_app;

REVOKE ALL ON SCHEMA restricted FROM nidana_reader;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
