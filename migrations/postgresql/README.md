# PostgreSQL tenant RLS migrations (T4B / T6B)

Phased rollout for `bot_events`, `leads`, `v5_turn_traces`. **Do not** apply to production without owner-approved preflight.

## Role model

| Role | Purpose |
|------|---------|
| **Bootstrap** (container superuser or equivalent) | One-time database + role provisioning on VPS only. Never used by bot/admin. Not in application env. |
| **`bot_migrator`** | `LOGIN`, `NOSUPERUSER`, `NOBYPASSRLS`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`. Owns tenant tables and `bot_migration` ledger. Runs DDL/migrations only (`BOT_MIGRATOR_PG_DSN`). |
| **`bot_runtime`** | Same privilege flags; does **not** own tenant tables. DML + sequence grants only (`BOT_PG_DSN`). No `CREATE` on `public`, no ledger access. |

See `roles_template.sql` for **pre-migration** vs **post-migration** grant order (`bot_migration` revokes only after the migrator creates the ledger schema).

## Greenfield sequence (new empty database)

1. Bootstrap: database exists.
2. Run **pre-migration** steps from `roles_template.sql` (roles + `public` schema ACL; no `bot_migration` revokes yet).
3. First migrator run (`deploy/postgres/migrate.py`) creates `bot_migration` ledger and applies manifest mutations.
4. Run **post-migration** grants/revokes from `roles_template.sql` (runtime DML, sequence grants, ledger revokes).
5. Run **`001_tenant_preflight.sql`** as post-create verification (`psql` — contains `\echo`; not executed by the Python migrator).
6. Deploy application compatible with `tenant_transaction` + `ON CONFLICT (client_id, turn_id)` (no runtime DDL).
7. Verify role flags, ownership, `FORCE RLS`, policies, grants (read-only catalog queries).
8. Run integration suite under non-owner `bot_runtime` (`BOT_TEST_PG_DSN` — disposable DB only).
9. Only after integration **PASS** (0 skipped): allow bot/admin production startup.

**`001` must not run first on an empty database** and is **not** in `deploy/postgres/migrations.manifest`.

Recommended mutation order for greenfield (manifest): `002` → `003` → `004`.

## Brownfield sequence (existing database)

Do not mix with greenfield steps on the same cutover plan.

1. **`001_tenant_preflight.sql`** — read-only counts; **STOP** on invalid data.
2. **STOP** if bad counts, owners, or grants.
3. Backup.
4. `python deploy/postgres/migrate.py --through 002_tenant_schema_prepare.sql` (migrator DSN only).
5. Deploy compatible application (no runtime DDL).
6. Verification reads/writes per tenant.
7. `python deploy/postgres/migrate.py` (no `--through`) for **`003`** and **`004`**.
8. Fail-closed RLS verification (unset `app.current_tenant` denies access).
9. Post-deploy read-only verification (`001` subset).

**Do not** apply mutation SQL manually outside the ledger runner (`002`–`004` must be recorded in `bot_migration.schema_migrations`).

Legacy upgrade order (pre-manifest brownfield) remains documented in phase comments inside `002`–`004`.

## Migration ledger

- Runner: `deploy/postgres/migrate.py`
- Manifest: `deploy/postgres/migrations.manifest` (mutations only: `002`, `003`, `004`)
- DSN: `BOT_MIGRATOR_PG_DSN` only
- Ledger table: `bot_migration.schema_migrations` (`filename`, `checksum` SHA-256 of file bytes, `applied_at`)
- Session `pg_advisory_lock` for the full run; runtime role has no ledger access
- `--dry-run`: no database writes (supports `--through`)
- `--through <exact manifest filename>`: apply only sequential manifest prefix (brownfield pause after `002`)
- Ledger reconciliation and checksum checks use the **full** manifest; only the prefix is executed
- Application deploy must run pending migrations **before** startup; bot/admin never apply DDL

### Crash window (not atomic with ledger)

Migration files use their own `BEGIN`/`COMMIT`. A crash after SQL commit but before ledger insert can leave the DB migrated without a ledger row. **Do not claim atomic ledger+DDL.** Re-run the migrator: replay-safe migrations (notably **`004`**) detect desired end state and skip redundant work; the runner then records the ledger row when SQL succeeds.

`001` remains **psql-only** verification and is **not** in `migrations.manifest`.

## Stop conditions (preflight / 001)

- Any invalid `client_id` row (NULL, blank, untrimmed, `default`, `_template`, unsafe/path-like, bad format).
- `turn_id` NULL/blank in `v5_turn_traces`.
- Distinct `client_id` values outside deployment-approved registry (manual review).
- Historical `leads.name` / `leads.phone` counts > 0 → privacy decision before migration (no automatic redaction in T4B).

## Integration qualification (`BOT_TEST_PG_DSN`)

- Disposable test database only; database name **must** contain `test`.
- Connection role: non-owner `bot_runtime` (not `SUPERUSER` / `BYPASSRLS`).
- Schema: migrations `002` + `003` + `004` applied.
- Suite: `tests/test_pg_tenant_rls_integration.py` (14 scenarios); **0 skipped** required before first production traffic.
- Cleanup: marker-owned rows only (`t4b-int-` prefix).
- **Never** use production `BOT_PG_DSN` as test DSN.

## Fail-closed rollback

- **Do not** use `DISABLE ROW LEVEL SECURITY` or privileged shared DSN as normal rollback.
- Safe rollback: keep RLS; roll app back to a version **with** `tenant_transaction`, or disable PG sink/retention/admin DB endpoints (`BOT_PG_DSN` unset).
- Observability loss is acceptable; cross-tenant exposure is not.
- Data/backfill changes require backup and mapping ledger; prefer roll-forward fixes.
