-- G8 disposable post-migration grants (mirrors migrations/postgresql/roles_template.sql post section).
SET search_path = public, pg_catalog;

ALTER TABLE IF EXISTS public.bot_events OWNER TO bot_migrator;
ALTER TABLE IF EXISTS public.leads OWNER TO bot_migrator;
ALTER TABLE IF EXISTS public.v5_turn_traces OWNER TO bot_migrator;
ALTER SCHEMA bot_migration OWNER TO bot_migrator;
ALTER TABLE IF EXISTS bot_migration.schema_migrations OWNER TO bot_migrator;

REVOKE ALL ON SCHEMA bot_migration FROM PUBLIC, bot_runtime;
REVOKE ALL ON TABLE bot_migration.schema_migrations FROM PUBLIC, bot_runtime;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.bot_events TO bot_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.leads TO bot_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.v5_turn_traces TO bot_runtime;

GRANT USAGE, SELECT ON SEQUENCE public.bot_events_id_seq TO bot_runtime;
GRANT USAGE, SELECT ON SEQUENCE public.leads_id_seq TO bot_runtime;
REVOKE UPDATE ON SEQUENCE public.bot_events_id_seq FROM bot_runtime;
REVOKE UPDATE ON SEQUENCE public.leads_id_seq FROM bot_runtime;
