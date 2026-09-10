-- T4B phase 001: read-only preflight (counts only; no PII values).
-- Run as migration/owner role. STOP if any blocking count > 0 (see README).

SET search_path = public, pg_catalog;

\echo '=== PostgreSQL version / extensions ==='
SELECT version();
SELECT extname, extversion FROM pg_extension ORDER BY extname;

\echo '=== Current user / role flags ==='
SELECT current_user, session_user, current_database();
SELECT rolname, rolsuper, rolbypassrls, rolcreatedb, rolcreaterole
FROM pg_roles
WHERE rolname = current_user;

\echo '=== Database owner ==='
SELECT datname, pg_catalog.pg_get_userbyid(datdba) AS owner
FROM pg_database
WHERE datname = current_database();

\echo '=== Schema owner / grants (public) ==='
SELECT nspname, pg_catalog.pg_get_userbyid(nspowner) AS owner
FROM pg_namespace
WHERE nspname = 'public';

\echo '=== Schema ACL (public) ==='
SELECT nspname, nspacl::text AS acl
FROM pg_namespace
WHERE nspname = 'public';

\echo '=== Schema default privileges (public) ==='
SELECT defaclrole::regrole::text AS grantor,
       defaclnamespace::regnamespace::text AS schema,
       defaclobjtype AS object_type,
       defaclacl::text AS acl
FROM pg_default_acl
WHERE defaclnamespace = 'public'::regnamespace;

\echo '=== Role membership (current user) ==='
SELECT r.rolname AS role, m.rolname AS member
FROM pg_auth_members am
JOIN pg_roles r ON r.oid = am.roleid
JOIN pg_roles m ON m.oid = am.member
WHERE m.rolname = current_user;

\echo '=== Table owners ==='
SELECT tablename, tableowner
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN ('bot_events', 'leads', 'v5_turn_traces');

\echo '=== Table grants (tenant tables) ==='
SELECT grantee, table_schema, table_name, privilege_type
FROM information_schema.table_privileges
WHERE table_schema = 'public'
  AND table_name IN ('bot_events', 'leads', 'v5_turn_traces')
ORDER BY table_name, grantee, privilege_type;

\echo '=== Sequence grants (BIGSERIAL backing sequences) ==='
SELECT grantee, object_schema, object_name, privilege_type
FROM information_schema.usage_privileges
WHERE object_schema = 'public'
  AND object_name IN ('bot_events_id_seq', 'leads_id_seq')
ORDER BY object_name, grantee, privilege_type;

\echo '=== RLS / FORCE RLS status ==='
SELECT c.relname,
       c.relrowsecurity,
       c.relforcerowsecurity
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN ('bot_events', 'leads', 'v5_turn_traces');

\echo '=== Constraint definitions (tenant tables) ==='
SELECT c.conrelid::regclass AS table_name,
       c.conname,
       pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_namespace n ON n.oid = c.connamespace
WHERE n.nspname = 'public'
  AND c.conrelid::regclass::text IN ('bot_events', 'leads', 'v5_turn_traces')
ORDER BY 1, 2;

\echo '=== Column nullability (client_id, turn_id) ==='
SELECT table_name, column_name, is_nullable
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name IN ('bot_events', 'leads', 'v5_turn_traces')
  AND column_name IN ('client_id', 'turn_id')
ORDER BY table_name, column_name;

\echo '=== PK / indexes (v5_turn_traces) ==='
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename = 'v5_turn_traces';

\echo '=== Invalid client_id counts (public.bot_events) ==='
SELECT count(*) AS null_client_id FROM public.bot_events WHERE client_id IS NULL;
SELECT count(*) AS blank_client_id FROM public.bot_events WHERE client_id IS NOT NULL AND btrim(client_id) = '';
SELECT count(*) AS untrimmed_client_id FROM public.bot_events WHERE client_id IS NOT NULL AND client_id <> btrim(client_id);
SELECT count(*) AS sentinel_default FROM public.bot_events WHERE client_id IN ('default', '_template');
SELECT count(*) AS unsafe_path_like FROM public.bot_events
 WHERE client_id ~ '[./\\]' OR client_id LIKE '%..%' OR client_id ~ '^[.-]';
SELECT count(*) AS invalid_format FROM public.bot_events
 WHERE client_id IS NOT NULL
   AND btrim(client_id) <> ''
   AND client_id = btrim(client_id)
   AND client_id !~ '^[a-z0-9][a-z0-9_-]*$';

\echo '=== Invalid client_id counts (public.leads) ==='
SELECT count(*) AS null_client_id FROM public.leads WHERE client_id IS NULL;
SELECT count(*) AS blank_client_id FROM public.leads WHERE client_id IS NOT NULL AND btrim(client_id) = '';
SELECT count(*) AS untrimmed_client_id FROM public.leads WHERE client_id IS NOT NULL AND client_id <> btrim(client_id);
SELECT count(*) AS sentinel_default FROM public.leads WHERE client_id IN ('default', '_template');
SELECT count(*) AS unsafe_path_like FROM public.leads
 WHERE client_id ~ '[./\\]' OR client_id LIKE '%..%' OR client_id ~ '^[.-]';
SELECT count(*) AS invalid_format FROM public.leads
 WHERE client_id IS NOT NULL
   AND btrim(client_id) <> ''
   AND client_id = btrim(client_id)
   AND client_id !~ '^[a-z0-9][a-z0-9_-]*$';

\echo '=== Invalid client_id counts (public.v5_turn_traces) ==='
SELECT count(*) AS null_client_id FROM public.v5_turn_traces WHERE client_id IS NULL;
SELECT count(*) AS blank_client_id FROM public.v5_turn_traces WHERE client_id IS NOT NULL AND btrim(client_id) = '';
SELECT count(*) AS untrimmed_client_id FROM public.v5_turn_traces WHERE client_id IS NOT NULL AND client_id <> btrim(client_id);
SELECT count(*) AS sentinel_default FROM public.v5_turn_traces WHERE client_id IN ('default', '_template');
SELECT count(*) AS unsafe_path_like FROM public.v5_turn_traces
 WHERE client_id ~ '[./\\]' OR client_id LIKE '%..%' OR client_id ~ '^[.-]';
SELECT count(*) AS invalid_format FROM public.v5_turn_traces
 WHERE client_id IS NOT NULL
   AND btrim(client_id) <> ''
   AND client_id = btrim(client_id)
   AND client_id !~ '^[a-z0-9][a-z0-9_-]*$';

\echo '=== Distinct client_id (compare to deployment registry) ==='
SELECT client_id, count(*) FROM public.bot_events GROUP BY client_id ORDER BY client_id;
SELECT client_id, count(*) FROM public.leads GROUP BY client_id ORDER BY client_id;
SELECT client_id, count(*) FROM public.v5_turn_traces GROUP BY client_id ORDER BY client_id;

\echo '=== turn_id hygiene (public.v5_turn_traces) ==='
SELECT count(*) AS null_turn_id FROM public.v5_turn_traces WHERE turn_id IS NULL;
SELECT count(*) AS blank_turn_id FROM public.v5_turn_traces WHERE turn_id IS NOT NULL AND btrim(turn_id) = '';

\echo '=== Historical PII in leads (counts only) ==='
SELECT count(*) AS leads_with_name FROM public.leads WHERE name IS NOT NULL AND btrim(name) <> '';
SELECT count(*) AS leads_with_phone FROM public.leads WHERE phone IS NOT NULL AND btrim(phone) <> '';
