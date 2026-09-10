# PostgreSQL tenant RLS migrations (T4B)

Phased rollout for `bot_events`, `leads`, `v5_turn_traces`. **Do not** apply to production without owner-approved preflight.

## Upgrade order

1. **001_tenant_preflight.sql** — read-only counts; stop if invalid `client_id`, bad `turn_id`, or unexpected PII counts in `leads`.
2. **002_tenant_schema_prepare.sql** — `NOT NULL`, format CHECK, tenant-first indexes, `UNIQUE (client_id, turn_id)` on traces (keeps legacy `PRIMARY KEY (turn_id)` if present).
3. **Deploy application** with `tenant_transaction` + `ON CONFLICT (client_id, turn_id)` (no runtime DDL).
4. Verify writes/reads per tenant.
5. **003_tenant_rls_enable.sql** — `ENABLE` + `FORCE ROW LEVEL SECURITY` + fail-closed policies on `app.current_tenant`.
6. Verify fail-closed (unset GUC denies access).
7. **004_tenant_trace_pk_finalize.sql** — replace global PK with `(client_id, turn_id)` after app UPSERT alignment.
8. Post-deploy read-only verification (001 subset).

## Stop conditions (preflight)

- Any invalid `client_id` row (NULL, blank, untrimmed, `default`, `_template`, unsafe/path-like, bad format).
- `turn_id` NULL/blank in `v5_turn_traces`.
- Distinct `client_id` values outside deployment-approved registry (manual review).
- Historical `leads.name` / `leads.phone` counts > 0 → privacy decision before migration (no automatic redaction in T4B).

## Roles

Use `roles_template.sql` in a separate maintenance window. Runtime role must not be SUPERUSER, BYPASSRLS, or table owner.

## Fail-closed rollback

- **Do not** use `DISABLE ROW LEVEL SECURITY` or privileged shared DSN as normal rollback.
- Safe rollback: keep RLS; roll app back to a version **with** `tenant_transaction`, or disable PG sink/retention/admin DB endpoints (`BOT_PG_DSN` unset).
- Observability loss is acceptable; cross-tenant exposure is not.
- Data/backfill changes require backup and mapping ledger; prefer roll-forward fixes.
