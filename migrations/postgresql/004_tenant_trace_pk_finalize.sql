-- T4B phase 004: finalize v5_turn_traces primary key (client_id, turn_id).
-- Run only after app uses ON CONFLICT (client_id, turn_id) and unique index exists.

SET search_path = public, pg_catalog;

BEGIN;

-- Ensure composite unique exists (created in 002).
CREATE UNIQUE INDEX IF NOT EXISTS v5_turn_traces_client_turn_uidx
  ON public.v5_turn_traces (client_id, turn_id);

DO $$
DECLARE
  pk_name text;
BEGIN
  SELECT conname INTO pk_name
  FROM pg_constraint
  WHERE conrelid = 'public.v5_turn_traces'::regclass
    AND contype = 'p';
  IF pk_name IS NOT NULL AND pk_name <> '' THEN
    EXECUTE format('ALTER TABLE public.v5_turn_traces DROP CONSTRAINT %I', pk_name);
  END IF;
END $$;

ALTER TABLE public.v5_turn_traces
  ADD CONSTRAINT v5_turn_traces_pkey PRIMARY KEY (client_id, turn_id);

COMMIT;
