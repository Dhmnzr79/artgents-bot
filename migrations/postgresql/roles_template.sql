-- Environment-specific role provisioning template (review before production use).
-- No passwords in repository. Run as superuser or existing table owner.

-- Migrator / owner role (DDL + migrations only):
-- CREATE ROLE bot_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
-- ALTER TABLE public.bot_events OWNER TO bot_migrator;
-- ALTER TABLE public.leads OWNER TO bot_migrator;
-- ALTER TABLE public.v5_turn_traces OWNER TO bot_migrator;
-- (Optional) ALTER SEQUENCE public.bot_events_id_seq OWNER TO bot_migrator;
-- (Optional) ALTER SEQUENCE public.leads_id_seq OWNER TO bot_migrator;

-- Runtime role (DML only; not owner; no DDL):
-- CREATE ROLE bot_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;

-- GRANT CONNECT ON DATABASE :dbname TO bot_runtime;
-- GRANT USAGE ON SCHEMA public TO bot_runtime;
-- REVOKE CREATE ON SCHEMA public FROM bot_runtime;

-- GRANT SELECT, INSERT, UPDATE, DELETE ON public.bot_events TO bot_runtime;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON public.leads TO bot_runtime;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON public.v5_turn_traces TO bot_runtime;

-- Sequences used by BIGSERIAL inserts only:
-- GRANT USAGE, SELECT ON SEQUENCE public.bot_events_id_seq TO bot_runtime;
-- GRANT USAGE, SELECT ON SEQUENCE public.leads_id_seq TO bot_runtime;

-- Verification (read-only):
-- SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole
-- FROM pg_roles WHERE rolname IN ('bot_migrator', 'bot_runtime');
-- SELECT tablename, tableowner FROM pg_tables
-- WHERE schemaname='public' AND tablename IN ('bot_events','leads','v5_turn_traces');
