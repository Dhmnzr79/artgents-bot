-- T4B phase 002: schema hardening (run as migrator/owner on public schema).
-- STOP on invalid rows (preflight). No Demo backfill.

SET search_path = public, pg_temp;

BEGIN;

-- Inline CHECK expression (stable identifier format; not dynamic registry membership).
-- Duplicated in greenfield CREATE and brownfield ADD CONSTRAINT (no pg_temp in table CHECK).

-- client_id format:
--   client_id = btrim(client_id)
--   AND length(client_id) > 0
--   AND client_id !~ '[./\\]'
--   AND client_id NOT LIKE '%..%'
--   AND client_id !~ '^[.-]'
--   AND client_id ~ '^[a-z0-9][a-z0-9_-]*$'
--   AND client_id NOT IN ('default', '_template')

CREATE OR REPLACE FUNCTION pg_temp._assert_no_invalid_client_id(tbl regclass) RETURNS void AS $$
DECLARE
  bad bigint;
BEGIN
  EXECUTE format(
    'SELECT count(*) FROM %s WHERE client_id IS NULL OR btrim(client_id) = '''' OR client_id <> btrim(client_id)
       OR client_id IN (''default'', ''_template'')
       OR client_id ~ ''[./\\]'' OR client_id LIKE ''%%..%%'' OR client_id ~ ''^[.-]''
       OR client_id !~ ''^[a-z0-9][a-z0-9_-]*$''',
    tbl
  ) INTO bad;
  IF bad > 0 THEN
    RAISE EXCEPTION 'invalid client_id rows in %: %', tbl, bad;
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION pg_temp._strip_redundant_outer_parens(expr text) RETURNS text AS $$
DECLARE
  inner text := btrim(expr);
  candidate text;
BEGIN
  WHILE length(inner) >= 2 AND left(inner, 1) = '(' AND right(inner, 1) = ')' LOOP
    candidate := btrim(substring(inner from 2 for length(inner) - 2));
    IF (length(regexp_replace(candidate, '[^(]', '', 'g')) <>
        length(regexp_replace(candidate, '[^)]', '', 'g'))) THEN
      EXIT;
    END IF;
    inner := candidate;
  END LOOP;
  RETURN inner;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION pg_temp._normalize_check_expr(def text) RETURNS text AS $$
  SELECT lower(
    regexp_replace(
      pg_temp._strip_redundant_outer_parens(substring(def from '^CHECK \((.*)\)$')),
      '\s+',
      ' ',
      'g'
    )
  );
$$ LANGUAGE sql IMMUTABLE;

CREATE OR REPLACE FUNCTION pg_temp._ensure_t4b_check_constraint(
  p_schema text,
  p_table text,
  p_constraint text,
  p_check_sql text
) RETURNS void AS $$
DECLARE
  existing_def text;
  expected_def text;
BEGIN
  expected_def := 'CHECK (' || p_check_sql || ')';

  SELECT pg_get_constraintdef(c.oid) INTO existing_def
  FROM pg_constraint c
  JOIN pg_class t ON t.oid = c.conrelid
  JOIN pg_namespace n ON n.oid = t.relnamespace
  WHERE n.nspname = p_schema
    AND t.relname = p_table
    AND c.conname = p_constraint
    AND c.contype = 'c';

  IF existing_def IS NOT NULL THEN
    IF pg_temp._normalize_check_expr(existing_def) IS DISTINCT FROM pg_temp._normalize_check_expr(expected_def) THEN
      EXECUTE format(
        'ALTER TABLE %I.%I DROP CONSTRAINT %I',
        p_schema, p_table, p_constraint
      );
      existing_def := NULL;
    END IF;
  END IF;

  IF existing_def IS NULL THEN
    EXECUTE format(
      'ALTER TABLE %I.%I ADD CONSTRAINT %I CHECK (%s) NOT VALID',
      p_schema, p_table, p_constraint, p_check_sql
    );
    EXECUTE format(
      'ALTER TABLE %I.%I VALIDATE CONSTRAINT %I',
      p_schema, p_table, p_constraint
    );
  END IF;
END;
$$ LANGUAGE plpgsql;

