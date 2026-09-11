-- T4B phase 004: finalize v5_turn_traces primary key (client_id, turn_id).
-- Run only after app uses ON CONFLICT (client_id, turn_id) and unique index exists.
-- Replay-safe: if PK is already (client_id, turn_id), no DROP/ADD.

SET search_path = public, pg_catalog;

BEGIN;

-- Ensure composite unique exists (created in 002).
CREATE UNIQUE INDEX IF NOT EXISTS v5_turn_traces_client_turn_uidx
  ON public.v5_turn_traces (client_id, turn_id);

DO $$
DECLARE
  pk_name text;
  pk_cols text[];
  expected_cols text[] := ARRAY['client_id', 'turn_id'];
BEGIN
  SELECT c.conname,
         array_agg(a.attname ORDER BY u.ordinality)
    INTO pk_name, pk_cols
  FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  JOIN unnest(c.conkey) WITH ORDINALITY AS u(attnum, ordinality) ON true
  JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = u.attnum
  WHERE n.nspname = 'public'
    AND t.relname = 'v5_turn_traces'
    AND c.contype = 'p'
  GROUP BY c.oid, c.conname;

  IF pk_cols IS NOT NULL AND pk_cols = expected_cols THEN
    RETURN;
  END IF;

  IF pk_name IS NOT NULL AND pk_name <> '' THEN
    EXECUTE format('ALTER TABLE public.v5_turn_traces DROP CONSTRAINT %I', pk_name);
  END IF;

  ALTER TABLE public.v5_turn_traces
    ADD CONSTRAINT v5_turn_traces_pkey PRIMARY KEY (client_id, turn_id);
END $$;

COMMIT;
