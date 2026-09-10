-- T4B phase 003: enable RLS (after app deploy with tenant_transaction hooks).
-- Apply as table owner / migrator. Runtime role must not own tables.

SET search_path = public, pg_catalog;

BEGIN;

ALTER TABLE public.bot_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.bot_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.bot_events;
CREATE POLICY tenant_isolation ON public.bot_events
  FOR ALL
  USING (client_id = NULLIF(current_setting('app.current_tenant', true), ''))
  WITH CHECK (client_id = NULLIF(current_setting('app.current_tenant', true), ''));

ALTER TABLE public.leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leads FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.leads;
CREATE POLICY tenant_isolation ON public.leads
  FOR ALL
  USING (client_id = NULLIF(current_setting('app.current_tenant', true), ''))
  WITH CHECK (client_id = NULLIF(current_setting('app.current_tenant', true), ''));

ALTER TABLE public.v5_turn_traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.v5_turn_traces FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_isolation ON public.v5_turn_traces;
CREATE POLICY tenant_isolation ON public.v5_turn_traces
  FOR ALL
  USING (client_id = NULLIF(current_setting('app.current_tenant', true), ''))
  WITH CHECK (client_id = NULLIF(current_setting('app.current_tenant', true), ''));

COMMIT;