-- Greenfield: create tables if missing (constraints included in CREATE).
DO $$
BEGIN
  IF to_regclass('public.bot_events') IS NULL THEN
    CREATE TABLE public.bot_events (
      id BIGSERIAL PRIMARY KEY,
      occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      kind TEXT NOT NULL,
      event_type TEXT NOT NULL,
      schema_version INTEGER NOT NULL,
      request_id TEXT,
      sid TEXT,
      client_id TEXT NOT NULL,
      path TEXT,
      status TEXT,
      details JSONB NOT NULL DEFAULT '{}'::jsonb,
      CONSTRAINT bot_events_client_id_format CHECK (
        client_id = btrim(client_id)
        AND length(client_id) > 0
        AND client_id !~ '[./\\]'
        AND client_id NOT LIKE '%..%'
        AND client_id !~ '^[.-]'
        AND client_id ~ '^[a-z0-9][a-z0-9_-]*$'
        AND client_id NOT IN ('default', '_template')
      )
    );
    CREATE INDEX idx_bot_events_occurred_at ON public.bot_events (occurred_at DESC);
    CREATE INDEX idx_bot_events_client_time ON public.bot_events (client_id, occurred_at DESC);
    CREATE INDEX idx_bot_events_client_sid_time ON public.bot_events (client_id, sid, occurred_at DESC);
    CREATE INDEX idx_bot_events_event_type_time ON public.bot_events (event_type, occurred_at DESC);
    CREATE INDEX idx_bot_events_request_id ON public.bot_events (request_id);
  END IF;

  IF to_regclass('public.leads') IS NULL THEN
    CREATE TABLE public.leads (
      id BIGSERIAL PRIMARY KEY,
      captured_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      request_id TEXT,
      sid TEXT,
      client_id TEXT NOT NULL,
      name TEXT,
      phone TEXT,
      topic TEXT,
      cta_action TEXT,
      turns_to_lead INTEGER,
      delivery_status TEXT,
      CONSTRAINT leads_client_id_format CHECK (
        client_id = btrim(client_id)
        AND length(client_id) > 0
        AND client_id !~ '[./\\]'
        AND client_id NOT LIKE '%..%'
        AND client_id !~ '^[.-]'
        AND client_id ~ '^[a-z0-9][a-z0-9_-]*$'
        AND client_id NOT IN ('default', '_template')
      )
    );
    CREATE INDEX idx_leads_captured_at ON public.leads (captured_at DESC);
    CREATE INDEX idx_leads_client_time ON public.leads (client_id, captured_at DESC);
    CREATE INDEX idx_leads_client_sid ON public.leads (client_id, sid);
  END IF;

  IF to_regclass('public.v5_turn_traces') IS NULL THEN
    CREATE TABLE public.v5_turn_traces (
      turn_id TEXT NOT NULL,
      ts TIMESTAMPTZ NOT NULL,
      sid TEXT,
      client_id TEXT NOT NULL,
      request_id TEXT,
      gate_traces JSONB NOT NULL DEFAULT '[]'::jsonb,
      decision_frame JSONB,
      source_routing JSONB,
      retrieval_candidates JSONB NOT NULL DEFAULT '[]'::jsonb,
      arbiter_decision JSONB,
      generator_input JSONB,
      verifier_verdict JSONB,
      final_payload JSONB,
      latency_ms JSONB,
      errors JSONB NOT NULL DEFAULT '[]'::jsonb,
      safety_net_used JSONB NOT NULL DEFAULT '[]'::jsonb,
      resolver_bypassed_env BOOLEAN NOT NULL DEFAULT false,
      PRIMARY KEY (turn_id),
      CONSTRAINT v5_turn_traces_client_id_format CHECK (
        client_id = btrim(client_id)
        AND length(client_id) > 0
        AND client_id !~ '[./\\]'
        AND client_id NOT LIKE '%..%'
        AND client_id !~ '^[.-]'
        AND client_id ~ '^[a-z0-9][a-z0-9_-]*$'
        AND client_id NOT IN ('default', '_template')
      ),
      CONSTRAINT v5_turn_traces_turn_id_nonempty CHECK (turn_id IS NOT NULL AND btrim(turn_id) <> '')
    );
    CREATE UNIQUE INDEX v5_turn_traces_client_turn_uidx ON public.v5_turn_traces (client_id, turn_id);
    CREATE INDEX idx_v5_turn_traces_time ON public.v5_turn_traces (ts DESC);
    CREATE INDEX idx_v5_turn_traces_client_time ON public.v5_turn_traces (client_id, ts DESC);
    CREATE INDEX idx_v5_turn_traces_client_sid_time ON public.v5_turn_traces (client_id, sid, ts DESC);
  END IF;
END $$;

-- Brownfield: bring legacy v5_turn_traces to current column set or fail-fast.
DO $$
BEGIN
  IF to_regclass('public.v5_turn_traces') IS NULL THEN
    RAISE EXCEPTION 'v5_turn_traces missing after greenfield block';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'v5_turn_traces' AND column_name = 'safety_net_used'
  ) THEN
    ALTER TABLE public.v5_turn_traces
      ADD COLUMN safety_net_used JSONB NOT NULL DEFAULT '[]'::jsonb;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'v5_turn_traces' AND column_name = 'resolver_bypassed_env'
  ) THEN
    ALTER TABLE public.v5_turn_traces
      ADD COLUMN resolver_bypassed_env BOOLEAN NOT NULL DEFAULT false;
  END IF;
END $$;

-- Data assertions before NOT NULL / constraints on brownfield rows.
SELECT pg_temp._assert_no_invalid_client_id('public.bot_events'::regclass);
SELECT pg_temp._assert_no_invalid_client_id('public.leads'::regclass);
SELECT pg_temp._assert_no_invalid_client_id('public.v5_turn_traces'::regclass);

DO $$
DECLARE
  bad bigint;
BEGIN
  SELECT count(*) INTO bad
  FROM public.v5_turn_traces
  WHERE turn_id IS NULL OR btrim(turn_id) = '';
  IF bad > 0 THEN
    RAISE EXCEPTION 'invalid turn_id rows in public.v5_turn_traces: %', bad;
  END IF;
END $$;

-- T4B CHECK constraints: fail-fast on semantic drift, else ensure NOT VALID + VALIDATE.
SELECT pg_temp._ensure_t4b_check_constraint(
  'public', 'bot_events', 'bot_events_client_id_format',
  'client_id = btrim(client_id) AND length(client_id) > 0 AND client_id !~ ''[./\\]'' AND client_id NOT LIKE ''%..%'' AND client_id !~ ''^[.-]'' AND client_id ~ ''^[a-z0-9][a-z0-9_-]*$'' AND client_id NOT IN (''default'', ''_template'')'
);
SELECT pg_temp._ensure_t4b_check_constraint(
  'public', 'leads', 'leads_client_id_format',
  'client_id = btrim(client_id) AND length(client_id) > 0 AND client_id !~ ''[./\\]'' AND client_id NOT LIKE ''%..%'' AND client_id !~ ''^[.-]'' AND client_id ~ ''^[a-z0-9][a-z0-9_-]*$'' AND client_id NOT IN (''default'', ''_template'')'
);
SELECT pg_temp._ensure_t4b_check_constraint(
  'public', 'v5_turn_traces', 'v5_turn_traces_client_id_format',
  'client_id = btrim(client_id) AND length(client_id) > 0 AND client_id !~ ''[./\\]'' AND client_id NOT LIKE ''%..%'' AND client_id !~ ''^[.-]'' AND client_id ~ ''^[a-z0-9][a-z0-9_-]*$'' AND client_id NOT IN (''default'', ''_template'')'
);
SELECT pg_temp._ensure_t4b_check_constraint(
  'public', 'v5_turn_traces', 'v5_turn_traces_turn_id_nonempty',
  'turn_id IS NOT NULL AND btrim(turn_id) <> '''''
);

ALTER TABLE public.bot_events ALTER COLUMN client_id SET NOT NULL;
ALTER TABLE public.leads ALTER COLUMN client_id SET NOT NULL;
ALTER TABLE public.v5_turn_traces ALTER COLUMN client_id SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS v5_turn_traces_client_turn_uidx
  ON public.v5_turn_traces (client_id, turn_id);

CREATE INDEX IF NOT EXISTS idx_bot_events_client_sid_time
  ON public.bot_events (client_id, sid, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_leads_client_sid
  ON public.leads (client_id, sid);
CREATE INDEX IF NOT EXISTS idx_v5_turn_traces_client_sid_time
  ON public.v5_turn_traces (client_id, sid, ts DESC);

COMMIT;
